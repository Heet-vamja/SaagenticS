from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_session
from app.schemas.api import (
    FindingRead,
    PageRead,
    ProjectCreate,
    ProjectRead,
    ScanCreate,
    ScanRead,
    WorkflowRead,
)
from app.services.agent_policy import client_identity
from app.services.audits import AuditService, RecordNotFound
from app.services.crawls import execute_scan

router = APIRouter(prefix="/api/v1")
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


def get_service(session: Annotated[Session, Depends(get_session)]) -> AuditService:
    return AuditService(session)


Service = Annotated[AuditService, Depends(get_service)]


@router.post("/projects", response_model=ProjectRead, status_code=201, tags=["Projects"])
def create_project(data: ProjectCreate, service: Service):
    return service.create_project(data)


@router.get("/projects", response_model=list[ProjectRead], tags=["Projects"])
def list_projects(service: Service, limit: Limit = 100, offset: Offset = 0):
    return service.records.projects(limit, offset)


@router.get("/projects/{project_id}", response_model=ProjectRead, tags=["Projects"])
def get_project(project_id: UUID, service: Service):
    return service.project(project_id)


@router.post("/scans", response_model=ScanRead, status_code=201, tags=["Scans"])
def create_scan(
    data: ScanCreate, service: Service, background_tasks: BackgroundTasks, request: Request
):
    scan = service.create_scan(data.project_id, client_identity(request, get_settings()))
    background_tasks.add_task(execute_scan, scan.id)
    return scan


@router.post(
    "/projects/{project_id}/scans", response_model=ScanRead, status_code=201, tags=["Scans"]
)
def start_project_scan(
    project_id: UUID, service: Service, background_tasks: BackgroundTasks, request: Request
):
    scan = service.create_scan(project_id, client_identity(request, get_settings()))
    background_tasks.add_task(execute_scan, scan.id)
    return scan


@router.get("/scans/{scan_id}/pages", response_model=list[PageRead], tags=["Pages"])
def pages(scan_id: UUID, service: Service, limit: Limit = 100, offset: Offset = 0):
    service.scan(scan_id)
    return service.records.pages(scan_id, limit, offset)


@router.get("/scans/{scan_id}/pages/{page_id}", response_model=PageRead, tags=["Pages"])
def page(scan_id: UUID, page_id: UUID, service: Service):
    service.scan(scan_id)
    result = service.records.page(scan_id, page_id)
    if result is None:
        raise RecordNotFound("Page not found")
    return result


@router.get("/scans", response_model=list[ScanRead], tags=["Scans"])
def list_scans(service: Service, limit: Limit = 100, offset: Offset = 0):
    return service.records.scans(limit, offset)


@router.get("/scans/{scan_id}", response_model=ScanRead, tags=["Scans"])
def get_scan(scan_id: UUID, service: Service):
    return service.scan(scan_id)


@router.get("/scans/{scan_id}/findings", response_model=list[FindingRead], tags=["Findings"])
def findings(scan_id: UUID, service: Service, limit: Limit = 100, offset: Offset = 0):
    service.scan(scan_id)
    return service.records.findings(scan_id, limit, offset)


@router.get(
    "/scans/{scan_id}/workflow-tests", response_model=list[WorkflowRead], tags=["Workflow tests"]
)
def workflow_tests(scan_id: UUID, service: Service, limit: Limit = 100, offset: Offset = 0):
    service.scan(scan_id)
    return service.records.workflow_tests(scan_id, limit, offset)
