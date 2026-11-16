"""Mailbox verification and website-scoped customer capabilities. No account system."""

import asyncio
import hashlib
import hmac
import ipaddress
import re
import secrets
import smtplib
import ssl
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from urllib.parse import urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.core.config import get_settings
from app.engines.crawling.crawler import WebsiteCrawler
from app.engines.crawling.urls import URLValidator
from app.models.domain import AdmissionBucket, DomainOrder, WebsiteVerification

COOKIE = "ar_website_session"
EMAIL = re.compile(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}")


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def dev_shortcut_enabled():
    settings = get_settings()
    return (
        settings.app_environment == "development"
        and settings.dev_email_shortcut_enabled
        and bool(settings.dev_access_email.strip())
        and not settings.stripe_live_mode
        and urlsplit(settings.public_site_url).hostname in {"localhost", "127.0.0.1", "::1"}
    )


def is_dev_session(row):
    return dev_shortcut_enabled() and row.verification_method in {"DEV_SHORTCUT", "DEV_EMAIL_OTP"}


def development_report_unlocked(verification, share):
    return dev_shortcut_enabled() and bool(share.development_unlocked)


def create_dev_session(session, website_url, email, identity):
    """Explicit local-only development access, never a paid/OTP-verified record."""
    if not dev_shortcut_enabled():
        return None
    domain, url = domain_url(website_url)
    token = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    row = WebsiteVerification(
        domain=domain,
        website_url=url,
        email=email_address(email),
        identity_hash=digest(identity),
        verification_method="DEV_SHORTCUT",
        otp_expires_at=now,
        verified_at=now,
        session_digest=digest(token),
        session_expires_at=now + timedelta(days=30),
    )
    session.add(row)
    session.commit()
    return row, token


def domain_url(value):
    try:
        url = URLValidator.normalize(value)
        scope = URLValidator(url, False)
        url = scope.accept(url)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    host = urlsplit(url).hostname
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise HTTPException(422, "Use a website domain rather than an IP address")
    return host.removeprefix("www."), url


def email_address(value):
    value = value.strip().lower()
    if len(value) > 254 or not EMAIL.fullmatch(value) or ".." in value:
        raise HTTPException(422, "Enter a valid email address")
    local, host = value.rsplit("@", 1)
    if (
        len(local) > 64
        or local.startswith(".")
        or local.endswith(".")
        or any(part.startswith("-") or part.endswith("-") for part in host.split("."))
    ):
        raise HTTPException(422, "Enter a valid email address")
    return value


def mask_email(value):
    local, host = value.rsplit("@", 1)
    return local[:1] + "***@" + host


def secret():
    value = get_settings().verification_secret.get_secret_value()
    if len(value) < 32:
        raise HTTPException(503, "Email verification is not configured yet")
    return value.encode()


def otp_hash(row, code):
    return hmac.new(
        secret(), f"{row.id}:{row.domain}:{row.email}:{code}".encode(), hashlib.sha256
    ).hexdigest()


def rate_limit(session, identity, operation, limit, seconds=3600):
    """Persistent atomic counters, including failed verification attempts."""
    now = datetime.now(UTC)
    start = int(now.timestamp()) // seconds * seconds
    key = f"customer-{operation}:{start}:{digest(identity)}"
    statement = insert(AdmissionBucket).values(
        bucket_key=key, count=1, expires_at=datetime.fromtimestamp(start + seconds, UTC)
    )
    count = session.scalar(
        statement.on_conflict_do_update(
            index_elements=[AdmissionBucket.bucket_key], set_={"count": AdmissionBucket.count + 1}
        ).returning(AdmissionBucket.count)
    )
    session.commit()
    if count > limit:
        raise HTTPException(429, "Too many requests. Please wait before trying again.")


def send_code(email, code, domain):
    settings = get_settings()
    password = settings.smtp_password.get_secret_value()
    if not settings.smtp_username or not password or not settings.smtp_from:
        raise HTTPException(503, "Email delivery is not configured yet")
    message = EmailMessage()
    message["Subject"] = "Your Aglanetic verification code"
    message["From"] = settings.smtp_from
    message["To"] = email
    message.set_content(
        f"Your verification code is {code}.\n\nIt allows a read-only Aglanetic scan of {domain}. It expires in 10 minutes.\n\nOnly enter it on the Aglanetic website if you requested this scan. Do not forward or share it. If you did not request this, ignore this email. No scan starts until verification succeeds."
    )
    try:
        context = ssl.create_default_context()
        if settings.smtp_starttls:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
                server.login(settings.smtp_username, password)
                server.send_message(message)
        else:
            with smtplib.SMTP_SSL(
                settings.smtp_host, settings.smtp_port, timeout=15, context=context
            ) as server:
                server.login(settings.smtp_username, password)
                server.send_message(message)
    except (smtplib.SMTPException, OSError) as exc:
        raise HTTPException(
            503, "The verification email could not be delivered. Please retry later."
        ) from exc


def request_code(session, website_url, identity, email=None, candidate_id=None):
    secret()  # Fail closed before issuing a challenge.
    domain, url = domain_url(website_url)
    rate_limit(session, identity, "email-ip", 8)
    rate_limit(session, domain, "email-domain", 12)
    now = datetime.now(UTC)
    if candidate_id:
        row = session.scalar(
            select(WebsiteVerification)
            .where(WebsiteVerification.id == candidate_id)
            .with_for_update()
        )
        if (
            not row
            or not row.discovered
            or row.domain != domain
            or row.identity_hash != digest(identity)
            or row.verified_at
            or row.otp_expires_at <= now
        ):
            raise HTTPException(422, "The published email selection has expired. Find it again.")
    else:
        address = email_address(email or "")
        # Any mailbox may verify; the session stays bound to this one website.
        # Local development still marks other-domain mailboxes as development sessions.
        relaxed = address.rsplit("@", 1)[1] != domain and dev_shortcut_enabled()
        row = WebsiteVerification(
            domain=domain,
            website_url=url,
            email=address,
            identity_hash=digest(identity),
            discovered=False,
            verification_method="DEV_EMAIL_OTP" if relaxed else "EMAIL_OTP",
            otp_expires_at=now,
        )
        session.add(row)
        session.flush()
    rate_limit(session, row.email, "email-recipient", 4)
    rate_limit(session, row.email, "email-cooldown", 1, seconds=60)
    rate_limit(session, "all-mail", "email-daily", 100, seconds=86400)
    # rate_limit commits; re-lock existing challenge before changing it.
    row = session.scalar(
        select(WebsiteVerification).where(WebsiteVerification.id == row.id).with_for_update()
    )
    code = f"{secrets.randbelow(1_000_000):06d}"
    row.otp_expires_at = now + timedelta(minutes=10)
    row.attempts = 0
    row.otp_digest = otp_hash(row, code)
    row.verified_at = None
    session.commit()
    try:
        send_code(row.email, code, domain)
    except HTTPException:
        row.otp_digest = None
        session.commit()
        raise
    return {"challenge_id": row.id, "email_hint": mask_email(row.email), "expires_in": 600}


def verify_code(session, challenge_id, code, identity):
    rate_limit(session, identity, "otp-check", 30)
    row = session.scalar(
        select(WebsiteVerification).where(WebsiteVerification.id == challenge_id).with_for_update()
    )
    now = datetime.now(UTC)
    if (
        not row
        or row.identity_hash != digest(identity)
        or not row.otp_digest
        or row.verified_at
        or row.otp_expires_at <= now
        or row.attempts >= 5
    ):
        raise HTTPException(400, "Code invalid or expired. Request a new code.")
    row.attempts += 1
    if not re.fullmatch(r"[0-9]{6}", code) or not hmac.compare_digest(
        row.otp_digest, otp_hash(row, code)
    ):
        session.commit()
        raise HTTPException(400, "Code invalid or expired. Request a new code.")
    token = secrets.token_urlsafe(32)
    row.verified_at = now
    row.otp_digest = None
    row.session_digest = digest(token)
    row.session_expires_at = now + timedelta(days=30)
    session.commit()
    return row, token


def verified_session(session, token, domain=None):
    if not token or len(token) > 128:
        raise HTTPException(401, "Verify your email to continue")
    row = session.scalar(
        select(WebsiteVerification).where(
            WebsiteVerification.session_digest == digest(token),
            WebsiteVerification.verified_at.is_not(None),
            WebsiteVerification.session_expires_at > datetime.now(UTC),
        )
    )
    if not row or (domain is not None and row.domain != domain):
        raise HTTPException(401, "Verify an email for this website to continue")
    if row.verification_method in {"DEV_SHORTCUT", "DEV_EMAIL_OTP"} and not is_dev_session(row):
        raise HTTPException(401, "Development access is disabled. Verify your email.")
    return row


def active_order(session, verification):
    return session.scalar(
        select(DomainOrder)
        .where(
            DomainOrder.domain == verification.domain,
            DomainOrder.email == verification.email,
            DomainOrder.status == "PAID",
            DomainOrder.livemode == get_settings().stripe_live_mode,
            DomainOrder.rescan_until > datetime.now(UTC),
        )
        .order_by(DomainOrder.paid_at.desc())
    )


def report_access(session, token, cookie, paid=False):
    from app.models.domain import Project, Scan
    from app.services.reports import ReportService

    reports = ReportService(session)
    share = reports.shared_link(token)
    scan = session.get(Scan, share.scan_id)
    project = session.get(Project, scan.project_id)
    domain, _ = domain_url(project.website_url)
    verification = verified_session(session, cookie, domain)
    if share.verification_id and not is_dev_session(verification):
        owner = session.get(WebsiteVerification, share.verification_id)
        if owner.email != verification.email:
            raise HTTPException(403, "This report belongs to another verified mailbox")
    order = session.get(DomainOrder, share.domain_order_id) if share.domain_order_id else None
    if not order or order.status != "PAID":
        grant = active_order(session, verification)
        if grant:
            share.domain_order_id = grant.id
            share.expires_at = datetime.now(UTC) + timedelta(days=get_settings().paid_report_days)
            session.commit()
            order = grant
    unlocked = bool(
        order
        and order.status == "PAID"
        and order.domain == domain
        and order.email == verification.email
        and order.livemode == get_settings().stripe_live_mode
    )
    if paid and not unlocked and not development_report_unlocked(verification, share):
        raise HTTPException(402, "Unlock the full report for $19 to access this feature")
    return verification, share, order if unlocked else None


def bind_share(session, token, verification, order=None):
    from app.services.reports import ReportService

    share = ReportService(session).shared_link(token)
    share.verification_id = verification.id
    if order:
        share.domain_order_id = order.id
        share.expires_at = datetime.now(UTC) + timedelta(days=get_settings().paid_report_days)
    session.commit()
    return share


async def discover_contact_emails(website_url, settings=None, transport=None):
    """Only public, robots-permitted same-site pages; no guessed addresses."""
    settings = settings or get_settings()
    _, url = domain_url(website_url)
    crawler = WebsiteCrawler(url, settings.model_copy(update={"crawl_allow_subdomains": False}))
    if transport is not None:
        from app.engines.crawling.transport import Fetcher

        await crawler.fetcher.close()
        crawler.fetcher = Fetcher(crawler.scope, crawler.settings, transport)
    found = set()
    try:
        async with asyncio.timeout(20):
            handler = await crawler.robots_for(crawler.scope.start)
            if not handler.permits(crawler.scope.start):
                raise HTTPException(
                    422,
                    "Contact discovery is restricted by the website. Use a matching domain email or contact us.",
                )
            crawler.fetcher.permit = crawler.permitted
            queue = [crawler.scope.start]
            visited = set()
            while queue and len(visited) < 4:
                target = queue.pop(0)
                if target in visited:
                    continue
                visited.add(target)
                try:
                    response = await crawler.fetcher.get(target, 128_000)
                    if response.status != 200 or "html" not in response.content_type:
                        continue
                    soup = BeautifulSoup(response.body, "html.parser")
                    for tag in soup(["script", "style"]):
                        tag.decompose()
                    candidates = EMAIL.findall(soup.get_text(" ", strip=True))
                    for link in soup.find_all("a", href=True):
                        href = str(link["href"])
                        if href.lower().startswith("mailto:"):
                            candidates.extend(EMAIL.findall(href.split("?", 1)[0]))
                        elif len(visited) == 1 and re.search(
                            r"contact|about",
                            link.get_text(" ", strip=True) + " " + href,
                            re.IGNORECASE,
                        ):
                            try:
                                destination = crawler.scope.accept(urljoin(response.url, href))
                                if destination not in visited and len(queue) < 3:
                                    queue.append(destination)
                            except ValueError:
                                pass
                    for candidate in candidates:
                        try:
                            found.add(email_address(candidate))
                        except HTTPException:
                            pass
                except (ValueError, OSError, TimeoutError, httpx.HTTPError):
                    continue
    finally:
        await crawler.fetcher.close()
    return sorted(found)[:5]


def customer_scan(session, website_url, identity, cookie):
    from app.models.domain import ReportShare, Scan
    from app.services.audits import AuditService

    domain, url = domain_url(website_url)
    verification = verified_session(session, cookie, domain)
    rate_limit(session, identity, "scan-request", 20)
    from app.repositories.records import Records

    Records(session).admission_lock()
    order = active_order(session, verification)
    prior = session.scalar(
        select(Scan)
        .join(ReportShare, ReportShare.scan_id == Scan.id)
        .join(WebsiteVerification, WebsiteVerification.id == ReportShare.verification_id)
        .where(
            WebsiteVerification.domain == domain, WebsiteVerification.email == verification.email
        )
        .order_by(Scan.created_at.desc())
        .limit(1)
    )
    usable = prior and any(
        str(check.get("rule", "")).removeprefix("render.")
        in {"page.title", "page.h1", "page.meta_description", "schema.syntax"}
        and check.get("status") in {"PASS", "FAIL"}
        for check in (prior.audit_summary or {}).get("checks", [])
    )
    pending = prior and prior.status.value in {"PENDING", "RUNNING"}
    if not dev_shortcut_enabled() and not order and prior and (usable or pending):
        token = secrets.token_urlsafe(32)
        share = ReportShare(
            scan_id=prior.id,
            token_digest=digest(token),
            expires_at=datetime.now(UTC) + timedelta(days=7),
            verification_id=verification.id,
        )
        session.add(share)
        session.commit()
        return prior, token, share.expires_at, False
    scan, token, _expires = AuditService(session).create_free_scan(url, identity)
    share = bind_share(session, token, verification, order)
    return scan, token, share.expires_at, True
