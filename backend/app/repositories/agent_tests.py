from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.domain import AgentStep, WorkflowStatus, WorkflowTest


class AgentRecords:
    def __init__(self, session: Session):
        self.session = session

    def test(self, test_id: UUID):
        return self.session.scalar(
            select(WorkflowTest).where(
                WorkflowTest.id == test_id, WorkflowTest.task_type.is_not(None)
            )
        )

    def tests(self, scan_id: UUID, limit: int, offset: int):
        return list(
            self.session.scalars(
                select(WorkflowTest)
                .where(WorkflowTest.scan_id == scan_id, WorkflowTest.task_type.is_not(None))
                .order_by(WorkflowTest.execution_deadline.desc(), WorkflowTest.id)
                .limit(limit)
                .offset(offset)
            )
        )

    def steps(self, test_id: UUID, limit: int, offset: int):
        return list(
            self.session.scalars(
                select(AgentStep)
                .where(AgentStep.workflow_test_id == test_id)
                .order_by(AgentStep.step_number)
                .limit(limit)
                .offset(offset)
            )
        )

    def step(self, test_id: UUID, step_id: UUID):
        return self.session.scalar(
            select(AgentStep).where(AgentStep.workflow_test_id == test_id, AgentStep.id == step_id)
        )

    def claim(self, test_id: UUID):
        return (
            self.session.execute(
                update(WorkflowTest)
                .where(WorkflowTest.id == test_id, WorkflowTest.status == WorkflowStatus.PENDING)
                .values(status=WorkflowStatus.RUNNING, started_at=datetime.now(UTC))
            ).rowcount
            == 1
        )

    def expire(self):
        now = datetime.now(UTC)
        self.session.execute(
            update(WorkflowTest)
            .where(
                WorkflowTest.task_type.is_not(None),
                WorkflowTest.status.in_([WorkflowStatus.PENDING, WorkflowStatus.RUNNING]),
                WorkflowTest.execution_deadline < now,
            )
            .values(
                status=WorkflowStatus.FAILED,
                completed_at=now,
                failure_reason="Agent execution deadline expired; process may have restarted",
            )
        )
