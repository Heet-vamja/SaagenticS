import asyncio
from pathlib import Path
from threading import BoundedSemaphore
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_session
from app.models.domain import AgentStep, WorkflowTest
from app.schemas.api import ScanRead
from app.schemas.reports import ComparisonRead, ReportRead, ShareRead
from app.services.agent_evidence import resolve_evidence_ref
from app.services.audits import RecordNotFound
from app.services.report_pdf import pdf_export
from app.services.reports import ReportService, csv_export

PDF_SLOTS = BoundedSemaphore(2)

router = APIRouter(prefix="/api/v1", tags=["Reports"])


def service(session: Annotated[Session, Depends(get_session)]):
    return ReportService(session)


Service = Annotated[ReportService, Depends(service)]


@router.get("/scans/{scan_id}/report", response_model=ReportRead, response_model_exclude_unset=True)
def report(scan_id: UUID, service: Service):
    return service.report(scan_id)


@router.get(
    "/scans/{scan_id}/comparison", response_model=ComparisonRead, response_model_exclude_unset=True
)
def comparison(scan_id: UUID, service: Service, before: UUID | None = None):
    return service.compare(scan_id, before)


@router.get("/projects/{project_id}/history", response_model=list[ScanRead])
def history(
    project_id: UUID,
    service: Service,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    return service.history(project_id, limit, offset)


@router.post("/scans/{scan_id}/shares", status_code=201, response_model=ShareRead)
def share(scan_id: UUID, service: Service):
    return service.create_share(scan_id)


@router.post("/scans/{scan_id}/shares/revoke")
def revoke(scan_id: UUID, service: Service):
    return service.revoke_shares(scan_id)


@router.get("/shares/{token}", response_model=ReportRead, response_model_exclude_unset=True)
def shared_report(token: str, service: Service, response: Response):
    response.headers.update(
        {
            "Cache-Control": "no-store",
            "X-Robots-Tag": "noindex, nofollow",
            "Referrer-Policy": "no-referrer",
        }
    )
    return service.report(service.shared_scan(token), shared=True, share_token=token)


@router.get("/shares/{token}/evidence/{run_ref}/{step_ref}.png")
def shared_agent_screenshot(
    token: str, run_ref: str, step_ref: str, service: Service, response: Response
):
    """Serve a screenshot only through a live, share-scoped opaque capability."""
    scan_id = service.shared_scan(token)
    run_ids = list(
        service.session.scalars(
            select(WorkflowTest.id)
            .where(WorkflowTest.scan_id == scan_id, WorkflowTest.task_test_id.is_not(None))
            .limit(10000)
        )
    )
    run_id = resolve_evidence_ref(token, scan_id, "run", run_ref, run_ids)
    step_ids = list(
        service.session.scalars(
            select(AgentStep.id)
            .join(WorkflowTest, AgentStep.workflow_test_id == WorkflowTest.id)
            .where(WorkflowTest.scan_id == scan_id, WorkflowTest.task_test_id.is_not(None))
            .limit(10000)
        )
    )
    step_id = resolve_evidence_ref(token, scan_id, "step", step_ref, step_ids)
    run = service.session.scalar(
        select(WorkflowTest).where(WorkflowTest.id == run_id, WorkflowTest.scan_id == scan_id)
    )
    step = service.session.scalar(
        select(AgentStep).where(
            AgentStep.id == step_id,
            AgentStep.workflow_test_id == run_id,
        )
    )
    if not run or not run.task_test_id or not step or not step.screenshot_path:
        raise RecordNotFound("Evidence not found")
    path = Path(step.screenshot_path).resolve()
    root = (Path(get_settings().agent_screenshot_dir) / str(run_id)).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise RecordNotFound("Evidence not found")
    headers = {
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "no-referrer",
    }
    response.headers.update(headers)
    return FileResponse(path, media_type="image/png", headers=headers)


def export_response(report, format):
    import json

    headers = {
        "Content-Disposition": f'attachment; filename="agentreadiness-report.{format}"',
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
    }
    if format == "json":
        return Response(
            json.dumps(jsonable_encoder(report), ensure_ascii=False),
            media_type="application/json",
            headers=headers,
        )
    if format == "csv":
        return Response(csv_export(report), media_type="text/csv", headers=headers)
    try:
        if not PDF_SLOTS.acquire(blocking=False):
            raise HTTPException(503, "PDF exporter is busy. Please retry shortly.")
        try:
            pdf = asyncio.run(pdf_export(report))
        finally:
            PDF_SLOTS.release()
    except Exception as exc:
        import logging

        logging.getLogger(__name__).exception("Offline PDF export failed (%s)", type(exc).__name__)
        raise HTTPException(
            503, "PDF rendering unavailable. JSON and CSV exports remain available."
        ) from exc
    return Response(pdf, media_type="application/pdf", headers=headers)


@router.get("/scans/{scan_id}/export")
def export(scan_id: UUID, service: Service, format: Literal["json", "csv", "pdf"] = "json"):
    return export_response(service.report(scan_id), format)


@router.get("/shares/{token}/export")
def shared_export(token: str, service: Service, format: Literal["json", "csv", "pdf"] = "json"):
    return export_response(
        service.report(service.shared_scan(token), shared=True, share_token=token), format
    )
