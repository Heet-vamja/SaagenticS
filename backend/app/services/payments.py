"""Stripe Checkout transport and signature-verified, idempotent fulfillment."""

import hashlib
import hmac
import json
import time
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from fastapi import HTTPException
from sqlalchemy import select

from app.core.config import get_settings
from app.models.domain import DomainOrder, PaymentEvent, Project, ReportShare, Scan, ScanStatus
from app.repositories.records import Records
from app.services.website_access import rate_limit, report_access


def create_stripe_session(data, key, idempotency_key):
    try:
        with httpx.Client(trust_env=False, timeout=15) as client:
            response = client.post(
                "https://api.stripe.com/v1/checkout/sessions",
                data=data,
                headers={"Authorization": f"Bearer {key}", "Idempotency-Key": idempotency_key},
            )
            response.raise_for_status()
            result = response.json()
            if (
                not isinstance(result.get("id"), str)
                or urlsplit(result.get("url", "")).hostname != "checkout.stripe.com"
            ):
                raise ValueError("Unexpected Checkout response")
            return result
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        raise HTTPException(
            503, "Checkout is unavailable. No report was unlocked. Please retry later."
        ) from exc


def checkout(session, token, cookie, identity):
    verification, share, existing = report_access(session, token, cookie)
    settings = get_settings()
    key = settings.stripe_secret_key.get_secret_value()
    if not key or not settings.stripe_webhook_secret.get_secret_value():
        raise HTTPException(503, "Payments are not configured yet")
    if not key.startswith("sk_live_" if settings.stripe_live_mode else "sk_test_"):
        raise HTTPException(503, "Stripe key and payment environment do not match")
    if existing:
        raise HTTPException(409, "This report is already unlocked")
    scan = session.get(Scan, share.scan_id)
    if scan.status in {ScanStatus.PENDING, ScanStatus.RUNNING}:
        raise HTTPException(409, "Wait for the report before purchasing")
    from app.services.free_reports import free_report

    if free_report(scan, session.get(Project, scan.project_id), []).score is None:
        raise HTTPException(
            422,
            "There is not enough inspected page evidence to sell a full report. Retry the scan instead.",
        )
    rate_limit(session, identity, "checkout", 10)
    Records(session).admission_lock()
    # A fixed server-side product. Never accept price, currency or domain from the client.
    order = session.scalar(
        select(DomainOrder)
        .where(
            DomainOrder.share_id == share.id,
            DomainOrder.email == verification.email,
            DomainOrder.domain == verification.domain,
            DomainOrder.status == "PENDING",
            DomainOrder.livemode == settings.stripe_live_mode,
        )
        .order_by(DomainOrder.created_at.desc())
    )
    if not order:
        order = DomainOrder(
            verification_id=verification.id,
            share_id=share.id,
            domain=verification.domain,
            email=verification.email,
            livemode=settings.stripe_live_mode,
        )
        session.add(order)
        session.commit()
    base = settings.public_site_url.rstrip("/")
    parsed = urlsplit(base)
    if (
        parsed.scheme not in {"https", "http"}
        or not parsed.netloc
        or parsed.query
        or parsed.fragment
    ):
        raise HTTPException(503, "Public checkout return URL is not configured correctly")
    if settings.stripe_live_mode and (
        parsed.scheme != "https" or not settings.verification_cookie_secure
    ):
        raise HTTPException(503, "Live payments require HTTPS and secure verification cookies")
    result = create_stripe_session(
        {
            "mode": "payment",
            "payment_method_types[0]": "card",
            "customer_email": verification.email,
            "client_reference_id": str(order.id),
            "metadata[order_id]": str(order.id),
            "line_items[0][quantity]": "1",
            "line_items[0][price_data][currency]": "usd",
            "line_items[0][price_data][unit_amount]": "1900",
            "line_items[0][price_data][product_data][name]": f"Aglanetic full report — {verification.domain}",
            "line_items[0][price_data][product_data][description]": "Full static report, fix guidance and 30 days of same-domain re-scans. AI agent testing is coming Christmas 2026.",
            "success_url": f"{base}/free-reports/{token}?checkout=success",
            "cancel_url": f"{base}/free-reports/{token}?checkout=cancelled",
        },
        key,
        f"domain-report-{order.id}",
    )
    order.checkout_session_id = result["id"]
    session.commit()
    return {"url": result["url"]}


def verify_event(body, signature, now=None):
    secret = get_settings().stripe_webhook_secret.get_secret_value()
    if not secret:
        raise HTTPException(503, "Stripe webhooks are not configured")
    try:
        fields = [part.split("=", 1) for part in signature.split(",")]
        timestamp = next(int(value) for name, value in fields if name == "t")
        if abs((now if now is not None else time.time()) - timestamp) > 300:
            raise ValueError("Expired signature")
        expected = hmac.new(
            secret.encode(), str(timestamp).encode() + b"." + body, hashlib.sha256
        ).hexdigest()
        if not any(name == "v1" and hmac.compare_digest(expected, value) for name, value in fields):
            raise ValueError("Invalid signature")
        event = json.loads(body)
        if (
            not isinstance(event, dict)
            or not isinstance(event.get("id"), str)
            or len(event["id"]) > 255
            or not isinstance(event.get("data"), dict)
            or not isinstance(event.get("data", {}).get("object"), dict)
            or event.get("livemode") is not get_settings().stripe_live_mode
        ):
            raise ValueError("Wrong event environment")
        return event
    except (ValueError, TypeError, StopIteration) as exc:
        raise HTTPException(400, "Invalid Stripe webhook signature or payload") from exc


def process_event(session, event):
    # Existing short database advisory lock serializes duplicate/concurrent deliveries.
    Records(session).admission_lock()
    if session.get(PaymentEvent, event["id"]):
        return {"received": True}
    obj = event.get("data", {}).get("object", {})
    kind = event.get("type")
    intent = obj.get("payment_intent")
    revoked = kind == "charge.dispute.created" or (
        kind == "charge.refunded" and obj.get("refunded") is True
    )
    if revoked and isinstance(intent, str):
        order = session.scalar(
            select(DomainOrder).where(DomainOrder.payment_intent_id == intent).with_for_update()
        )
        if order:
            order.status = "REVOKED"
    elif kind in {"checkout.session.completed", "checkout.session.async_payment_succeeded"}:
        try:
            order_id = UUID(str(obj.get("client_reference_id")))
        except ValueError:
            raise HTTPException(400, "Checkout order reference is invalid") from None
        order = session.scalar(
            select(DomainOrder).where(DomainOrder.id == order_id).with_for_update()
        )
        if not order:
            raise HTTPException(400, "Unknown checkout order")
        if (
            obj.get("id") != order.checkout_session_id
            or obj.get("metadata", {}).get("order_id") != str(order.id)
            or obj.get("amount_total") != 1900
            or obj.get("currency") != "usd"
            or obj.get("mode") != "payment"
            or order.livemode != event["livemode"]
        ):
            raise HTTPException(400, "Checkout does not match the expected order")
        if obj.get("payment_status") == "paid" and order.status == "PENDING":
            if not isinstance(intent, str) or len(intent) > 255:
                raise HTTPException(400, "Checkout payment reference is invalid")
            blocked = session.scalar(
                select(PaymentEvent.id)
                .where(PaymentEvent.payment_intent_id == intent, PaymentEvent.revoked.is_(True))
                .limit(1)
            )
            if blocked:
                order.status = "REVOKED"
            else:
                now = datetime.now(UTC)
                order.status = "PAID"
                order.payment_intent_id = intent
                order.paid_at = now
                order.rescan_until = now + timedelta(days=30)
                share = session.get(ReportShare, order.share_id)
                share.domain_order_id = order.id
                share.expires_at = now + timedelta(days=get_settings().paid_report_days)
    session.add(
        PaymentEvent(
            id=event["id"],
            payment_intent_id=intent if isinstance(intent, str) else None,
            revoked=revoked,
        )
    )
    session.commit()
    return {"received": True}
