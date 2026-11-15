from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import ClassVar
from uuid import UUID, uuid4

import pytest
from agent_fixtures import fixture_transport

from app.core.config import Settings
from app.engines.agent.actions import AgentAction
from app.engines.agent.browser import BrowserSession
from app.models.domain import Scan, ScanStatus, WorkflowStatus, WorkflowTest
from app.repositories.agent_tests import AgentRecords
from app.services.agents import execute_agent_task
from app.services.crawls import finalize_interrupted_agent_scan


@pytest.mark.parametrize("task_type", ["FIND_PRICING", "FIND_CONTACT", "FIND_SIGNUP_FORM"])
def test_agent_api_persistence_trace_and_rule_verified_completion(
    client, session, monkeypatch, tmp_path, task_type
):
    project = client.post(
        "/api/v1/projects",
        json={"name": "Browser fixture", "website_url": "https://fixture.example"},
    ).json()
    scan = client.post(f"/api/v1/projects/{project['id']}/scans").json()
    scan_record = session.get(Scan, UUID(scan["id"]))
    scan_record.status = ScanStatus.COMPLETED
    session.commit()
    response = client.post(
        f"/api/v1/scans/{scan['id']}/agent-tasks",
        json={"task_type": task_type, "runs": 1},
    )
    assert response.status_code == 201
    task = response.json()
    assert task["status"] == "PENDING"

    @contextmanager
    def factory():
        yield session

    settings = Settings(agent_screenshot_dir=str(tmp_path))
    monkeypatch.setattr("app.services.agents.get_settings", lambda: settings)
    monkeypatch.setattr("app.api.agent_routes.get_settings", lambda: settings)

    class DynamicMock:
        # The mock chooses from observation labels, never site selectors or routes.
        usage: ClassVar[dict] = {"total_tokens": 10}

        async def generate_action(self, messages):
            import json

            observation = json.loads(messages[-1]["content"])["untrusted_latest_observation"]
            target = {
                "FIND_PRICING": "plans and costs",
                "FIND_CONTACT": "contact our team",
                "FIND_SIGNUP_FORM": "try northstar",
            }[task_type]
            import re

            elements = re.findall(
                r"^\[([^]]+)\] link \| ([^|]*) \| (.*)$",
                observation["interactive_text"],
                re.MULTILINE,
            )
            link = next((item for item in elements if target in item[1].lower()), None)
            if link:
                return AgentAction(
                    action="click",
                    element_id=link[0],
                    reason="Open the page linked for the requested task",
                )
            return AgentAction(
                action="finish",
                success=True,
                reason="The task destination is open for independent page verification",
            )

        async def close(self):
            pass

    execute_agent_task(
        UUID(task["id"]),
        factory,
        lambda url, domains, config, identifier: BrowserSession(
            url, domains, config, identifier, fixture_transport()
        ),
        lambda config: DynamicMock(),
    )
    session.expire_all()
    task_result = client.get(f"/api/v1/agent-tasks/{task['id']}").json()
    assert task_result["status"] == "COMPLETED"
    assert task_result["outcome"] == "SUCCEEDED"
    assert task_result["eligible_runs"] == 1
    run = client.get(f"/api/v1/agent-tasks/{task['id']}/runs").json()[0]
    result = client.get(f"/api/v1/agent-tests/{run['id']}").json()
    assert result["status"] == "COMPLETED"
    assert result["task_type"] == task_type
    assert result["verification_method"] == "rules"
    assert result["verification"] == "RULE_VERIFIED"
    assert result["outcome"] == "SUCCEEDED"
    assert result["steps_completed"] == 2
    test_id = UUID(result["id"])
    assert result["execution_duration"] > 0
    assert result["final_url"].endswith(
        {
            "FIND_PRICING": "/plans.html",
            "FIND_CONTACT": "/contact.html",
            "FIND_SIGNUP_FORM": "/join.html",
        }[task_type]
    )
    trace = client.get(f"/api/v1/agent-tests/{test_id}/steps").json()
    assert [s["action_type"] for s in trace] == ["navigate", "click"]
    assert "screenshot_path" not in trace[1]
    screenshot = client.get(f"/api/v1/agent-tests/{test_id}/steps/{trace[1]['id']}/screenshot")
    assert screenshot.status_code == 200
    assert screenshot.headers["content-type"] == "image/png"
    assert len(client.get(f"/api/v1/agent-tests/{test_id}/steps?limit=1&offset=1").json()) == 1
    assert len(client.get(f"/api/v1/scans/{scan['id']}/agent-tasks").json()) == 1
    assert client.get(f"/api/v1/agent-tests/{uuid4()}").status_code == 404
    assert (
        client.post(
            f"/api/v1/scans/{scan['id']}/agent-tests", json={"task_type": "ARBITRARY"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/api/v1/scans/{scan['id']}/agent-tests",
            json={"task_type": "FIND_PRICING", "allowed_domains": ["127.0.0.1"]},
        ).status_code
        == 422
    )
    execute_agent_task(UUID(task["id"]), factory, lambda *args: None, lambda *args: None)
    assert len(AgentRecords(session).steps(test_id, 100, 0)) == 2


def test_agent_failure_and_expired_execution_recovery(client, session, monkeypatch):
    project = client.post(
        "/api/v1/projects", json={"name": "Failure", "website_url": "https://fixture.example"}
    ).json()
    scan = client.post(f"/api/v1/projects/{project['id']}/scans").json()
    scan_record = session.get(Scan, UUID(scan["id"]))
    scan_record.status = ScanStatus.COMPLETED
    session.commit()
    task = client.post(
        f"/api/v1/scans/{scan['id']}/agent-tasks",
        json={"task_type": "FIND_CONTACT", "runs": 1},
    ).json()

    @contextmanager
    def factory():
        yield session

    def unavailable(settings):
        raise RuntimeError("Configure an inference endpoint")

    execute_agent_task(UUID(task["id"]), factory, provider_factory=unavailable)
    session.expire_all()
    run = AgentRecords(session).runs(UUID(task["id"]), 1, 0)[0]
    result = AgentRecords(session).test(run.id)
    assert result.status == WorkflowStatus.FAILED
    assert result.completed_at and result.failure_reason
    result.status = WorkflowStatus.RUNNING
    result.execution_deadline = datetime.now(UTC) - timedelta(seconds=1)
    session.commit()
    AgentRecords(session).expire()
    session.commit()
    session.expire_all()
    assert result.status == WorkflowStatus.FAILED


def test_interrupted_agent_stage_recovers_to_completed_static_scan(client, session):
    project = client.post(
        "/api/v1/projects", json={"name": "Recovery", "website_url": "https://fixture.example"}
    ).json()
    scan_response = client.post(f"/api/v1/projects/{project['id']}/scans")
    scan = session.get(Scan, UUID(scan_response.json()["id"]))
    scan.status = ScanStatus.COMPLETED
    session.commit()
    task = client.post(
        f"/api/v1/scans/{scan.id}/agent-tasks",
        json={"task_type": "FIND_CONTACT", "runs": 1},
    ).json()
    parent = AgentRecords(session).task(UUID(task["id"]))
    run = AgentRecords(session).runs(parent.id, 1, 0)[0]
    expired_at = datetime.now(UTC) - timedelta(seconds=1)
    scan.status = ScanStatus.RUNNING
    scan.started_at = expired_at
    scan.audit_summary = {"phase": "AGENT_TASKS", "static_score": 72.0}
    parent.status = ScanStatus.RUNNING
    parent.deadline = expired_at
    run.status = WorkflowStatus.RUNNING
    run.execution_deadline = expired_at
    session.commit()

    from app.repositories.agent_tests import AgentRecords as TaskRecords

    TaskRecords(session).expire()
    assert finalize_interrupted_agent_scan(session, scan.id)
    session.commit()
    session.refresh(scan)
    assert scan.status == ScanStatus.COMPLETED
    assert scan.audit_summary["phase"] == "COMPLETED"
    assert scan.audit_summary["static_score"] == 72.0
    assert scan.audit_summary["agent_stage"]["status"] == "UNAVAILABLE"
    assert scan.audit_summary["agent"]["provisional"] is True


def test_scan_pipeline_crawls_then_runs_three_rule_checked_tasks(
    client, session, monkeypatch, tmp_path
):
    import json
    import re

    from app.engines.crawling.crawler import WebsiteCrawler
    from app.engines.crawling.transport import Fetcher
    from app.engines.crawling.urls import URLValidator
    from app.services.crawls import execute_scan

    @contextmanager
    def factory():
        yield session

    settings = Settings(
        database_url="postgresql+psycopg://agentreadiness:local-development-only@localhost:5432/agentreadiness_test",
        audit_browser_enabled=False,
        agent_pipeline_enabled=True,
        # The customer release skips the agent stage; these tests cover internal mode.
        customer_mode_enabled=False,
        agent_free_limits_enabled=False,
        agent_runs_per_task=1,
        agent_duration=30,
        agent_stage_duration=120,
        agent_action_delay=1,
        scan_duration=60,
        agent_screenshot_dir=str(tmp_path),
    )
    for module in (
        "app.api.routes",
        "app.services.audits",
        "app.services.crawls",
        "app.services.agents",
    ):
        monkeypatch.setattr(f"{module}.get_settings", lambda: settings)

    class DynamicMock:
        usage: ClassVar[dict] = {"total_tokens": 12, "prompt_tokens": 8, "completion_tokens": 4}

        async def generate_action(self, messages):
            observation = json.loads(messages[-1]["content"])["untrusted_latest_observation"]
            goal = messages[1]["content"].lower()
            keyword = (
                "contact our team"
                if "contact" in goal
                else "try northstar"
                if "sign-up" in goal or "signup" in goal or "reach signup" in goal
                else "plans and costs"
            )
            links = re.findall(
                r"^\[([^]]+)\] link \| ([^|]*) \| (.*)$",
                observation["interactive_text"],
                re.MULTILINE,
            )
            link = next((row for row in links if keyword in row[1].lower()), None)
            if link:
                return AgentAction(
                    action="click",
                    element_id=link[0],
                    reason="Open the navigation item for the requested website task",
                )
            return AgentAction(
                action="give_up",
                reason="The task destination is not available in the current navigation",
            )

        async def close(self):
            pass

    def crawler_factory(url, config):
        return WebsiteCrawler(url, config, Fetcher(URLValidator(url), config, fixture_transport()))

    def browser_factory(url, domains, config, identifier):
        return BrowserSession(url, domains, config, identifier, fixture_transport())

    project = client.post(
        "/api/v1/projects",
        json={"name": "Full pipeline fixture", "website_url": "https://fixture.example"},
    ).json()
    scan = client.post(f"/api/v1/projects/{project['id']}/scans").json()
    execute_scan(
        UUID(scan["id"]),
        factory,
        crawler_factory,
        browser_factory,
        lambda config: DynamicMock(),
    )
    session.expire_all()
    completed = client.get(f"/api/v1/scans/{scan['id']}").json()
    assert completed["status"] == "COMPLETED"
    assert completed["pages_crawled"] >= 4
    assert completed["audit_summary"]["phase"] == "COMPLETED"
    assert completed["audit_summary"]["score_kind"] == "COMBINED_READINESS"
    persisted_runs = [
        run for run in session.query(WorkflowTest).all() if run.scan_id == UUID(scan["id"])
    ]
    pricing = next(run for run in persisted_runs if run.task_type == "FIND_PRICING")
    assert pricing.outcome == "SUCCEEDED", (pricing.failure_reason, pricing.verification_evidence)
    assert completed["audit_summary"]["agent"]["agent_score"] == 100
    assert completed["overall_score"] is not None
    task_rows = client.get(f"/api/v1/scans/{scan['id']}/agent-tasks").json()
    assert {task["task_type"] for task in task_rows} == {
        "FIND_PRICING",
        "FIND_CONTACT",
        "FIND_SIGNUP_FORM",
    }
    assert all(task["outcome"] == "SUCCEEDED" for task in task_rows)


def test_agent_inference_failure_keeps_completed_static_scan(client, session, monkeypatch):
    from contextlib import contextmanager

    from app.engines.crawling.crawler import WebsiteCrawler
    from app.engines.crawling.transport import Fetcher
    from app.engines.crawling.urls import URLValidator
    from app.services.crawls import execute_scan

    @contextmanager
    def factory():
        yield session

    settings = Settings(
        audit_browser_enabled=False,
        agent_pipeline_enabled=True,
        # The customer release skips the agent stage; these tests cover internal mode.
        customer_mode_enabled=False,
        agent_free_limits_enabled=True,
        agent_free_task_limit=1,
        agent_free_runs_per_task=1,
        agent_duration=20,
        agent_stage_duration=60,
        scan_duration=60,
    )
    for module in (
        "app.api.routes",
        "app.services.audits",
        "app.services.crawls",
        "app.services.agents",
    ):
        monkeypatch.setattr(f"{module}.get_settings", lambda: settings)

    def crawler_factory(url, config):
        return WebsiteCrawler(url, config, Fetcher(URLValidator(url), config, fixture_transport()))

    def unavailable(_settings):
        raise RuntimeError("inference endpoint unavailable")

    project = client.post(
        "/api/v1/projects",
        json={"name": "Static fallback fixture", "website_url": "https://fixture.example"},
    ).json()
    scan = client.post(f"/api/v1/projects/{project['id']}/scans").json()
    execute_scan(
        UUID(scan["id"]),
        factory,
        crawler_factory,
        lambda *args: pytest.fail("The browser should not start when the provider is unavailable"),
        unavailable,
    )
    session.expire_all()
    completed = client.get(f"/api/v1/scans/{scan['id']}").json()
    assert completed["status"] == "COMPLETED"
    assert completed["audit_summary"]["phase"] == "COMPLETED"
    assert completed["audit_summary"]["score_kind"] == "STATIC_READINESS"
    assert completed["overall_score"] == completed["audit_summary"]["static_score"]
    assert "infrastructure errors" in completed["audit_summary"]["agent"]["fallback_reason"]
    task = client.get(f"/api/v1/scans/{scan['id']}/agent-tasks").json()[0]
    assert task["outcome"] == "UNAVAILABLE"
    run = client.get(f"/api/v1/agent-tasks/{task['id']}/runs").json()[0]
    assert run["failure_category"] == "infra_error"


def test_customer_mode_never_starts_the_agent_stage(client, session, monkeypatch):
    """The customer release is static-only even when the agent pipeline is configured."""
    from contextlib import contextmanager

    from app.engines.crawling.crawler import WebsiteCrawler
    from app.engines.crawling.transport import Fetcher
    from app.engines.crawling.urls import URLValidator
    from app.services.crawls import execute_scan

    @contextmanager
    def factory():
        yield session

    settings = Settings(
        audit_browser_enabled=False,
        agent_pipeline_enabled=True,
        customer_mode_enabled=False,  # Lets the internal API create the scan below.
        scan_duration=60,
    )
    for module in ("app.api.routes", "app.services.audits", "app.services.agents"):
        monkeypatch.setattr(f"{module}.get_settings", lambda: settings)
    project = client.post(
        "/api/v1/projects",
        json={"name": "Customer mode fixture", "website_url": "https://fixture.example"},
    ).json()
    scan = client.post(f"/api/v1/projects/{project['id']}/scans").json()

    customer = settings.model_copy(update={"customer_mode_enabled": True})
    monkeypatch.setattr("app.services.crawls.get_settings", lambda: customer)

    def crawler_factory(url, config):
        return WebsiteCrawler(url, config, Fetcher(URLValidator(url), config, fixture_transport()))

    execute_scan(
        UUID(scan["id"]),
        factory,
        crawler_factory,
        lambda *args: pytest.fail("No agent browser may start in customer mode"),
        lambda *args: pytest.fail("No agent provider may start in customer mode"),
    )
    session.expire_all()
    completed = client.get(f"/api/v1/scans/{scan['id']}").json()
    assert completed["status"] == "COMPLETED"
    assert completed["audit_summary"]["score_kind"] == "STATIC_READINESS"
    assert "agent_stage" not in completed["audit_summary"]
    assert client.get(f"/api/v1/scans/{scan['id']}/agent-tasks").json() == []
