from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_session
from app.models.domain import WebsiteVerification
from app.services import payments
from app.services import website_access as access
from app.services.agent_policy import client_identity

router = APIRouter(prefix="/api/v1", tags=["Verified website access"])
SessionDep = Annotated[Session, Depends(get_session)]


class WebsiteInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    website_url: str = Field(min_length=1, max_length=2048)


class EmailInput(WebsiteInput):
    email: str | None = Field(None, max_length=254)
    candidate_id: UUID | None = None


class CodeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    challenge_id: UUID
    code: str = Field(min_length=6, max_length=6)


def privacy(response):
    response.headers.update(
        {
            "Cache-Control": "no-store",
            "Referrer-Policy": "no-referrer",
            "X-Robots-Tag": "noindex, nofollow",
        }
    )


def set_session_cookie(response, token):
    response.set_cookie(
        access.COOKIE,
        token,
        max_age=30 * 86400,
        httponly=True,
        secure=get_settings().verification_cookie_secure,
        samesite="lax",
        path="/",
    )


@router.get("/verification/status")
def status(website_url: str, request: Request, response: Response, session: SessionDep):
    privacy(response)
    domain, _ = access.domain_url(website_url)
    try:
        row = access.verified_session(session, request.cookies.get(access.COOKIE), domain)
        return {
            "verified": True,
            "email_hint": access.mask_email(row.email),
            "domain": domain,
            "development_access": access.is_dev_session(row),
            "development_skip_available": access.dev_shortcut_enabled(),
        }
    except HTTPException as exc:
        if exc.status_code != 401:
            raise
        return {
            "verified": False,
            "domain": domain,
            "development_skip_available": access.dev_shortcut_enabled(),
            "development_email": get_settings().dev_access_email
            if access.dev_shortcut_enabled()
            else None,
        }


@router.post("/verification/request")
def request_code(data: EmailInput, request: Request, response: Response, session: SessionDep):
    privacy(response)
    return access.request_code(
        session,
        data.website_url,
        client_identity(request, get_settings()),
        data.email,
        data.candidate_id,
    )


@router.post("/verification/verify")
def verify(data: CodeInput, request: Request, response: Response, session: SessionDep):
    row, token = access.verify_code(
        session, data.challenge_id, data.code, client_identity(request, get_settings())
    )
    privacy(response)
    set_session_cookie(response, token)
    return {"verified": True, "domain": row.domain, "email_hint": access.mask_email(row.email)}


@router.post("/verification/discover")
async def discover(data: WebsiteInput, request: Request, response: Response, session: SessionDep):
    privacy(response)
    access.secret()
    identity = client_identity(request, get_settings())
    access.rate_limit(session, identity, "discover", 5)
    domain, url = access.domain_url(data.website_url)
    try:
        emails = await access.discover_contact_emails(url)
    except (TimeoutError, OSError, ValueError, httpx.HTTPError) as exc:
        raise HTTPException(
            422, "Could not inspect public contact details. Use a domain email instead."
        ) from exc
    candidates = []
    for email in emails:
        row = WebsiteVerification(
            domain=domain,
            website_url=url,
            email=email,
            identity_hash=access.digest(identity),
            discovered=True,
            otp_expires_at=datetime.now(UTC) + timedelta(minutes=10),
        )
        session.add(row)
        session.flush()
        candidates.append({"id": row.id, "email_hint": access.mask_email(email)})
    session.commit()
    return {
        "candidates": candidates,
        "message": "Choose a published mailbox you can access."
        if candidates
        else "No public email was found. Use an exact-domain email or contact support; no scan has started.",
    }


@router.post("/free-reports/{token}/checkout")
def checkout(token: str, request: Request, session: SessionDep, response: Response):
    privacy(response)
    return payments.checkout(
        session, token, request.cookies.get(access.COOKIE), client_identity(request, get_settings())
    )


@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request, session: SessionDep):
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 1_000_000:
            raise HTTPException(413, "Webhook payload too large")
    event = payments.verify_event(bytes(body), request.headers.get("stripe-signature", ""))
    return payments.process_event(session, event)


@router.get("/free-reports/{token}/verification-target")
def report_target(token: str, session: SessionDep, response: Response):
    from app.engines.agent.privacy import public_url
    from app.models.domain import Project, Scan
    from app.services.reports import ReportService

    privacy(response)
    share = ReportService(session).shared_link(token)
    scan = session.get(Scan, share.scan_id)
    project = session.get(Project, scan.project_id)
    return {"website_url": public_url(project.website_url)}


@router.post("/verification/skip")
def skip_verification(data: EmailInput, request: Request, response: Response, session: SessionDep):
    if not access.dev_shortcut_enabled():
        raise HTTPException(403, "Development skips are disabled")
    domain, _ = access.domain_url(data.website_url)
    identity = client_identity(request, get_settings())
    email = data.email or ""
    if data.candidate_id:
        candidate = session.get(WebsiteVerification, data.candidate_id)
        if (
            not candidate
            or candidate.domain != domain
            or candidate.identity_hash != access.digest(identity)
            or candidate.otp_expires_at <= datetime.now(UTC)
        ):
            raise HTTPException(422, "Contact selection has expired")
        email = candidate.email
    row, token = access.create_dev_session(session, data.website_url, email, identity)
    privacy(response)
    set_session_cookie(response, token)
    return {
        "verified": True,
        "development_access": True,
        "email_hint": access.mask_email(row.email),
    }


@router.post("/free-reports/{token}/skip-payment")
def skip_payment(token: str, request: Request, response: Response, session: SessionDep):
    if not access.dev_shortcut_enabled():
        raise HTTPException(403, "Development skips are disabled")
    _, share, _ = access.report_access(session, token, request.cookies.get(access.COOKIE))
    share.development_unlocked = True
    session.commit()
    privacy(response)
    return {"development_payment_skipped": True}
