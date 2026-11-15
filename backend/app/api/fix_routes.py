from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_session
from app.schemas.fixes import FixCenterRead, FixEventCreate, FreeFixPreview
from app.schemas.reports import FreeScanAccepted
from app.services.agent_policy import client_identity
from app.services.audits import RecordNotFound
from app.services.crawls import execute_scan
from app.services.customer_fixes import CustomerFixService

router = APIRouter(prefix="/api/v1/free-reports/{token}", tags=["Fix Center"])
PRIVACY_HEADERS = {
    "Cache-Control": "no-store",
    "X-Robots-Tag": "noindex, nofollow",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
}
RobotsPreset = Literal["keep_existing", "allow_search", "block_training"]


def service(
    token: str,
    response: Response,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
):
    response.headers.update(PRIVACY_HEADERS)
    if get_settings().customer_mode_enabled:
        from app.services.website_access import COOKIE, report_access

        report_access(session, token, request.cookies.get(COOKIE), paid=True)
    return CustomerFixService(session, token)


Service = Annotated[CustomerFixService, Depends(service)]


@router.get("/fix-preview", response_model=FreeFixPreview)
def preview(
    token: str,
    response: Response,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
):
    response.headers.update(PRIVACY_HEADERS)
    if get_settings().customer_mode_enabled:
        from app.services.website_access import COOKIE, report_access

        report_access(session, token, request.cookies.get(COOKIE))
    return CustomerFixService(session, token).preview()


@router.get("/fix-center", response_model=FixCenterRead)
def center(service: Service, robots_preset: RobotsPreset = "keep_existing"):
    return service.center(robots_preset)


@router.post("/fix-events")
def event(data: FixEventCreate, service: Service, robots_preset: RobotsPreset = "keep_existing"):
    return service.record(data.event_type, data.fix_key, robots_preset)


@router.post("/rescan", status_code=201, response_model=FreeScanAccepted)
def rescan(service: Service, request: Request, background_tasks: BackgroundTasks):
    if get_settings().customer_mode_enabled:
        from fastapi import HTTPException

        from app.services.website_access import (
            COOKIE,
            active_order,
            bind_share,
            development_report_unlocked,
            report_access,
        )

        verification, source_share, _ = report_access(
            service.session, request.path_params["token"], request.cookies.get(COOKIE), paid=True
        )
        order = active_order(service.session, verification)
        if not order and not development_report_unlocked(verification, source_share):
            raise HTTPException(
                402,
                "The 30-day free re-scan window has ended. Start a new domain unlock to run another scan.",
            )
    scan, accepted = service.rescan(client_identity(request, get_settings()))
    if get_settings().customer_mode_enabled:
        bound = bind_share(
            service.session, accepted["report_path"].rsplit("/", 1)[-1], verification, order
        )
        if development_report_unlocked(verification, source_share):
            bound.development_unlocked = True
            service.session.commit()
        accepted["expires_at"] = bound.expires_at
    background_tasks.add_task(execute_scan, scan.id)
    return accepted


@router.get("/assets/{filename}")
def asset(filename: str, service: Service, robots_preset: RobotsPreset = "keep_existing"):
    result = next(
        (asset for asset in service.center(robots_preset).assets if asset.filename == filename),
        None,
    )
    if not result:
        raise RecordNotFound("Validated asset not found")
    service.record("ASSET_DOWNLOADED", result.key, robots_preset)
    return Response(
        result.content,
        media_type=result.media_type,
        headers={
            **PRIVACY_HEADERS,
            "Content-Disposition": f'attachment; filename="{result.filename}"',
            "Content-Security-Policy": "default-src 'none'; sandbox",
        },
    )


@router.get("/fix-pack.zip")
def fix_pack(service: Service, robots_preset: RobotsPreset = "keep_existing"):
    content = service.fix_pack(robots_preset)
    service.record("PACK_DOWNLOADED")
    return Response(
        content,
        media_type="application/zip",
        headers={
            **PRIVACY_HEADERS,
            "Content-Disposition": 'attachment; filename="agentlane-fix-pack.zip"',
        },
    )
