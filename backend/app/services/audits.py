import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.engines.crawling.urls import URLValidator
from app.models.domain import Project, ReportShare, Scan, ScanStatus
from app.repositories.records import Records
from app.schemas.api import ProjectCreate
from app.services.agent_policy import consume_admission, snapshot


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

    def create_scan(self, project_id: UUID, identity="local") -> Scan:
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
        settings = get_settings()
        consume_admission(self.session, identity, "scan", settings)
        scan = Scan(
            project_id=project_id,
            audit_summary={
                "phase": "QUEUED",
                "limits": {
                    "max_pages": settings.crawl_max_pages,
                    "total_seconds": settings.scan_duration,
                    "browser_pages": settings.audit_render_pages,
                },
                "agent_policy": snapshot(settings),
            },
            status=ScanStatus.PENDING,
            execution_deadline=datetime.now(UTC)
            + timedelta(
                seconds=settings.scan_queue_wait
                + settings.scan_duration
                + settings.agent_stage_duration
                + 30
            ),
        )
        self.records.add(scan)
        self.session.commit()
        return scan

    def create_free_scan(self, website_url: str, identity: str):
        """Create a URL-only scan and expiring report capability; never enables agents."""
        settings = get_settings()
        try:
            normalized = URLValidator.normalize(website_url)
            scope = URLValidator(normalized, settings.crawl_allow_subdomains)
            normalized = scope.accept(normalized)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        self.records.admission_lock()
        consume_admission(self.session, identity, "scan", settings)

        project = self.session.scalar(
            select(Project).where(Project.website_url == scope.start).order_by(Project.created_at)
        )
        if project is None:
            host = urlsplit(scope.start).hostname or "Website"
            project = Project(name=host[:200], website_url=scope.start)
            self.records.add(project)

        active_scans = list(
            self.session.scalars(
                select(Scan)
                .where(
                    Scan.project_id == project.id,
                    Scan.status.in_([ScanStatus.PENDING, ScanStatus.RUNNING]),
                )
                .order_by(Scan.created_at, Scan.id)
            )
        )
        scan = next(
            (
                item
                for item in active_scans
                if (item.audit_summary or {}).get("scan_mode") == "FREE_REPORT"
            ),
            None,
        )
        if scan is None:
            if (
                self.records.active_count([ScanStatus.PENDING, ScanStatus.RUNNING])
                >= settings.scan_queue_limit
            ):
                raise HTTPException(429, "The scan queue is full. Please try again shortly.")
            limits = {
                "max_pages": min(10, settings.crawl_max_pages),
                "total_seconds": settings.scan_duration,
                "browser_pages": settings.audit_render_pages,
            }
            agent_policy = snapshot(settings)
            agent_policy.update({"pipeline_enabled": False, "task_types": [], "task_limit": 0})
            scan = Scan(
                project_id=project.id,
                status=ScanStatus.PENDING,
                audit_summary={
                    "phase": "QUEUED",
                    "scan_mode": "FREE_REPORT",
                    "limits": limits,
                    "agent_policy": agent_policy,
                },
                execution_deadline=datetime.now(UTC)
                + timedelta(seconds=settings.scan_queue_wait + settings.scan_duration + 30),
            )
            self.records.add(scan)

        token = secrets.token_urlsafe(32)
        expires = datetime.now(UTC) + timedelta(days=settings.report_share_days)
        self.session.add(
            ReportShare(
                scan_id=scan.id,
                token_digest=hashlib.sha256(token.encode()).hexdigest(),
                expires_at=expires,
            )
        )
        self.session.commit()
        return scan, token, expires
