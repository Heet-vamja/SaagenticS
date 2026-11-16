"""Gemini structured output: the schema subset it accepts and the request it receives."""

import asyncio
import json

import httpx
from pydantic import SecretStr

from app.core.config import Settings
from app.engines.agent.provider import GeminiProvider, gemini_response_schema
from app.engines.variants.contracts import Catalog


def test_catalog_schema_is_reduced_to_what_gemini_accepts():
    schema = gemini_response_schema(Catalog.model_json_schema())
    text = json.dumps(schema)
    for rejected in ("$ref", "$defs", "maxItems", "maxLength", "additionalProperties", "anyOf"):
        assert rejected not in text, rejected
    product = schema["properties"]["products"]["items"]
    assert {"slug", "name", "price"} <= set(product["required"])
    assert product["properties"]["category"]["nullable"] is True


def test_gemini_requests_constrained_json_and_still_validates_locally():
    seen = {}
    reply = {
        "store_name": "Northstar Shoes",
        "summary": "Running and walking shoes.",
        "currency": "INR",
        "products": [],
        "policies": [],
        "key_tasks": [],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": json.dumps(reply)}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            },
        )

    settings = Settings(
        agent_llm_provider="gemini",
        agent_model="gemini-3.5-flash-lite",
        agent_llm_base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        gemini_api_key=SecretStr("test-key"),
    )
    provider = GeminiProvider(settings, transport=httpx.MockTransport(handler))

    async def run():
        try:
            return await provider.generate_structured([{"role": "user", "content": "x"}], Catalog)
        finally:
            await provider.close()

    catalog = asyncio.run(run())
    assert catalog.store_name == "Northstar Shoes"
    response_format = seen["body"]["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["name"] == "Catalog"
    assert "maxItems" not in json.dumps(response_format)
