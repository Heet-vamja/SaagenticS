import asyncio
import json

import httpx
import pytest

from app.core.config import Settings
from app.engines.agent.provider import (
    HuggingFaceProvider,
    InferenceError,
    InvalidAction,
    TokenBudgetExceeded,
)


def _tool(name="click", arguments=None):
    arguments = arguments or {"element_id": "el:1", "reason": "Open pricing"}
    return {
        "choices": [
            {
                "message": {
                    "tool_calls": [
                        {
                            "type": "function",
                            "function": {"name": name, "arguments": json.dumps(arguments)},
                        }
                    ]
                }
            }
        ],
        "usage": {"prompt_tokens": 12, "completion_tokens": 4},
    }


def test_native_tool_action_is_canonical_and_requires_one_call():
    async def scenario():
        bodies = []

        def handler(request):
            body = json.loads(request.content)
            bodies.append(body)
            return httpx.Response(200, json=_tool())

        provider = HuggingFaceProvider(Settings(hf_token="secret"), httpx.MockTransport(handler))
        action = await provider.generate_action([{"role": "user", "content": "Find pricing"}])
        assert action.action == "click" and action.element_id == "el:1"
        assert [tool["function"]["name"] for tool in bodies[0]["tools"]] == [
            "click",
            "type_text",
            "navigate",
            "scroll",
            "finish",
            "give_up",
        ]
        assert bodies[0]["tool_choice"] == "required" and bodies[0]["temperature"] == 0
        await provider.close()

    asyncio.run(scenario())


@pytest.mark.parametrize("calls", [[], [_tool()["choices"][0]["message"]["tool_calls"][0]] * 2])
def test_missing_or_multiple_tool_calls_are_invalid(calls):
    async def scenario():
        provider = HuggingFaceProvider(
            Settings(hf_token="secret"),
            httpx.MockTransport(
                lambda _: httpx.Response(
                    200, json={"choices": [{"message": {"tool_calls": calls}}]}
                )
            ),
        )
        with pytest.raises(InvalidAction):
            await provider.generate_action([])
        await provider.close()

    asyncio.run(scenario())


def test_invalid_tool_arguments_and_content_shape_json_fallback():
    async def scenario():
        bodies = []

        def handler(request):
            body = json.loads(request.content)
            bodies.append(body)
            if len(bodies) == 1:
                return httpx.Response(
                    200, json={"choices": [{"message": {"content": "tools unsupported"}}]}
                )
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": '{"action":"finish","success":true,"reason":"The page shows the goal"}'
                            }
                        }
                    ]
                },
            )

        provider = HuggingFaceProvider(Settings(hf_token="secret"), httpx.MockTransport(handler))
        action = await provider.generate_action([])
        assert action.action == "finish" and action.success is True
        assert "tools" not in bodies[1]
        await provider.close()

        bad = HuggingFaceProvider(
            Settings(hf_token="secret"),
            httpx.MockTransport(
                lambda _: httpx.Response(
                    200, json=_tool("click", {"element_id": "x", "reason": "ok", "extra": 1})
                )
            ),
        )
        with pytest.raises(InvalidAction):
            await bad.generate_action([])
        await bad.close()

    asyncio.run(scenario())


@pytest.mark.parametrize("success", ["yes", "false", 1, 0])
def test_finish_success_requires_a_real_boolean(success):
    async def scenario():
        provider = HuggingFaceProvider(
            Settings(hf_token="secret"),
            httpx.MockTransport(
                lambda _: httpx.Response(
                    200,
                    json=_tool("finish", {"success": success, "reason": "Observed result"}),
                )
            ),
        )
        with pytest.raises(InvalidAction):
            await provider.generate_action([])
        await provider.close()

    asyncio.run(scenario())


def test_unsupported_status_falls_back_but_auth_and_billing_fail_fatally():
    async def scenario():
        calls = []

        def unsupported(request):
            calls.append(json.loads(request.content))
            if len(calls) == 1:
                return httpx.Response(422, json={"error": "tools are not supported"})
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {"message": {"content": '{"action":"give_up","reason":"No relevant page"}'}}
                    ]
                },
            )

        provider = HuggingFaceProvider(
            Settings(hf_token="secret"), httpx.MockTransport(unsupported)
        )
        assert (await provider.generate_action([])).action == "give_up"
        assert len(calls) == 2
        await provider.close()

        for status in (401, 402):
            fatal = HuggingFaceProvider(
                Settings(hf_token="secret"),
                httpx.MockTransport(lambda _, s=status: httpx.Response(s)),
            )
            with pytest.raises(InferenceError, match=f"HTTP {status}"):
                await fatal.generate_action([])
            await fatal.close()

        bad_request = HuggingFaceProvider(
            Settings(hf_token="secret"),
            httpx.MockTransport(lambda _: httpx.Response(400, json={"error": "invalid model"})),
        )
        with pytest.raises(InferenceError, match="HTTP 400"):
            await bad_request.generate_action([])
        await bad_request.close()

    asyncio.run(scenario())


def test_usage_estimates_cost_and_budget_prevents_request():
    async def scenario():
        requests = []

        def handler(request):
            requests.append(request)
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
                                            "name": "give_up",
                                            "arguments": '{"reason":"No relevant page"}',
                                        },
                                    }
                                ]
                            }
                        }
                    ]
                },
            )

        settings = Settings(
            hf_token="secret", agent_input_cost_per_million=1, agent_output_cost_per_million=2
        )
        provider = HuggingFaceProvider(settings, httpx.MockTransport(handler))
        await provider.generate_action([{"role": "user", "content": "Find something"}])
        assert provider.usage["prompt_tokens"] > 0 and provider.usage["completion_tokens"] > 0
        assert (
            provider.usage["total_tokens"]
            >= provider.usage["prompt_tokens"] + provider.usage["completion_tokens"]
        )
        assert provider.estimated_cost_usd > 0
        await provider.close()

        bounded = HuggingFaceProvider(
            Settings(hf_token="secret", agent_token_budget=1000, agent_max_output_tokens=1000),
            httpx.MockTransport(handler),
        )
        with pytest.raises(TokenBudgetExceeded):
            await bounded.generate_action([])
        assert not requests or len(requests) == 1
        await bounded.close()

    asyncio.run(scenario())


def test_judgment_and_host_token_endpoint_safety():
    async def scenario():
        seen = []

        def handler(request):
            seen.append(request)
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": '{"success":false,"reason":"No pricing content was observed"}'
                            }
                        }
                    ]
                },
            )

        provider = HuggingFaceProvider(Settings(hf_token="secret"), httpx.MockTransport(handler))
        judgment = await provider.generate_judgment([{"role": "user", "content": "Judge"}])
        assert judgment.success is False
        assert seen[0].headers["authorization"] == "Bearer secret"
        await provider.close()

        local = HuggingFaceProvider(
            Settings(
                agent_llm_mode="local",
                agent_llm_base_url="http://localhost:1234/v1",
                hf_token="secret",
            ),
            httpx.MockTransport(lambda request: httpx.Response(402)),
        )
        assert "authorization" not in local.client.headers
        await local.close()

    asyncio.run(scenario())
    for base in (
        "http://router.huggingface.co/v1",
        "https://router.huggingface.co.evil.test/v1",
        "https://router.huggingface.co:9443/v1",
    ):
        with pytest.raises(InferenceError):
            HuggingFaceProvider(Settings(agent_llm_base_url=base, hf_token="secret"))


def test_judgment_rejects_coercion_and_extra_fields():
    async def scenario(content):
        provider = HuggingFaceProvider(
            Settings(hf_token="secret"),
            httpx.MockTransport(
                lambda _: httpx.Response(200, json={"choices": [{"message": {"content": content}}]})
            ),
        )
        with pytest.raises(InvalidAction):
            await provider.generate_judgment([])
        await provider.close()

    asyncio.run(scenario('{"success":"yes","reason":"Looks good"}'))
    asyncio.run(scenario('{"success":true,"reason":"Looks good","extra":1}'))


def test_utf8_budget_and_missing_usage_estimates_are_conservative():
    async def scenario():
        body_sizes = []

        def handler(request):
            body_sizes.append(len(request.content))
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
                                            "name": "give_up",
                                            "arguments": '{"reason":"No relevant page"}',
                                        },
                                    }
                                ]
                            }
                        }
                    ]
                },
            )

        provider = HuggingFaceProvider(
            Settings(hf_token="secret", agent_token_budget=1000, agent_max_output_tokens=100),
            httpx.MockTransport(handler),
        )
        with pytest.raises(TokenBudgetExceeded):
            await provider.generate_action([{"role": "user", "content": "🙂" * 300}])
        assert not body_sizes
        await provider.close()

        estimated = HuggingFaceProvider(Settings(hf_token="secret"), httpx.MockTransport(handler))
        await estimated.generate_action([{"role": "user", "content": "🙂"}])
        assert estimated.usage["prompt_tokens"] >= body_sizes[0]
        await estimated.close()

    asyncio.run(scenario())


def test_model_and_base_url_configuration_are_bounded():
    for model in ("", "  ", "model with spaces", "x" * 201):
        with pytest.raises(InferenceError):
            HuggingFaceProvider(Settings(agent_model=model, hf_token="secret"))
    for base in (
        "https://router.huggingface.co/v1?token=bad",
        "https://router.huggingface.co/v1#fragment",
        "https://router.huggingface.co/anything/deep",
    ):
        with pytest.raises(InferenceError):
            HuggingFaceProvider(Settings(agent_llm_base_url=base, hf_token="secret"))


def test_transient_retries_are_bounded_and_counted():
    async def scenario():
        calls = []

        def handler(request):
            calls.append(request)
            return httpx.Response(503)

        provider = HuggingFaceProvider(
            Settings(hf_token="secret", agent_llm_retries=2), httpx.MockTransport(handler)
        )
        with pytest.raises(InferenceError):
            await provider.generate_action([])
        assert len(calls) == 3 and provider.retries == 2 and provider.failures == 3
        await provider.close()

    asyncio.run(scenario())
