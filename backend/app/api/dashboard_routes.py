"""Owner dashboard API (phase 3). Every route requires the operator bearer token."""

import hmac
from contextlib import nullcontext
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_session
from app.repositories.edge import EdgeRecords
from app.services.insights import build_sessions, overview


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
