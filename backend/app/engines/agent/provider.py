"""Open-weight Hugging Face chat inference over HTTP; no proprietary model SDK."""

import asyncio
import json
from typing import Protocol
from urllib.parse import urlsplit

import httpx
from pydantic import ValidationError

from app.core.config import Settings
from app.engines.agent.actions import AgentAction


class InvalidAction(ValueError):
    pass


class InferenceError(RuntimeError):
    pass


class LLMProvider(Protocol):
    async def generate_action(self, messages: list[dict]) -> AgentAction: ...
    async def close(self) -> None: ...


class HuggingFaceProvider:
    def __init__(self, settings: Settings, transport=None):
        self.settings = settings
        self.usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        self.failures = 0
        self.retries = 0
        # Local servers are operator configuration, never website/model supplied.
        base = settings.agent_llm_base_url.rstrip("/")
        if not settings.agent_model.startswith("Qwen/"):
            raise InferenceError("This MVP supports verified open-weight Qwen model IDs only")
        if settings.agent_llm_mode == "hosted" and (
            urlsplit(base).scheme != "https"
            or not (
                urlsplit(base).hostname == "router.huggingface.co"
                or (urlsplit(base).hostname or "").endswith(".endpoints.huggingface.cloud")
            )
        ):
            raise InferenceError("Hosted mode requires the Hugging Face HTTPS inference router")
        token = settings.hf_token.get_secret_value()
        if not token and settings.hf_tokens.get_secret_value():
            token = settings.hf_tokens.get_secret_value().split(",")[0].strip()
        if settings.agent_llm_mode == "hosted" and not token:
            raise InferenceError("Configure HF_TOKEN for Hugging Face inference")
        if settings.agent_llm_mode == "local":
            token = ""  # Never send a Hugging Face token to a different local/server endpoint.
        self.client = httpx.AsyncClient(
            base_url=base + "/",
            transport=transport,
            trust_env=False,
            follow_redirects=False,
            timeout=settings.agent_llm_timeout,
            headers={"Authorization": "Bearer " + token} if token else {},
        )

    async def close(self):
        await self.client.aclose()

    @staticmethod
    def parse(content: str) -> AgentAction:
        try:
            # Strict JSON: no extracting code fences, hidden thinking or executable text.
            return AgentAction.model_validate_json(content)
        except (ValidationError, ValueError) as exc:
            raise InvalidAction("Model returned invalid structured action JSON") from exc

    async def generate_action(self, messages: list[dict]) -> AgentAction:
        body = {
            "model": self.settings.agent_model,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": self.settings.agent_max_output_tokens,
        }
        if self.settings.agent_structured_output:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "browser_action",
                    "strict": True,
                    "schema": AgentAction.model_json_schema(),
                },
            }
        for attempt in range(self.settings.agent_llm_retries + 1):
            try:
                async with self.client.stream("POST", "chat/completions", json=body) as response:
                    if response.status_code in (429, 500, 502, 503, 504):
                        raise httpx.TransportError("Transient inference failure")
                    if response.status_code == 402:
                        raise InferenceError(
                            "Inference endpoint returned HTTP 402: inference credits or billing required; configure a funded endpoint or local model server"
                        )
                    if response.status_code != 200:
                        raise InferenceError(
                            f"Inference endpoint returned HTTP {response.status_code}"
                        )
                    raw = bytearray()
                    async for chunk in response.aiter_bytes():
                        raw.extend(chunk)
                        if len(raw) > 65536:
                            raise InferenceError("Inference response exceeded size limit")
                data = json.loads(raw)
                for key in self.usage:
                    amount = data.get("usage", {}).get(key, 0)
                    if isinstance(amount, int) and amount >= 0:
                        self.usage[key] += amount
                choice = data["choices"][0]
                if choice.get("finish_reason") == "length":
                    raise InvalidAction("Model action exceeded the output token limit")
                content = choice["message"].get("content")
                if not isinstance(content, str):
                    raise InvalidAction("Model returned no JSON action")
                return self.parse(content)
            except (httpx.TransportError, TimeoutError):
                self.failures += 1
                if attempt == self.settings.agent_llm_retries:
                    raise InferenceError(
                        "Inference request failed after transient retries"
                    ) from None
                self.retries += 1
                await asyncio.sleep(min(2**attempt, 2))
            except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                raise InvalidAction("Malformed inference response") from None
        raise InferenceError("Inference failed")
