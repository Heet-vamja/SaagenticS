"""Opt-in Osaurus/Raptor smoke test against local fixture pages; no cloud fallback."""

import asyncio
import os

import pytest
from agent_fixtures import fixture_transport

from app.core.config import get_settings
from app.engines.agent.browser import BrowserSession
from app.engines.agent.provider import OsaurusProvider
from app.engines.agent.runner import AgentRunner


@pytest.mark.skipif(
    os.environ.get("RUN_REAL_OSAURUS_TEST") != "1",
    reason="REAL LOCAL MODEL UNVERIFIED: set RUN_REAL_OSAURUS_TEST=1 with Osaurus running",
)
def test_real_raptor_agent_on_local_fixture(tmp_path):
    async def scenario():
        settings = get_settings().model_copy(
            update={
                "agent_llm_provider": "osaurus",
                "agent_screenshot_dir": str(tmp_path),
            }
        )
        browser = BrowserSession(
            "https://fixture.example/", [], settings, "real-osaurus", fixture_transport()
        )
        provider = OsaurusProvider(settings)
        runner = AgentRunner(browser, provider, settings)
        rows = []
        result = await runner.run(
            "Find the pricing page and report the displayed plan prices without submitting forms.",
            "https://fixture.example/",
            rows.append,
        )
        assert result["status"] == "COMPLETED"
        assert runner.final_url.endswith("/plans.html")
        assert any(row["action_type"] in ("click", "navigate") for row in rows[1:])
        assert "12" in result["outcome"] and "39" in result["outcome"]
        print(
            f"REAL OSaurus model used: {settings.agent_model}; steps={len(rows)}; "
            "agent-declared result only, not independently verified"
        )

    asyncio.run(scenario())
