from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.engines.crawling.urls import URLValidator
from app.models.domain import Project, Scan, ScanStatus
from app.repositories.records import Records
from app.schemas.api import ProjectCreate


class RecordNotFound(Exception):
    pass


class AuditService:
    def __init__(self, session: Session):
        self.session = session
        self.records = Records(session)

    def project(self, project_id: UUID) -> Project:
        if (project := self.records.project(project_id)) is None:
            raise RecordNotFound("Project not found")
        return project

    def create_project(self, data: ProjectCreate) -> Project:
        project = Project(**data.model_dump())
        self.records.add(project)
        self.session.commit()
        return project

    def scan(self, scan_id: UUID) -> Scan:
        if (scan := self.records.scan(scan_id)) is None:
            raise RecordNotFound("Scan not found")
        return scan

    def create_scan(self, project_id: UUID) -> Scan:
        project = self.project(project_id)
        URLValidator(project.website_url, get_settings().crawl_allow_subdomains)
        self.records.admission_lock()
        existing = self.session.scalar(
            select(Scan)
            .where(
                Scan.project_id == project_id,
                Scan.status.in_([ScanStatus.PENDING, ScanStatus.RUNNING]),
            )
            .order_by(Scan.created_at)
        )
        if existing:
            self.session.commit()
            return existing
        if (
            self.records.active_count([ScanStatus.PENDING, ScanStatus.RUNNING])
            >= get_settings().scan_queue_limit
        ):
            raise HTTPException(429, "The scan queue is full. Please try again shortly.")
        scan = Scan(
            project_id=project_id,
            audit_summary={
                "phase": "QUEUED",
                "limits": {
                    "max_pages": get_settings().crawl_max_pages,
                    "total_seconds": get_settings().scan_duration,
                    "browser_pages": get_settings().audit_render_pages,
                },
            },
            status=ScanStatus.PENDING,
            execution_deadline=datetime.now(UTC)
            + timedelta(seconds=get_settings().scan_queue_wait),
        )
        self.records.add(scan)
        self.session.commit()
        return scan
