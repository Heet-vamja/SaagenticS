from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.domain import AgentStep, AgentTaskTest, ScanStatus, WorkflowStatus, WorkflowTest


class AgentRecords:
    def __init__(self, session: Session):
        self.session = session

    def test(self, test_id: UUID):
        return self.session.scalar(
            select(WorkflowTest).where(
                WorkflowTest.id == test_id, WorkflowTest.task_type.is_not(None)
            )
        )

    def task(self, task_id: UUID):
        return self.session.get(AgentTaskTest, task_id)

    def tasks(self, scan_id: UUID, limit: int, offset: int):
        return list(
            self.session.scalars(
                select(AgentTaskTest)
                .where(AgentTaskTest.scan_id == scan_id)
                .order_by(AgentTaskTest.created_at.desc(), AgentTaskTest.id)
                .limit(limit)
                .offset(offset)
            )
        )

    def runs(self, task_id: UUID, limit: int, offset: int):
        return list(
            self.session.scalars(
                select(WorkflowTest)
                .where(WorkflowTest.task_test_id == task_id)
                .order_by(WorkflowTest.run_number)
                .limit(limit)
                .offset(offset)
            )
        )

    def claim_task(self, task_id: UUID, deadline: datetime | None = None):
        now = datetime.now(UTC)
        values = {"status": ScanStatus.RUNNING, "started_at": now}
        if deadline is not None:
            values["deadline"] = deadline
        return (
            self.session.execute(
                update(AgentTaskTest)
                .where(AgentTaskTest.id == task_id, AgentTaskTest.status == ScanStatus.PENDING)
                .values(**values)
            ).rowcount
            == 1
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
