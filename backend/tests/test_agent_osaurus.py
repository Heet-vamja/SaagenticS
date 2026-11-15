"""Osaurus-compatible request, health, validation, and provider selection tests."""

import asyncio
import json

import httpx
import pytest

from app.core.config import Settings
from app.engines.agent.provider import (
    HuggingFaceProvider,
    InferenceError,
    InvalidAction,
    OsaurusProvider,
    get_agent_provider,
)

MODEL = "raptor-0.6-4b-jang_6m"


def test_hugging_face_provider_remains_explicitly_selectable():
    settings = Settings(
        agent_llm_provider="huggingface",
        agent_model="Qwen/Qwen3-4B-Instruct-2507",
        agent_llm_mode="hosted",
        agent_llm_base_url="https://router.huggingface.co/v1",
        hf_token="test-token",
    )
    provider = get_agent_provider(settings)
    assert isinstance(provider, HuggingFaceProvider)
    assert not isinstance(provider, OsaurusProvider)
    asyncio.run(provider.close())


def test_osaurus_openai_tool_call_and_model_health():
    async def scenario():
        requests = []

        def handler(request):
            requests.append(request)
            assert request.headers.get("authorization") == "Bearer local-test-key"
            if request.method == "GET":
                assert request.url.path == "/v1/models"
                return httpx.Response(200, json={"data": [{"id": MODEL}]})
            body = json.loads(request.content)
            assert request.url.path == "/v1/chat/completions"
            assert body["model"] == MODEL
            assert body["tool_choice"] == "required"
            assert body["temperature"] == 1.0
            assert body["top_p"] == 0.95
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "finish_reason": "tool_calls",
                            "message": {
                                "role": "assistant",
                                "content": "",
                                "tool_calls": [
                                    {
                                        "id": "call_1",
                                        "type": "function",
                                        "function": {
                                            "name": "navigate",
                                            "arguments": json.dumps(
                                                {
                                                    "url": "https://fixture.example/plans.html",
                                                    "reason": "Open the pricing link observed on the page",
                                                }
                                            ),
                                        },
                                    }
                                ],
                            },
                        }
                    ],
                    "usage": {"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20},
                },
            )

        settings = Settings(
            agent_llm_provider="osaurus",
            agent_model=MODEL,
            agent_llm_base_url="http://127.0.0.1:1337/v1",
            osaurus_api_key="local-test-key",
        )
        provider = get_agent_provider(settings, httpx.MockTransport(handler))
        assert isinstance(provider, OsaurusProvider)
        health = await provider.health()
        assert health == {
            "provider": "osaurus",
            "model": MODEL,
            "reachable": True,
            "model_available": True,
        }
        action = await provider.generate_action([{"role": "user", "content": "Find pricing"}])
        assert action.action == "navigate"
        assert action.url == "https://fixture.example/plans.html"
        assert len(requests) == 2
        await provider.close()

    asyncio.run(scenario())


def test_osaurus_rejects_invalid_tool_output_and_untrusted_endpoints():
    async def scenario():
        def bad_call(request):
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "tool_calls": [
                                    {
                                        "type": "function",
                                        "function": {"name": "shell_run", "arguments": "{}"},
                                    }
                                ]
                            }
                        }
                    ]
                },
            )

        provider = OsaurusProvider(
            Settings(agent_llm_base_url="http://localhost:1337/v1"),
            httpx.MockTransport(bad_call),
        )
        with pytest.raises(InvalidAction):
            await provider.generate_action([])
        await provider.close()

    asyncio.run(scenario())
    with pytest.raises(InferenceError, match="local HTTP API"):
        OsaurusProvider(Settings(agent_llm_base_url="http://example.com:1337/v1"))


def test_osaurus_health_handles_unavailable_server_and_unknown_model():
    async def scenario():
        provider = OsaurusProvider(
            Settings(agent_llm_base_url="http://localhost:1337/v1"),
            httpx.MockTransport(lambda request: httpx.Response(200, json={"data": []})),
        )
        health = await provider.health()
        assert health["reachable"] is True
        assert health["model_available"] is False
        await provider.close()

        unavailable = OsaurusProvider(
            Settings(agent_llm_base_url="http://localhost:1337/v1"),
            httpx.MockTransport(lambda request: httpx.Response(503)),
        )
        assert (await unavailable.health())["reachable"] is False
        await unavailable.close()

    asyncio.run(scenario())


def test_osaurus_inference_timeout_is_bounded_and_sanitized():
    async def scenario():
        def timeout(request):
            raise httpx.ReadTimeout("local model server did not answer")

        provider = OsaurusProvider(
            Settings(
                agent_llm_base_url="http://localhost:1337/v1",
                agent_llm_retries=0,
            ),
            httpx.MockTransport(timeout),
        )
        with pytest.raises(InferenceError, match="transient retries") as error:
            await provider.generate_action([])
        assert "local model server" not in str(error.value)
        await provider.close()

    asyncio.run(scenario())


def test_local_model_health_endpoint_reports_provider_state(monkeypatch):
    from fastapi.testclient import TestClient

    from app import main

    class Reachable:
        async def health(self):
            return {
                "provider": "osaurus",
                "model": MODEL,
                "reachable": True,
                "model_available": True,
            }

        async def close(self):
            return None

    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: Settings(agent_llm_provider="osaurus", customer_mode_enabled=False),
    )
    monkeypatch.setattr(main, "get_agent_provider", lambda settings: Reachable())
    response = TestClient(main.app).get("/health/llm")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "provider": "osaurus",
        "model": MODEL,
        "reachable": True,
        "model_available": True,
    }
