from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.models.domain import (
    AdmissionBucket,
    AgentStep,
    AgentTaskTest,
    Project,
    Scan,
    ScanStatus,
    WorkflowTest,
)
from app.repositories.agent_tests import AgentRecords
from app.schemas.agent import AgentTaskCreate, AgentTaskRead


def make_scan(session):
    project = Project(name="Task persistence", website_url="https://example.test")
    session.add(project)
    session.flush()
    scan = Scan(project_id=project.id)
    session.add(scan)
    session.flush()
    return scan


def test_task_runs_claim_and_legacy_run_defaults(session):
    scan = make_scan(session)
    task = AgentTaskTest(
        scan_id=scan.id,
        task_type="FIND_CONTACT",
        task_description="Find the public contact page",
        requested_runs=2,
        policy_snapshot={"max_steps": 15},
    )
    session.add(task)
    session.flush()
    for run_number in (2, 1):
        session.add(
            WorkflowTest(
                scan_id=scan.id,
                task_test_id=task.id,
                run_number=run_number,
                task_name="Find contact",
                starting_url="https://example.test",
                status="PENDING",
            )
        )
    legacy = WorkflowTest(
        scan_id=scan.id,
        task_name="Legacy run",
        starting_url="https://example.test",
        status="COMPLETED",
    )
    session.add(legacy)
    session.flush()

    records = AgentRecords(session)
    assert records.task(task.id) is task
    assert records.tasks(scan.id, 10, 0) == [task]
    assert [run.run_number for run in records.runs(task.id, 10, 0)] == [1, 2]
    assert legacy.task_test_id is None
    assert legacy.verification_method == "unverified"
    assert legacy.outcome is None
    deadline = datetime.now(UTC) + timedelta(minutes=3)
    assert records.claim_task(task.id, deadline)
    assert not records.claim_task(task.id, deadline)
    session.flush()
    assert task.status == ScanStatus.RUNNING
    assert task.started_at is not None
    assert task.deadline is not None


def test_create_schema_is_bounded_and_rejects_provider_controls():
    assert AgentTaskCreate(task_type="FIND_CONTACT").runs is None
    assert AgentTaskCreate(task_type="FIND_PRICING", runs=3).runs == 3
    for values in (
        {"task_type": "FIND_DOCUMENTATION", "runs": 4},
        {"task_type": "FIND_DOCUMENTATION", "model": "arbitrary/model"},
        {"task_type": "UNKNOWN"},
    ):
        with pytest.raises(ValidationError):
            AgentTaskCreate.model_validate(values)


def test_admission_bucket_and_step_usage_persist(session):
    scan = make_scan(session)
    workflow = WorkflowTest(
        scan_id=scan.id,
        task_name="Task",
        starting_url="https://example.test",
        status="PENDING",
    )
    session.add(workflow)
    session.flush()
    step = AgentStep(
        workflow_test_id=workflow.id,
        step_number=1,
        page_url="https://example.test",
        observation_summary={},
        action_type="navigate",
        action_arguments={},
        reasoning_summary="Open homepage",
        action_result={},
        duration_ms=1,
        prompt_tokens=10,
        completion_tokens=4,
        llm_latency_ms=120,
        error_category="infra_error",
    )
    bucket = AdmissionBucket(
        bucket_key="sha256:peer:scan:2032-01-01T00",
        count=1,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    session.add_all([step, bucket])
    session.flush()
    assert step.id and bucket.count == 1

    invalid = AgentTaskTest(
        scan_id=scan.id,
        task_type="FIND_PRICING",
        task_description="Price",
        requested_runs=4,
    )
    session.add(invalid)
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_run_cannot_reference_task_from_another_scan(session):
    scan_a = make_scan(session)
    scan_b = make_scan(session)
    task = AgentTaskTest(
        scan_id=scan_a.id,
        task_type="FIND_PRICING",
        task_description="Find pricing",
        requested_runs=1,
    )
    session.add(task)
    session.flush()
    session.add(
        WorkflowTest(
            scan_id=scan_b.id,
            task_test_id=task.id,
            run_number=1,
            task_name="Wrong scan",
            starting_url="https://example.test",
            status="PENDING",
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_task_read_schema_carries_aggregate_fields():
    now = datetime.now(UTC)
    dto = AgentTaskRead.model_validate(
        {
            "id": uuid4(),
            "scan_id": uuid4(),
            "task_type": "FIND_PRICING",
            "task_description": "Find prices",
            "requested_runs": 2,
            "status": "COMPLETED",
            "outcome": "INCONCLUSIVE",
            "consistency": False,
            "eligible_runs": 2,
            "runs_completed": 2,
            "created_at": now,
            "started_at": now,
            "completed_at": now,
            "deadline": None,
            "policy_snapshot": {},
            "failure_reason": None,
        }
    )
    assert dto.outcome == "INCONCLUSIVE"
