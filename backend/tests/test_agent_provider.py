import asyncio
import json

import httpx
import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.engines.agent.actions import AgentAction
from app.engines.agent.privacy import redact
from app.engines.agent.provider import HuggingFaceProvider, InferenceError, InvalidAction


def test_structured_actions_and_invalid_json():
    action = HuggingFaceProvider.parse(
        '{"action":"click","element_id":"latest:1","reason":"Open the visible link"}'
    )
    assert action.action == "click"
    for value in [
        "not json",
        "```json\n{}\n```",
        '{"action":"execute_javascript","reason":"evil"}',
        '{"action":"click","reason":"Missing ID"}',
        '{"action":"finish","result":"done","reason":"done","python":"print(1)"}',
    ]:
        with pytest.raises(InvalidAction):
            HuggingFaceProvider.parse(value)
    with pytest.raises(ValidationError):
        AgentAction(action="scroll", direction="left", reason="bad")


def test_provider_calls_configured_open_model_retries_and_usage():
    async def scenario():
        calls = []

        def handler(request):
            calls.append(request)
            if len(calls) == 1:
                return httpx.Response(503)
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "tool_calls": [
                                    {
                                        "type": "function",
                                        "function": {
                                            "name": "finish",
                                            "arguments": '{"success":true,"reason":"Observed the goal"}',
                                        },
                                    }
                                ]
                            }
                        }
                    ],
                    "usage": {"prompt_tokens": 30, "completion_tokens": 10, "total_tokens": 40},
                },
            )

        provider = HuggingFaceProvider(
            Settings(hf_token="test-only", agent_llm_retries=1), httpx.MockTransport(handler)
        )
        action = await provider.generate_action([{"role": "user", "content": "Find pricing"}])
        assert action.action == "finish"
        assert provider.retries == 1
        assert provider.usage == {"prompt_tokens": 30, "completion_tokens": 10, "total_tokens": 40}
        assert json.loads(calls[-1].content)["model"] == "Qwen/Qwen3-4B-Instruct-2507"
        request = json.loads(calls[-1].content)
        assert request["temperature"] == 0
        assert request["tool_choice"] == "required"
        assert provider.client._trust_env is False
        await provider.close()

    asyncio.run(scenario())


def test_credentials_not_sent_to_local_endpoint_and_errors_sanitized():
    async def scenario():
        def handler(request):
            assert "authorization" not in request.headers
            return httpx.Response(402, text="private provider account detail")

        provider = HuggingFaceProvider(
            Settings(
                agent_llm_mode="local",
                agent_llm_base_url="http://localhost:9999/v1",
                hf_token="test-secret",
            ),
            httpx.MockTransport(handler),
        )
        with pytest.raises(InferenceError, match="HTTP 402") as error:
            await provider.generate_action([])
        assert "private" not in str(error.value)
        await provider.close()

    asyncio.run(scenario())
    assert "hf_abc123" not in redact("hf_abc123 user@example.com password=secret")
    assert "user@example.com" not in redact("user@example.com")


def test_retry_budget_and_configurable_model():
    async def scenario():
        calls = []

        def handler(request):
            calls.append(request)
            return httpx.Response(503)

        provider = HuggingFaceProvider(
            Settings(hf_token="test", agent_llm_retries=0), httpx.MockTransport(handler)
        )
        with pytest.raises(InferenceError):
            await provider.generate_action([])
        assert len(calls) == 1
        await provider.close()

    asyncio.run(scenario())
    provider = HuggingFaceProvider(
        Settings(
            agent_model="org/custom-open-model",
            agent_llm_provider="huggingface",
            hf_token="test",
        )
    )
    asyncio.run(provider.close())
