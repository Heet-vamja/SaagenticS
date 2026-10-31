import asyncio
import json

import pytest
from agent_fixtures import fixture_transport

from app.core.config import Settings
from app.engines.agent.actions import AgentAction
from app.engines.agent.browser import BrowserSession
from app.engines.agent.runner import AgentRunner
from app.engines.agent.success import check_success


@pytest.mark.parametrize(
    "task,evidence",
    [
        ("FIND_PRICING", {"pricing_context": True}),
        ("FIND_CONTACT", {"contact_context": True}),
        ("FIND_SIGNUP_FORM", {"signup_context": True}),
        ("FIND_DOCUMENTATION", {"documentation_context": True}),
    ],
)
def test_destination_without_actual_dom_evidence_is_inconclusive(task, evidence):
    assert check_success(task, evidence).success is None


def test_clear_failure_and_js_are_distinct():
    assert check_success("FIND_PRICING", {"challenge": True}).success is False
    assert check_success("FIND_PRICING", {"not_found": True}).success is False
    check = check_success("FIND_PRICING", {"requires_js": True})
    assert check.success is None and check.failure_category == "content_requires_js"


@pytest.mark.parametrize(
    "task,path",
    [
        ("FIND_PRICING", "/plans.html"),
        ("FIND_CONTACT", "/contact.html"),
        ("FIND_SIGNUP_FORM", "/join.html"),
        ("FIND_DOCUMENTATION", "/guide.html"),
    ],
)
def test_real_chromium_mock_llm_rules_and_cleanup(task, path):
    class FixtureModel:
        def __init__(self):
            self.usage = {"prompt_tokens": 30, "completion_tokens": 10, "total_tokens": 40}
            self.closed = False

        async def generate_action(self, messages):
            assert "visible_text" not in messages[-1]["content"]
            return AgentAction(
                action="navigate",
                url="https://fixture.example" + path,
                reason="Inspect destination",
            )

        async def close(self):
            self.closed = True

    async def scenario():
        calls, rows = [], []
        settings = Settings(agent_screenshots=False)
        browser = BrowserSession(
            "https://fixture.example/", [], settings, "rules", fixture_transport(calls)
        )
        provider = FixtureModel()
        result = await AgentRunner(browser, provider, settings).run(
            "Discover requested information",
            "https://fixture.example/",
            rows.append,
            task_type=task,
        )
        assert result.outcome == "SUCCEEDED" and result.verification_method == "rules"
        assert result.steps_completed == 2 and browser.closed and provider.closed
        assert all(method == "GET" for method, _ in calls)
        assert "fixture-private-password" not in json.dumps(result.verification_evidence)
        assert "fixture-secret@example.com" not in json.dumps(result.verification_evidence)
        if task == "FIND_CONTACT":
            assert result.verification_evidence["public_email_count"] >= 1
            assert "hello@" not in json.dumps(result.verification_evidence)

    asyncio.run(scenario())


def test_observation_cap_priority_and_rule_false_positive_protection():
    async def scenario():
        browser = BrowserSession(
            "https://fixture.example/",
            [],
            Settings(agent_screenshots=False, agent_observation_chars=20000),
            "limits",
            fixture_transport(),
        )
        try:
            await browser.start()
            await browser.navigate("https://fixture.example/")
            await browser.page.evaluate("""() => {
                document.title='Ordinary page';
                document.body.innerHTML='<div id="filler"></div><nav><a href="/plans.html">Primary pricing navigation</a></nav><main><input type="text" aria-label="'+ 'A'.repeat(200)+'"></main>';
                const filler=document.getElementById('filler');
                for(let i=0;i<200;i++) {const a=document.createElement('a');a.href='/item'+i;a.textContent='Footer item '+i;filler.appendChild(a);}
            }""")
            observation = await browser.observe()
            assert len(observation["elements"]) == 150
            assert observation["elements"][0]["name"] == "Primary pricing navigation"
            assert all(len(e["name"]) <= 80 for e in observation["elements"])
            assert len(observation["interactive_text"]) <= 20000
            await browser.page.evaluate("""() => {
                document.title='Ordinary page';
                document.body.innerHTML='<nav>Pricing Free trial Contact</nav><p>$12 donation</p><form><input type="search" aria-label="Search"></form><textarea>secret@example.com</textarea>';
            }""")
            evidence = await browser.verification_evidence()
            assert check_success("FIND_PRICING", evidence).success is None
            assert check_success("FIND_SIGNUP_FORM", evidence).success is None
            assert check_success("FIND_CONTACT", evidence).success is None
        finally:
            await browser.close()

    asyncio.run(scenario())
