from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, Response
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
from app.schemas.reports import FreeReportRead, FreeScanAccepted, FreeScanCreate
from app.services.agent_policy import client_identity
from app.services.audits import AuditService, RecordNotFound
from app.services.crawls import execute_scan
from app.services.reports import ReportService

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


@router.post("/free-scans", response_model=FreeScanAccepted, status_code=201, tags=["Free report"])
def create_free_scan(
    data: FreeScanCreate,
    service: Service,
    background_tasks: BackgroundTasks,
    request: Request,
):
    if get_settings().customer_mode_enabled:
        from app.services.website_access import COOKIE, customer_scan

        scan, token, expires, schedule = customer_scan(
            service.session,
            data.website_url,
            client_identity(request, get_settings()),
            request.cookies.get(COOKIE),
        )
    else:
        scan, token, expires = service.create_free_scan(
            data.website_url, client_identity(request, get_settings())
        )
        schedule = True
    if schedule:
        background_tasks.add_task(execute_scan, scan.id)
    return {
        "report_path": f"/free-reports/{token}",
        "status": scan.status.value,
        "expires_at": expires,
    }


@router.get("/free-reports/{token}", response_model=FreeReportRead, tags=["Free report"])
def free_report(token: str, service: Service, response: Response, request: Request):
    response.headers.update(
        {
            "Cache-Control": "no-store",
            "X-Robots-Tag": "noindex, nofollow",
            "Referrer-Policy": "no-referrer",
        }
    )
    scan_id = ReportService(service.session).shared_scan(token)
    scan = service.scan(scan_id)
    if (scan.audit_summary or {}).get("scan_mode") != "FREE_REPORT":
        raise RecordNotFound("Report link not found or expired")
    project = service.project(scan.project_id)
    findings = service.records.findings(scan_id, 10000, 0)
    from app.services.free_reports import FREE_INSIGHT_LIMIT
    from app.services.free_reports import free_report as build_free_report

    result = build_free_report(scan, project, findings)
    if not get_settings().customer_mode_enabled:
        return result.model_copy(update={"full_report_unlocked": True})
    from app.services.website_access import (
        COOKIE,
        dev_shortcut_enabled,
        development_report_unlocked,
        is_dev_session,
        report_access,
    )

    verification, share, order = report_access(service.session, token, request.cookies.get(COOKIE))
    result = result.model_copy(
        update={
            "development_access": is_dev_session(verification),
            "development_skip_available": dev_shortcut_enabled(),
            "development_payment_skipped": development_report_unlocked(verification, share),
        }
    )
    if development_report_unlocked(verification, share):
        return result.model_copy(update={"full_report_unlocked": True})
    if order:
        return result.model_copy(
            update={"full_report_unlocked": True, "rescan_until": order.rescan_until}
        )
    return result.model_copy(
        update={
            "checks": [],
            "checks_truncated": False,
            "access_policies": [],
            "standards_coverage": None,
            "insights": [
                item.model_copy(update={"evidence_url": None, "evidence_summary": None})
                for item in result.insights[:FREE_INSIGHT_LIMIT]
            ],
            "full_report_unlocked": False,
        }
    )


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
