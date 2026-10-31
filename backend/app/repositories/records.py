from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, or_, select, text, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.domain import Finding, Page, Project, Scan, ScanStatus, WorkflowTest


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
            self.session.scalars(
                select(Scan).order_by(Scan.created_at.desc(), Scan.id).limit(limit).offset(offset)
            )
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

    def pages(self, scan_id: UUID, limit: int, offset: int) -> list[Page]:
        return list(
            self.session.scalars(
                select(Page)
                .where(Page.scan_id == scan_id)
                .order_by(Page.crawl_depth, Page.url)
                .limit(limit)
                .offset(offset)
            )
        )

    def page(self, scan_id: UUID, page_id: UUID) -> Page | None:
        return self.session.scalar(select(Page).where(Page.scan_id == scan_id, Page.id == page_id))

    def page_by_url(self, scan_id: UUID, url: str) -> Page | None:
        return self.session.scalar(select(Page).where(Page.scan_id == scan_id, Page.url == url))

    def admission_lock(self):
        # Serializes admission across API workers without a distributed queue.
        self.session.execute(text("SELECT pg_advisory_xact_lock(648216320)"))

    def pending_scans(self, limit):
        return list(
            self.session.scalars(
                select(Scan.id)
                .where(Scan.status == ScanStatus.PENDING)
                .order_by(Scan.created_at, Scan.id)
                .limit(limit)
            )
        )

    def active_count(self, statuses):
        return self.session.scalar(
            select(func.count()).select_from(Scan).where(Scan.status.in_(statuses))
        )

    def claim_scan(self, scan_id: UUID):
        self.admission_lock()
        settings = get_settings()
        if self.active_count([ScanStatus.RUNNING]) >= settings.scan_max_active:
            return False
        return (
            self.session.execute(
                update(Scan)
                .where(Scan.id == scan_id, Scan.status == ScanStatus.PENDING)
                .values(
                    status=ScanStatus.RUNNING,
                    started_at=datetime.now(UTC),
                    execution_deadline=datetime.now(UTC)
                    + timedelta(seconds=settings.scan_duration + 15),
                )
            ).rowcount
            == 1
        )

    def expire_scans(self):
        now = datetime.now(UTC)
        self.session.execute(
            update(Scan)
            .where(
                Scan.status.in_([ScanStatus.PENDING, ScanStatus.RUNNING]),
                or_(Scan.execution_deadline < now, Scan.execution_deadline.is_(None)),
            )
            .values(
                status=ScanStatus.FAILED,
                completed_at=now,
                started_at=func.coalesce(Scan.started_at, now),
                error_summary="Execution deadline expired; process may have restarted",
            )
        )
