from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import ClassVar
from uuid import UUID, uuid4

import pytest
from agent_fixtures import fixture_transport

from app.core.config import Settings
from app.engines.agent.actions import AgentAction
from app.engines.agent.browser import BrowserSession
from app.models.domain import WorkflowStatus
from app.repositories.agent_tests import AgentRecords
from app.services.agents import execute_agent_test


@pytest.mark.parametrize("task_type", ["FIND_PRICING", "FIND_DOCUMENTATION", "FIND_SIGNUP_FORM"])
def test_agent_api_persistence_trace_and_unverified_completion(
    client, session, monkeypatch, tmp_path, task_type
):
    project = client.post(
        "/api/v1/projects",
        json={"name": "Browser fixture", "website_url": "https://fixture.example"},
    ).json()
    scan = client.post(f"/api/v1/projects/{project['id']}/scans").json()
    response = client.post(f"/api/v1/scans/{scan['id']}/agent-tests", json={"task_type": task_type})
    assert response.status_code == 201
    test = response.json()
    assert test["status"] == "PENDING"
    assert test["verification"] == "NOT_INDEPENDENTLY_VERIFIED"
    test_id = UUID(test["id"])

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
            completed = {
                "FIND_PRICING": "$12" in observation["visible_text"],
                "FIND_DOCUMENTATION": "Product and developer documentation"
                in observation["visible_text"],
                "FIND_SIGNUP_FORM": any(e.get("required") for e in observation["elements"]),
            }[task_type]
            if completed:
                return AgentAction(
                    action="finish",
                    result={
                        "FIND_PRICING": "Starter $12/month; Team $39/month",
                        "FIND_DOCUMENTATION": "Developer documentation found",
                        "FIND_SIGNUP_FORM": "Required fields: Work email, Password, Company",
                    }[task_type],
                    reason="Requested information is visible",
                )
            keyword = {
                "FIND_PRICING": "costs",
                "FIND_DOCUMENTATION": "guides",
                "FIND_SIGNUP_FORM": "try northstar",
            }[task_type]
            link = next(e for e in observation["elements"] if keyword in e["name"].lower())
            return AgentAction(
                action="click",
                element_id=link["element_id"],
                reason="Inspect the relevant visible link",
            )

        async def close(self):
            pass

    execute_agent_test(
        test_id,
        factory,
        lambda url, domains, config, identifier: BrowserSession(
            url, domains, config, identifier, fixture_transport()
        ),
        lambda config: DynamicMock(),
    )
    session.expire_all()
    result = client.get(f"/api/v1/agent-tests/{test_id}").json()
    assert result["status"] == "COMPLETED"
    assert result["task_type"] == task_type
    assert result["verification"] == "NOT_INDEPENDENTLY_VERIFIED"
    assert result["steps_completed"] == 3
    assert {
        "FIND_PRICING": "$12",
        "FIND_DOCUMENTATION": "documentation",
        "FIND_SIGNUP_FORM": "Company",
    }[task_type] in result["agent_declared_outcome"]
    assert result["execution_duration"] > 0
    assert result["final_url"].endswith(
        {
            "FIND_PRICING": "/plans.html",
            "FIND_DOCUMENTATION": "/guide.html",
            "FIND_SIGNUP_FORM": "/join.html",
        }[task_type]
    )
    trace = client.get(f"/api/v1/agent-tests/{test_id}/steps").json()
    assert [s["action_type"] for s in trace] == ["navigate", "click", "finish"]
    assert "screenshot_path" not in trace[1]
    screenshot = client.get(f"/api/v1/agent-tests/{test_id}/steps/{trace[1]['id']}/screenshot")
    assert screenshot.status_code == 200
    assert screenshot.headers["content-type"] == "image/png"
    assert len(client.get(f"/api/v1/agent-tests/{test_id}/steps?limit=1&offset=1").json()) == 1
    assert len(client.get(f"/api/v1/scans/{scan['id']}/agent-tests").json()) == 1
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
    execute_agent_test(test_id, factory, lambda *args: None, lambda *args: None)
    assert len(AgentRecords(session).steps(test_id, 100, 0)) == 3


def test_agent_failure_and_expired_execution_recovery(client, session, monkeypatch):
    project = client.post(
        "/api/v1/projects", json={"name": "Failure", "website_url": "https://fixture.example"}
    ).json()
    scan = client.post(f"/api/v1/projects/{project['id']}/scans").json()
    test = client.post(
        f"/api/v1/scans/{scan['id']}/agent-tests", json={"task_type": "FIND_DOCUMENTATION"}
    ).json()

    @contextmanager
    def factory():
        yield session

    def unavailable(settings):
        raise RuntimeError("Configure an inference endpoint")

    execute_agent_test(UUID(test["id"]), factory, provider_factory=unavailable)
    session.expire_all()
    result = AgentRecords(session).test(UUID(test["id"]))
    assert result.status == WorkflowStatus.FAILED
    assert result.completed_at and result.failure_reason
    result.status = WorkflowStatus.RUNNING
    result.execution_deadline = datetime.now(UTC) - timedelta(seconds=1)
    session.commit()
    AgentRecords(session).expire()
    session.commit()
    session.expire_all()
    assert result.status == WorkflowStatus.FAILED
