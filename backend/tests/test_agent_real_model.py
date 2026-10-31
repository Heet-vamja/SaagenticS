"""Opt-in real HF model + real Chromium. Never substituted with a mock LLM."""

import asyncio
import os

import pytest
from agent_fixtures import fixture_transport

from app.core.config import get_settings
from app.engines.agent.actions import TASKS
from app.engines.agent.browser import BrowserSession
from app.engines.agent.provider import HuggingFaceProvider
from app.engines.agent.runner import AgentRunner


@pytest.mark.skipif(
    os.environ.get("RUN_REAL_HF_TEST") != "1",
    reason="REAL MODEL UNVERIFIED: set RUN_REAL_HF_TEST=1 and configure inference",
)
@pytest.mark.parametrize("task_type", list(TASKS))
def test_real_hugging_face_agent_on_local_fixture(task_type, tmp_path):
    async def scenario():
        settings = get_settings().model_copy(update={"agent_screenshot_dir": str(tmp_path)})
        browser = BrowserSession(
            "https://fixture.example/", [], settings, "real", fixture_transport()
        )
        provider = HuggingFaceProvider(settings)
        runner = AgentRunner(browser, provider, settings)
        rows = []
        result = await runner.run(TASKS[task_type], "https://fixture.example/", rows.append)
        assert result["status"] == "COMPLETED"
        assert len(rows) >= 3, "Real model must navigate and inspect the goal page"
        assert any(row["action_type"] in ("click", "navigate") for row in rows[1:])
        expected = {
            "FIND_PRICING": "/plans.html",
            "FIND_DOCUMENTATION": "/guide.html",
            "FIND_SIGNUP_FORM": "/join.html",
        }
        assert runner.final_url.endswith(expected[task_type])
        if task_type == "FIND_PRICING":
            assert "12" in result["outcome"] and "39" in result["outcome"]
        if task_type == "FIND_SIGNUP_FORM":
            assert "email" in result["outcome"].lower() and "company" in result["outcome"].lower()
        print(
            f"REAL MODEL USED: {settings.agent_model}; task={task_type}; steps={len(rows)}; outcome independently unverified"
        )

    asyncio.run(scenario())
