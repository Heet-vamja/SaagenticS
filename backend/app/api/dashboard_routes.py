"""Owner dashboard API (phase 3). Every route requires the operator bearer token."""

import hmac
from contextlib import nullcontext
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_session
from app.engines.variants.actions import DeliveryRules
from app.repositories.edge import EdgeRecords
from app.schemas.dashboard import JobCreate, SiteCreate, SiteUpdate
from app.services.edge_sites import (
    SiteBusy,
    register_site,
    remove_site,
    set_delivery_rules,
    site_settings,
    update_site,
)
from app.services.insights import build_sessions, overview
from app.services.site_jobs import JobConflict, enqueue, job_view, recent_jobs
from app.services.variants import publish_variant


def require_dashboard(request: Request) -> None:
    expected = get_settings().edge_dashboard_token.get_secret_value()
    if not expected:
        raise HTTPException(404, "The dashboard is not enabled")
    supplied = request.headers.get("authorization", "")
    token = supplied[7:] if supplied.lower().startswith("bearer ") else ""
    if not hmac.compare_digest(token.encode(), expected.encode()):
        raise HTTPException(401, "A valid dashboard token is required")


router = APIRouter(prefix="/api/v1/dashboard", dependencies=[Depends(require_dashboard)])
Db = Annotated[Session, Depends(get_session)]


def _scoped(session: Session):
    return lambda: nullcontext(session)


@router.get("/sites")
def sites(session: Db):
    return {
        "sites": [
            {"host": site.host, "name": site.name, "routing_enabled": site.routing_enabled}
            for site in EdgeRecords(session).sites()
        ]
    }


@router.post("/sites", status_code=201)
def create_site(body: SiteCreate, session: Db):
    try:
        site = register_site(session, get_settings(), body.host, body.origin, body.name)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"host": site.host, "name": site.name, "routing_enabled": site.routing_enabled}


@router.get("/sites/{host}/overview")
def site_overview(host: str, session: Db, days: Annotated[int, Query(ge=1, le=90)] = 7):
    try:
        return overview(host, _scoped(session), days)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/sites/{host}/sessions")
def refresh_sessions(host: str, session: Db):
    """Group new agent requests into sessions (deterministic; no model call)."""
    try:
        return build_sessions(host, _scoped(session))
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/sites/{host}/variants")
def variants(host: str, session: Db):
    records = EdgeRecords(session)
    site = records.site_by_host(host.strip().lower())
    if site is None:
        raise HTTPException(404, f"{host} is not registered")
    return {
        "variants": [
            {
                "version": v.version,
                "status": v.status,
                "parity_passed": bool(v.parity.get("passed")),
                "products": len(v.catalog.get("products", [])),
                "pages": v.evidence_summary.get("pages", 0),
                "created_at": v.created_at.isoformat(),
                "published_at": v.published_at.isoformat() if v.published_at else None,
            }
            for v in records.variants(site.id, limit=10)
        ]
    }


@router.post("/sites/{host}/variants/{version}/publish")
def publish(host: str, version: int, session: Db):
    try:
        publish_variant(host, version, _scoped(session))
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"published": version}


@router.get("/sites/{host}/jobs")
def jobs(host: str, session: Db):
    try:
        return {"jobs": [job_view(job) for job in recent_jobs(session, host)]}
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/sites/{host}/jobs", status_code=202)
def start_job(host: str, body: JobCreate, session: Db):
    """Queue a job for the jobs worker. Nothing runs in this request."""
    try:
        return job_view(enqueue(session, host, body.kind))
    except JobConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/sites/{host}/settings")
def get_site_settings(host: str, session: Db):
    site = EdgeRecords(session).site_by_host(host.strip().lower())
    if site is None:
        raise HTTPException(404, f"{host} is not registered")
    return site_settings(site)


@router.patch("/sites/{host}")
def patch_site(host: str, body: SiteUpdate, session: Db):
    try:
        site = update_site(session, get_settings(), host, **body.model_dump(exclude_unset=True))
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return site_settings(site)


@router.put("/sites/{host}/delivery")
def put_delivery(host: str, body: DeliveryRules, session: Db):
    """Owner-approved delivery estimates for the check_delivery action."""
    try:
        return site_settings(set_delivery_rules(session, host, body))
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.delete("/sites/{host}/delivery")
def delete_delivery(host: str, session: Db):
    try:
        return site_settings(set_delivery_rules(session, host, None))
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.delete("/sites/{host}", status_code=204)
def delete_site(host: str, session: Db):
    try:
        remove_site(session, host)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except SiteBusy as exc:
        raise HTTPException(409, str(exc)) from exc
