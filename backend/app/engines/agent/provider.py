"""Open-weight Hugging Face chat inference with bounded structured actions."""

import asyncio
import json
from typing import Protocol
from urllib.parse import urlsplit

import httpx
from pydantic import ValidationError

from app.core.config import Settings
from app.engines.agent.actions import AgentAction
from app.engines.agent.contracts import TaskJudgment


class InvalidAction(ValueError):
    """The model returned a syntactically or semantically invalid decision."""


class InferenceError(RuntimeError):
    """The inference service could not provide a usable response."""


class TokenBudgetExceeded(InferenceError):
    """Another inference request would exceed the configured execution budget."""


class _ToolCallingUnsupported(InferenceError):
    """The endpoint explicitly rejected the chat tools capability."""


class LLMProvider(Protocol):
    async def generate_action(self, messages: list[dict]) -> AgentAction: ...
    async def generate_judgment(self, messages: list[dict]) -> TaskJudgment: ...
    async def close(self) -> None: ...


_CANONICAL_TOOLS = {
    "click": ("element_id", "reason"),
    "type_text": ("element_id", "text", "reason"),
    "navigate": ("url", "reason"),
    "scroll": ("direction", "reason"),
    "finish": ("success", "reason"),
    "give_up": ("reason",),
}
_TOOL_SCHEMAS = {
    "click": {"element_id": {"type": "string"}, "reason": {"type": "string"}},
    "type_text": {
        "element_id": {"type": "string"},
        "text": {"type": "string"},
        "reason": {"type": "string"},
    },
    "navigate": {"url": {"type": "string"}, "reason": {"type": "string"}},
    "scroll": {
        "direction": {"type": "string", "enum": ["up", "down"]},
        "reason": {"type": "string"},
    },
    "finish": {
        "success": {"type": "boolean"},
        "reason": {"type": "string"},
    },
    "give_up": {"reason": {"type": "string"}},
}


def action_json_schema() -> dict:
    """JSON-only fallback schema for the same six tools exposed by native calls."""
    return {
        "oneOf": [
            {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "const": name},
                    **properties,
                },
                "required": ["action", *_CANONICAL_TOOLS[name]],
                "additionalProperties": False,
            }
            for name, properties in _TOOL_SCHEMAS.items()
        ]
    }


class HuggingFaceProvider:
    def __init__(self, settings: Settings, transport=None):
        self.settings = settings
        self.usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        self.failures = 0
        self.retries = 0
        model = settings.agent_model
        if (
            not isinstance(model, str)
            or not model
            or model != model.strip()
            or len(model) > 200
            or any(char.isspace() or ord(char) < 32 for char in model)
        ):
            raise InferenceError("Configure a nonempty Hugging Face model identifier")
        base = settings.agent_llm_base_url.rstrip("/")
        parsed = urlsplit(base)
        if parsed.query or parsed.fragment or not parsed.hostname or "\\" in parsed.path:
            raise InferenceError("Inference endpoint URL is invalid")
        path_parts = parsed.path.split("/")
        if any(part in {".", ".."} for part in path_parts):
            raise InferenceError("Inference endpoint URL path is invalid")
        if settings.agent_llm_mode == "hosted" and not self._allowed_hf_host(parsed):
            raise InferenceError("Hosted mode requires an allowed Hugging Face HTTPS endpoint")
        if settings.agent_llm_mode == "hosted" and parsed.path not in ("", "/", "/v1", "/v1/"):
            raise InferenceError("Hosted inference endpoint path is not allowed")
        token = settings.hf_token.get_secret_value()
        if not token and settings.hf_tokens.get_secret_value():
            token = settings.hf_tokens.get_secret_value().split(",")[0].strip()
        if settings.agent_llm_mode == "hosted" and not token:
            raise InferenceError("Configure HF_TOKEN for Hugging Face inference")
        if settings.agent_llm_mode == "local":
            token = ""
        self.client = httpx.AsyncClient(
            base_url=base + "/",
            transport=transport,
            trust_env=False,
            follow_redirects=False,
            timeout=settings.agent_llm_timeout,
            headers={"Authorization": "Bearer " + token} if token else {},
        )

    @staticmethod
    def _allowed_hf_host(parsed) -> bool:
        host = (parsed.hostname or "").lower()
        try:
            return (
                parsed.scheme == "https"
                and parsed.username is None
                and parsed.password is None
                and parsed.port in (None, 443)
                and (
                    host == "router.huggingface.co" or host.endswith(".endpoints.huggingface.cloud")
                )
            )
        except ValueError:
            return False

    @property
    def estimated_cost_usd(self) -> float | None:
        input_rate = self.settings.agent_input_cost_per_million
        output_rate = self.settings.agent_output_cost_per_million
        if input_rate is None and output_rate is None:
            return None
        return (
            self.usage["prompt_tokens"] * (input_rate or 0)
            + self.usage["completion_tokens"] * (output_rate or 0)
        ) / 1_000_000

    async def close(self):
        await self.client.aclose()

    @staticmethod
    def parse(content: str) -> AgentAction:
        """Parse stored/legacy action JSON; runtime requests use canonical schema validation."""
        try:
            return AgentAction.model_validate_json(content)
        except (ValidationError, ValueError) as exc:
            raise InvalidAction("Model returned invalid structured action JSON") from exc

    @staticmethod
    def _canonical_action(name: str, arguments: dict) -> AgentAction:
        if (
            not isinstance(name, str)
            or name not in _CANONICAL_TOOLS
            or not isinstance(arguments, dict)
        ):
            raise InvalidAction("Model selected an unsupported action")
        required = set(_CANONICAL_TOOLS[name])
        if set(arguments) != required:
            raise InvalidAction("Model returned noncanonical action arguments")
        if not isinstance(arguments.get("reason"), str) or not arguments["reason"].strip():
            raise InvalidAction("Action requires a brief reason")
        if name == "finish" and type(arguments["success"]) is not bool:
            raise InvalidAction("Finish success must be a boolean")
        for key, value in arguments.items():
            if key != "success" and not isinstance(value, str):
                raise InvalidAction("Action arguments must use canonical string types")
        try:
            return AgentAction.model_validate({"action": name, **arguments})
        except ValidationError as exc:
            raise InvalidAction("Model returned invalid action arguments") from exc

    def _reserve_budget(self, request_body: dict) -> int:
        # One token per UTF-8 byte is conservative for byte-fallback tokenizers and
        # avoids undercounting multibyte observations. Exact provider usage replaces
        # estimates after a successful response.
        serialized = json.dumps(request_body, ensure_ascii=False, separators=(",", ":"))
        estimate = len(serialized.encode("utf-8")) + 64
        max_output = request_body["max_tokens"]
        if self.usage["total_tokens"] + estimate + max_output > self.settings.agent_token_budget:
            raise TokenBudgetExceeded("Agent inference token budget would be exceeded")
        return estimate

    @staticmethod
    def _tools() -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": f"Perform the bounded {name} browser action.",
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": list(_CANONICAL_TOOLS[name]),
                        "additionalProperties": False,
                    },
                },
            }
            for name, properties in _TOOL_SCHEMAS.items()
        ]

    async def _request(self, body: dict) -> dict:
        retries = min(self.settings.agent_llm_retries, 2)
        for attempt in range(retries + 1):
            try:
                async with self.client.stream("POST", "chat/completions", json=body) as response:
                    status = response.status_code
                    if status == 429 or 500 <= status <= 599:
                        raise httpx.TransportError("Transient inference response")
                    if status in (400, 422):
                        error_body = bytearray()
                        async for chunk in response.aiter_bytes():
                            error_body.extend(chunk)
                            if len(error_body) > 4096:
                                break
                        reason = error_body.decode("utf-8", errors="ignore").lower()
                        unsupported = any(
                            marker in reason
                            for marker in (
                                "tool_choice",
                                "tool calling",
                                "tool calls",
                                "function calling",
                                "unsupported tool",
                                "tools are not supported",
                                "does not support tools",
                                "not support tool",
                                "unknown parameter: tools",
                                "unrecognized parameter: tools",
                            )
                        )
                        if unsupported:
                            raise _ToolCallingUnsupported("Endpoint does not support chat tools")
                        self.failures += 1
                        raise InferenceError(f"Inference endpoint returned HTTP {status}")
                    if status != 200:
                        self.failures += 1
                        raise InferenceError(f"Inference endpoint returned HTTP {status}")
                    raw = bytearray()
                    async for chunk in response.aiter_bytes():
                        raw.extend(chunk)
                        if len(raw) > 65536:
                            self.failures += 1
                            raise InferenceError("Inference response exceeded size limit")
                try:
                    data = json.loads(raw)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    raise InvalidAction("Malformed inference response") from None
                if not isinstance(data, dict):
                    raise InvalidAction("Malformed inference response")
                self._record_usage(data, body, raw)
                return data
            except (httpx.TimeoutException, httpx.TransportError, TimeoutError):
                self.failures += 1
                if attempt == retries:
                    raise InferenceError(
                        "Inference request failed after transient retries"
                    ) from None
                self.retries += 1
                await asyncio.sleep(min(2**attempt, 2))
        raise InferenceError("Inference failed")

    def _record_usage(self, data: dict, request_body: dict, response: bytes) -> None:
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        prompt = usage.get("prompt_tokens")
        completion = usage.get("completion_tokens")
        if not isinstance(prompt, int) or prompt < 0:
            prompt = len(json.dumps(request_body, ensure_ascii=False).encode("utf-8")) + 64
        if not isinstance(completion, int) or completion < 0:
            completion = len(response) + 32
        self.usage["prompt_tokens"] += prompt
        self.usage["completion_tokens"] += completion
        total = usage.get("total_tokens")
        self.usage["total_tokens"] += (
            max(total, prompt + completion)
            if isinstance(total, int) and total >= 0
            else prompt + completion
        )

    @staticmethod
    def _choice(data: dict) -> tuple[dict, str | None]:
        try:
            choices = data["choices"]
            choice = choices[0]
            message = choice["message"]
            if not isinstance(message, dict):
                raise TypeError
            if choice.get("finish_reason") == "length":
                raise InvalidAction("Model output exceeded the output token limit")
            return message, choice.get("finish_reason")
        except InvalidAction:
            raise
        except (KeyError, IndexError, TypeError):
            raise InvalidAction("Malformed inference response") from None

    async def _json_generation(self, messages: list[dict], kind: str):
        model_schema = (
            action_json_schema() if kind == "action" else TaskJudgment.model_json_schema()
        )
        body = {
            "model": self.settings.agent_model,
            "messages": messages,
            "temperature": 0,
            "max_tokens": self.settings.agent_max_output_tokens,
        }
        instruction = (
            "JSON-only generation is required because native tool calls are unavailable. "
            "Follow the existing system instructions and return exactly one JSON object "
            "matching this schema: "
            if kind == "action"
            else "Return only one JSON object matching this schema: "
        )
        body["messages"] = [
            {
                "role": "system",
                "content": instruction + json.dumps(model_schema),
            },
            *messages,
        ]
        self._reserve_budget(body)
        data = await self._request(body)
        message, _ = self._choice(data)
        content = message.get("content")
        if not isinstance(content, str):
            raise InvalidAction("Model returned no JSON decision")
        try:
            value = json.loads(content)
        except json.JSONDecodeError:
            raise InvalidAction("Model returned invalid JSON") from None
        if kind == "action":
            if not isinstance(value, dict) or "action" not in value:
                raise InvalidAction("Model returned no action")
            name = value.pop("action")
            return self._canonical_action(name, value)
        try:
            if (
                not isinstance(value, dict)
                or set(value) != {"success", "reason"}
                or (value["success"] is not None and type(value["success"]) is not bool)
                or not isinstance(value["reason"], str)
            ):
                raise InvalidAction("Task judgment must use canonical types and fields")
            return TaskJudgment.model_validate(value)
        except ValidationError as exc:
            raise InvalidAction("Model returned invalid task judgment") from exc

    async def generate_action(self, messages: list[dict]) -> AgentAction:
        body = {
            "model": self.settings.agent_model,
            "messages": messages,
            "temperature": 0,
            "max_tokens": self.settings.agent_max_output_tokens,
            "tools": self._tools(),
            "tool_choice": "required",
        }
        self._reserve_budget(body)
        try:
            data = await self._request(body)
        except _ToolCallingUnsupported:
            return await self._json_generation(messages, "action")
        message, _ = self._choice(data)
        tool_calls = message.get("tool_calls")
        if not isinstance(tool_calls, list):
            # Some compatible servers silently ignore tools and return content instead.
            if isinstance(message.get("content"), str):
                return await self._json_generation(messages, "action")
            raise InvalidAction("Model returned no tool action")
        if len(tool_calls) != 1:
            raise InvalidAction("Model must return exactly one tool action")
        try:
            call = tool_calls[0]
            function = call["function"]
            name = function["name"]
            arguments = json.loads(function["arguments"])
        except (KeyError, TypeError, json.JSONDecodeError):
            raise InvalidAction("Malformed tool action") from None
        return self._canonical_action(name, arguments)

    async def generate_judgment(self, messages: list[dict]) -> TaskJudgment:
        return await self._json_generation(messages, "judgment")
