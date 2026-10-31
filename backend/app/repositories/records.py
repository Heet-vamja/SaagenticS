from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.domain import Finding, Project, Scan, WorkflowTest


class Records:
    """Database access only; the service owns transaction boundaries."""

    def __init__(self, session: Session):
        self.session = session

    def projects(self, limit: int, offset: int) -> list[Project]:
        return list(
            self.session.scalars(
                select(Project)
                .order_by(Project.created_at.desc(), Project.id)
                .limit(limit)
                .offset(offset)
            )
        )

    def project(self, project_id: UUID) -> Project | None:
        return self.session.get(Project, project_id)

    def add(self, record: Project | Scan) -> None:
        self.session.add(record)
        self.session.flush()

    def scan(self, scan_id: UUID) -> Scan | None:
        return self.session.get(Scan, scan_id)

    def scans(self, limit: int, offset: int) -> list[Scan]:
        return list(
            self.session.scalars(select(Scan).order_by(Scan.id).limit(limit).offset(offset))
        )

    def findings(self, scan_id: UUID, limit: int, offset: int) -> list[Finding]:
        return list(
            self.session.scalars(
                select(Finding)
                .where(Finding.scan_id == scan_id)
                .order_by(Finding.id)
                .limit(limit)
                .offset(offset)
            )
        )

    def workflow_tests(self, scan_id: UUID, limit: int, offset: int) -> list[WorkflowTest]:
        return list(
            self.session.scalars(
                select(WorkflowTest)
                .where(WorkflowTest.scan_id == scan_id)
                .order_by(WorkflowTest.id)
                .limit(limit)
                .offset(offset)
            )
        )
