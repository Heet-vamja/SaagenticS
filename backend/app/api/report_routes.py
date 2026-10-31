import asyncio
from threading import BoundedSemaphore
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.schemas.api import ScanRead
from app.schemas.reports import ComparisonRead, ReportRead, ShareRead
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
    return service.report(service.shared_scan(token), shared=True)


def export_response(report, format):
    import json

    headers = {
        "Content-Disposition": f'attachment; filename="agentreadiness-static-report.{format}"',
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
    return export_response(service.report(service.shared_scan(token), shared=True), format)
