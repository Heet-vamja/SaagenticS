from uuid import UUID

from sqlalchemy.orm import Session

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
        self.project(project_id)
        scan = Scan(project_id=project_id, status=ScanStatus.PENDING)
        self.records.add(scan)
        self.session.commit()
        return scan
