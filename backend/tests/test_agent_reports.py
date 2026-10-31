import csv
import io
from datetime import UTC, datetime, timedelta

from app.core.config import Settings
from app.models.domain import (
    AgentStep,
    AgentTaskTest,
    Category,
    Finding,
    Project,
    Scan,
    ScanStatus,
    Severity,
    WorkflowStatus,
    WorkflowTest,
)
from app.schemas.reports import ComparisonRead, ReportRead
from app.services.report_pdf import render_html
from app.services.reports import ReportService, csv_export


def _scan(session, project, minutes_ago, summary, score):
    now = datetime.now(UTC) - timedelta(minutes=minutes_ago)
    scan = Scan(
        project_id=project.id,
        status=ScanStatus.COMPLETED,
        created_at=now,
        started_at=now,
        completed_at=now + timedelta(seconds=5),
        overall_score=score,
        audit_summary=summary,
    )
    session.add(scan)
    session.flush()
    session.add(
        Finding(
            scan_id=scan.id,
            category=Category.INTERACTABILITY,
            severity=Severity.MEDIUM,
            title="Agent failure evidence",
            description="An agent could not locate a control.",
            recommendation="Use a descriptive accessible name.",
            confidence=0.75,
            evidence={
                "engine": "agent-v1",
                "rule": "agent.task.FIND_CONTACT.element_not_found",
                "url": "https://example.test/contact?private=token",
                "run_ref": "private-run-reference",
                "step_ref": "private-step-reference",
            },
        )
    )
    return scan


def test_report_exports_task_runs_and_share_projection_is_safe(session):
    project = Project(name="Reporting", website_url="https://example.test")
    session.add(project)
    session.flush()
    scan = _scan(
        session,
        project,
        0,
        {
            "version": "static-v1",
            "static_score": 70,
            "score_kind": "COMBINED_READINESS",
            "agent_policy": {"model_identifier": "private-policy-detail"},
            "agent": {
                "static_score": 70,
                "agent_score": 100,
                "configured_weight": 0.45,
                "effective_weight": 0.45,
                "eligible_runs": 1,
                "excluded_infra_runs": 1,
                "inconclusive_runs": 0,
                "judged_runs": 0,
                "fallback_reason": None,
                "provisional": True,
                "tasks": [{"task_type": "FIND_CONTACT", "success_rate": 1}],
            },
        },
        83.5,
    )
    task = AgentTaskTest(
        scan_id=scan.id,
        task_type="FIND_CONTACT",
        task_description="Find the public contact page",
        requested_runs=2,
        status=ScanStatus.COMPLETED,
        outcome="SUCCEEDED",
        consistency=True,
        eligible_runs=1,
        runs_completed=2,
    )
    session.add(task)
    session.flush()
    session.add_all(
        [
            WorkflowTest(
                scan_id=scan.id,
                task_test_id=task.id,
                run_number=1,
                task_name="Find contact",
                starting_url="https://example.test/?private=query",
                status=WorkflowStatus.COMPLETED,
                outcome="SUCCEEDED",
                verification_method="rules",
                model_identifier="org/model",
                steps_completed=3,
                execution_duration=12.5,
                prompt_tokens=500,
                completion_tokens=80,
                estimated_cost_usd=0.002,
                final_url="https://example.test/contact?session=secret",
                verification_evidence={
                    "url": "https://example.test/contact?token=private",
                    "title": "Contact us",
                    "public_email_count": 2,
                    "forms": [{"fields": [{"label": "Private full observation"}]}],
                    "private_observation": "Private full observation",
                },
            ),
            WorkflowTest(
                scan_id=scan.id,
                task_test_id=task.id,
                run_number=2,
                task_name="Find contact",
                starting_url="https://example.test",
                status=WorkflowStatus.FAILED,
                outcome="UNAVAILABLE",
                verification_method="unverified",
                failure_category="infra_error",
                model_identifier="org/model",
                steps_completed=0,
            ),
        ]
    )
    session.flush()

    report = ReportService(session).report(scan.id)
    ReportRead.model_validate(report)
    assert report["score_kind"] == "COMBINED_READINESS"
    assert report["score_components"]["agent_score"] == 100
    assert len(report["agent_tasks"][0]["runs"]) == 2
    assert report["agent_tasks"][0]["runs"][0]["estimated_cost_usd"] == 0.002
    assert "id" in report["agent_tasks"][0]
    csv_rows = list(csv.reader(io.StringIO(csv_export(report).decode("utf-8-sig"))))
    assert any("agent_run" in row for row in csv_rows)
    html = render_html(report)
    assert "Find the public contact page" in html
    assert "eligible of" in html

    shared = ReportService(session).report(scan.id, shared=True)
    shared_text = str(shared)
    assert "private-policy-detail" not in shared_text
    assert "Private full observation" not in shared_text
    assert "private_observation" not in shared_text
    assert "session=secret" not in shared_text
    assert str(task.id) not in shared_text
    assert "contact?token=private" not in shared_text
    assert shared["agent_tasks"][0]["runs"][0]["evidence"]["forms"] == [{"field_count": 1}]
    assert "private-run-reference" not in shared_text
    assert "private-step-reference" not in shared_text


def test_comparison_includes_static_agent_score_and_coverage_deltas(session):
    project = Project(name="Comparison", website_url="https://example.test")
    session.add(project)
    session.flush()
    previous = _scan(
        session,
        project,
        2,
        {
            "version": "static-v1",
            "static_score": 60,
            "score_kind": "COMBINED_READINESS",
            "agent": {
                "static_score": 60,
                "agent_score": 50,
                "effective_weight": 0.45,
                "eligible_runs": 2,
            },
        },
        55.5,
    )
    current = _scan(
        session,
        project,
        0,
        {
            "version": "static-v1",
            "static_score": 70,
            "score_kind": "COMBINED_READINESS",
            "agent": {
                "static_score": 70,
                "agent_score": 75,
                "effective_weight": 0.45,
                "eligible_runs": 4,
            },
        },
        72.3,
    )
    comparison = ReportService(session).compare(current.id, previous.id)
    ComparisonRead.model_validate(comparison)
    assert comparison["score_components"]["static_delta"] == 10
    assert comparison["score_components"]["agent_delta"] == 25
    assert comparison["agent_coverage_changed"] is True


def test_comparison_hides_overall_delta_when_scoring_basis_changes(session):
    project = Project(name="Changed basis", website_url="https://example.test")
    session.add(project)
    session.flush()
    previous = _scan(
        session,
        project,
        2,
        {"version": "static-v1", "static_score": 60, "score_kind": "STATIC_READINESS"},
        60,
    )
    current = _scan(
        session,
        project,
        0,
        {
            "version": "static-v1",
            "static_score": 70,
            "score_kind": "COMBINED_READINESS",
            "agent": {
                "static_score": 70,
                "agent_score": 100,
                "effective_weight": 0.45,
                "eligible_runs": 1,
                "eligible_tasks": 1,
                "tasks": [{"task_type": "FIND_PRICING", "outcome": "SUCCEEDED"}],
            },
        },
        83.5,
    )
    comparison = ReportService(session).compare(current.id, previous.id)
    assert comparison["score_delta"] is None
    assert comparison["score_components"]["score_comparable"] is False
    assert comparison["score_components"]["static_delta"] == 10
    assert comparison["score_components"]["agent_delta"] is None


def test_shared_screenshot_uses_expiring_opaque_hmac_capability(
    client, session, monkeypatch, tmp_path
):
    project = Project(name="Shared replay", website_url="https://example.test")
    session.add(project)
    session.flush()
    scan = _scan(
        session,
        project,
        0,
        {"version": "static-v1", "score": 75, "static_score": 75},
        75,
    )
    task = AgentTaskTest(
        scan_id=scan.id,
        task_type="FIND_CONTACT",
        task_description="Find contact information",
        requested_runs=1,
        status=ScanStatus.COMPLETED,
        outcome="SUCCEEDED",
        consistency=True,
        eligible_runs=1,
        runs_completed=1,
    )
    session.add(task)
    session.flush()
    run = WorkflowTest(
        scan_id=scan.id,
        task_test_id=task.id,
        run_number=1,
        task_name="Find contact",
        starting_url="https://example.test",
        status=WorkflowStatus.COMPLETED,
        outcome="SUCCEEDED",
        verification_method="rules",
        steps_completed=1,
        final_url="https://example.test/contact",
    )
    session.add(run)
    session.flush()
    screenshot_path = tmp_path / str(run.id) / "1.png"
    screenshot_path.parent.mkdir(parents=True)
    screenshot_path.write_bytes(b"opaque screenshot bytes")
    step = AgentStep(
        workflow_test_id=run.id,
        step_number=1,
        page_url="https://example.test/contact?private=token",
        observation_summary={"private": "full observation must not be shared"},
        action_type="navigate",
        action_arguments={},
        reasoning_summary="Open contact page",
        action_result={},
        duration_ms=100,
        screenshot_path=str(screenshot_path),
    )
    session.add(step)
    session.flush()
    monkeypatch.setattr(
        "app.api.report_routes.get_settings",
        lambda: Settings(agent_screenshot_dir=str(tmp_path)),
    )

    share = client.post(f"/api/v1/scans/{scan.id}/shares")
    assert share.status_code == 201
    token = share.json()["path"].rsplit("/", 1)[-1]
    response = client.get(f"/api/v1/shares/{token}")
    assert response.status_code == 200
    body = str(response.json())
    assert str(run.id) not in body and str(step.id) not in body
    assert str(screenshot_path) not in body
    assert "private=token" not in body
    assert "full observation" not in body
    step_details = response.json()["agent_tasks"][0]["runs"][0]["step_details"]
    screenshot_url = step_details[0]["screenshot_url"]
    assert str(run.id) not in screenshot_url and str(step.id) not in screenshot_url
    image = client.get(screenshot_url)
    assert image.status_code == 200
    assert image.content == b"opaque screenshot bytes"
    assert image.headers["cache-control"] == "no-store"
    parts = screenshot_url.rsplit("/", 2)
    changed_ref = ("A" if parts[1][0] != "A" else "B") + parts[1][1:]
    tampered = f"{parts[0]}/{changed_ref}/{parts[2]}"
    assert client.get(tampered).status_code == 404
    assert client.post(f"/api/v1/scans/{scan.id}/shares/revoke").status_code == 200
    assert client.get(screenshot_url).status_code == 404
