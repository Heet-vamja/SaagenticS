from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.domain import EdgeSite, SiteJob


class JobRecords:
    """Database access only; the service owns transaction boundaries."""

    def __init__(self, session: Session):
        self.session = session

    def add(self, job: SiteJob) -> SiteJob:
        self.session.add(job)
        self.session.flush()
        return job

    def recent(self, site_id, limit: int = 10) -> list[SiteJob]:
        return list(
            self.session.scalars(
                select(SiteJob)
                .where(SiteJob.site_id == site_id)
                .order_by(SiteJob.created_at.desc())
                .limit(limit)
            )
        )

    def next_pending(self) -> SiteJob | None:
        """Oldest pending job, locked so concurrent workers never claim the same one."""
        return self.session.scalar(
            select(SiteJob)
            .where(SiteJob.status == "PENDING")
            .order_by(SiteJob.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )

    def has_active(self, site_id) -> bool:
        return (
            self.session.scalar(
                select(SiteJob.id)
                .where(SiteJob.site_id == site_id, SiteJob.status.in_(("PENDING", "RUNNING")))
                .limit(1)
            )
            is not None
        )

    def host_of(self, site_id) -> str:
        return self.session.scalar(select(EdgeSite.host).where(EdgeSite.id == site_id))

    def fail_running_before(self, cutoff: datetime, detail: str, now: datetime) -> int:
        result = self.session.execute(
            update(SiteJob)
            .where(SiteJob.status == "RUNNING", SiteJob.started_at < cutoff)
            .values(status="FAILED", detail=detail, finished_at=now)
        )
        return result.rowcount or 0
