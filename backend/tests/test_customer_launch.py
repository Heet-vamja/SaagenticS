"""Deterministic verification/Checkout tests: no email, charge, browser or model calls."""

import asyncio
import hashlib
import hmac
import json
import time
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import func, select

from app.core.config import get_settings
from app.engines.static_audit.checks import Check
from app.models.domain import (
    Category,
    DomainOrder,
    Finding,
    ReportShare,
    Scan,
    ScanStatus,
    Severity,
    WebsiteVerification,
)
from app.services import payments
from app.services import website_access as access


@pytest.fixture
def launch(client, session, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "customer_mode_enabled", True)
    monkeypatch.setattr(settings, "app_environment", "production")
    monkeypatch.setattr(settings, "dev_email_shortcut_enabled", False)
    monkeypatch.setattr(
        settings, "verification_secret", SecretStr("test-only-verification-secret-32-characters")
    )
    monkeypatch.setattr(settings, "verification_cookie_secure", False)
    monkeypatch.setattr(settings, "stripe_secret_key", SecretStr("sk_test_fixture"))
    monkeypatch.setattr(settings, "stripe_webhook_secret", SecretStr("whsec_fixture"))
    monkeypatch.setattr(settings, "stripe_live_mode", False)
    monkeypatch.setattr(settings, "public_site_url", "http://localhost:3000")
    sent = []
    monkeypatch.setattr(
        access, "send_code", lambda email, code, domain: sent.append((email, code, domain))
    )
    calls = []

    def stripe(data, key, idempotency):
        calls.append((data, idempotency))
        return {
            "id": "cs_test_" + data["client_reference_id"],
            "url": "https://checkout.stripe.com/c/pay/fixture",
        }

    monkeypatch.setattr(payments, "create_stripe_session", stripe)
    return client, session, sent, calls


def verify(launch, website="https://fixture.example/", email="owner@fixture.example"):
    client, _session, sent, _calls = launch
    response = client.post(
        "/api/v1/verification/request", json={"website_url": website, "email": email}
    )
    assert response.status_code == 200, response.json()
    challenge = response.json()["challenge_id"]
    result = client.post(
        "/api/v1/verification/verify", json={"challenge_id": challenge, "code": sent[-1][1]}
    )
    assert result.status_code == 200, result.json()
    assert "httponly" in result.headers["set-cookie"].lower()
    assert "samesite=lax" in result.headers["set-cookie"].lower()
    return challenge


def report(launch):
    client, session, _sent, _calls = launch
    verify(launch)
    response = client.post("/api/v1/free-scans", json={"website_url": "https://fixture.example/"})
    assert response.status_code == 201, response.json()
    token = response.json()["report_path"].rsplit("/", 1)[-1]
    share = session.scalar(
        select(ReportShare).where(ReportShare.token_digest == access.digest(token))
    )
    scan = session.get(Scan, share.scan_id)
    scan.status = ScanStatus.COMPLETED
    scan.pages_crawled = 1
    scan.audit_summary = {
        "scan_mode": "FREE_REPORT",
        "version": "static-v3",
        "phase": "COMPLETED",
        "checks": [
            Check(
                "page.title",
                "Readability",
                "PASS",
                "Title present",
                "",
                url="https://fixture.example/",
            ).dump(),
            Check(
                "semantic.buttons",
                "Actionability",
                "FAIL",
                "Unnamed control",
                "A control has no accessible name",
                "Add a descriptive label",
                url="https://fixture.example/",
                evidence={"examples": [{"example": "<button></button>"}]},
            ).dump(),
        ],
    }
    session.add(
        Finding(
            scan_id=scan.id,
            category=Category.INTERACTABILITY,
            severity=Severity.HIGH,
            title="Unnamed control",
            description="A control has no accessible name",
            recommendation="Add a descriptive label",
            evidence={
                "rule": "semantic.buttons",
                "url": "https://fixture.example/",
                "examples": [{"example": "<button></button>"}],
            },
        )
    )
    session.commit()
    return token, scan


def event_for(order, **overrides):
    obj = {
        "id": order.checkout_session_id,
        "client_reference_id": str(order.id),
        "metadata": {"order_id": str(order.id)},
        "amount_total": 1900,
        "currency": "usd",
        "mode": "payment",
        "payment_status": "paid",
        "payment_intent": "pi_fixture_" + str(order.id),
    }
    obj.update(overrides)
    return {
        "id": "evt_" + uuid4().hex,
        "livemode": False,
        "type": "checkout.session.completed",
        "data": {"object": obj},
    }


def webhook(client, event, timestamp=None, tamper=False):
    body = json.dumps(event, separators=(",", ":")).encode()
    timestamp = int(time.time()) if timestamp is None else timestamp
    signature = hmac.new(
        b"whsec_fixture", str(timestamp).encode() + b"." + body, hashlib.sha256
    ).hexdigest()
    return client.post(
        "/api/v1/webhooks/stripe",
        content=body + (b" " if tamper else b""),
        headers={
            "Stripe-Signature": f"t={timestamp},v1={signature}",
            "Content-Type": "application/json",
        },
    )


@pytest.mark.parametrize(
    "email",
    [
        "owner@fixture.evil.example",
        "owner@fixture.example.evil.com",
        "fixture.example@gmail.com",
        "owner@fixture.com",
        "owner@evilfixture.example",
    ],
)
def test_any_mailbox_can_verify_but_only_for_the_requested_website(launch, email):
    client, session, sent, _ = launch
    response = client.post(
        "/api/v1/verification/request",
        json={"website_url": "https://fixture.example", "email": email},
    )
    assert response.status_code == 200, response.text
    assert sent[-1][0] == email
    # Requesting a code never starts a scan; the OTP must still be entered.
    assert session.scalar(select(func.count()).select_from(Scan)) == 0
    row = session.get(WebsiteVerification, UUID(response.json()["challenge_id"]))
    assert row.domain == "fixture.example" and row.verification_method == "EMAIL_OTP"
    verified = client.post(
        "/api/v1/verification/verify",
        json={"challenge_id": response.json()["challenge_id"], "code": sent[-1][1]},
    )
    assert verified.status_code == 200, verified.text
    status = "/api/v1/verification/status"
    assert client.get(status, params={"website_url": "https://fixture.example"}).json()["verified"]
    assert not client.get(status, params={"website_url": "https://other.example"}).json()[
        "verified"
    ]


def test_otp_one_use_hashing_expiry_and_attempt_limit(launch):
    client, session, sent, _ = launch
    response = client.post(
        "/api/v1/verification/request",
        json={"website_url": "https://fixture.example", "email": "owner@fixture.example"},
    )
    challenge = response.json()["challenge_id"]
    row = session.get(WebsiteVerification, UUID(challenge))
    assert row.otp_digest != sent[-1][1]
    code = sent[-1][1]
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(5):
        assert (
            client.post(
                "/api/v1/verification/verify", json={"challenge_id": challenge, "code": wrong}
            ).status_code
            == 400
        )
    assert (
        client.post(
            "/api/v1/verification/verify", json={"challenge_id": challenge, "code": code}
        ).status_code
        == 400
    )
    session.refresh(row)
    assert row.attempts == 5
    # A separate authorized mailbox can verify while the first address is cooling down.
    challenge = verify(launch, email="second@fixture.example")
    assert (
        client.post(
            "/api/v1/verification/verify", json={"challenge_id": challenge, "code": sent[-1][1]}
        ).status_code
        == 400
    )
    assert (
        client.get(
            "/api/v1/verification/status", params={"website_url": "https://other.example"}
        ).json()["verified"]
        is False
    )


def test_expired_code_cannot_verify(launch):
    client, session, sent, _ = launch
    response = client.post(
        "/api/v1/verification/request",
        json={"website_url": "https://fixture.example", "email": "owner@fixture.example"},
    )

    row = session.get(WebsiteVerification, UUID(response.json()["challenge_id"]))
    row.otp_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    session.commit()
    assert (
        client.post(
            "/api/v1/verification/verify", json={"challenge_id": str(row.id), "code": sent[-1][1]}
        ).status_code
        == 400
    )


def test_no_scan_or_legacy_workspace_bypass_without_verification(launch):
    client, session, _, _ = launch
    assert (
        client.post(
            "/api/v1/free-scans", json={"website_url": "https://fixture.example"}
        ).status_code
        == 401
    )
    for path in (
        "/api/v1/projects",
        "/api/v1/scans",
        "/api/v1/agent-config",
        "/api/v1/scans/" + str(uuid4()) + "/report",
        "/api/v1/shares/arbitrary",
    ):
        assert client.get(path).status_code == 403
    assert client.post("/api/v1/scans", json={"project_id": str(uuid4())}).status_code == 403
    assert session.scalar(select(func.count()).select_from(Scan)) == 0


def test_published_email_selection_is_server_bound(launch, monkeypatch):
    client, _session, sent, _ = launch

    async def found(*_args):
        return ["contact@gmail.com"]

    monkeypatch.setattr(access, "discover_contact_emails", found)
    result = client.post(
        "/api/v1/verification/discover", json={"website_url": "https://fixture.example"}
    )
    assert result.status_code == 200
    assert "contact@gmail.com" not in result.text
    candidate = result.json()["candidates"][0]["id"]
    assert (
        client.post(
            "/api/v1/verification/request",
            json={"website_url": "https://other.example", "candidate_id": candidate},
        ).status_code
        == 422
    )
    challenge = client.post(
        "/api/v1/verification/request",
        json={"website_url": "https://fixture.example", "candidate_id": candidate},
    )
    assert challenge.status_code == 200
    assert sent[-1][0] == "contact@gmail.com"


def test_discovery_respects_robots_and_external_domains(monkeypatch):
    settings = get_settings().model_copy(update={"crawl_min_delay": 0})
    calls = []

    def serve(request):
        calls.append(str(request.url))
        if request.url.path == "/robots.txt":
            return httpx.Response(200, stream=httpx.ByteStream(b"User-agent: *\nAllow: /"))
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            stream=httpx.ByteStream(
                b'<a href="mailto:hello@fixture.example">Email</a><a href="https://evil.example/contact">Contact</a>'
            ),
        )

    found = asyncio.run(
        access.discover_contact_emails(
            "https://fixture.example", settings, httpx.MockTransport(serve)
        )
    )
    assert found == ["hello@fixture.example"]
    assert all(url.startswith("https://fixture.example/") for url in calls)
    calls.clear()

    def deny(request):
        calls.append(request.url.path)
        return httpx.Response(200, stream=httpx.ByteStream(b"User-agent: *\nDisallow: /"))

    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        asyncio.run(
            access.discover_contact_emails(
                "https://fixture.example", settings, httpx.MockTransport(deny)
            )
        )
    assert calls == ["/robots.txt"]


def test_preview_is_server_redacted_and_paid_endpoints_are_locked(launch):
    client, session, _, _ = launch
    token, _scan = report(launch)
    result = client.get(f"/api/v1/free-reports/{token}?checkout=success")
    assert result.status_code == 200
    data = result.json()
    assert data["score"] is not None
    assert data["full_report_unlocked"] is False
    assert data["checks"] == []
    assert data["insights"][0]["recommendation"] == "Add a descriptive label"
    assert data["insights"][0]["evidence_summary"] is None
    assert "<button>" not in result.text
    for suffix in ("fix-center", "fix-pack.zip", "export.pdf", "assets/llms.txt"):
        assert client.get(f"/api/v1/free-reports/{token}/{suffix}").status_code == 402
    assert client.post(f"/api/v1/free-reports/{token}/rescan").status_code == 402
    second = client.post("/api/v1/free-scans", json={"website_url": "https://fixture.example/"})
    assert second.status_code == 201
    assert session.scalar(select(func.count()).select_from(Scan)) == 1
    client.cookies.clear()
    assert client.get(f"/api/v1/free-reports/{token}").status_code == 401
    assert client.get(f"/api/v1/free-reports/{token}/verification-target").status_code == 200


def test_stripe_webhook_unlocks_once_and_grants_same_domain_rescans(launch):
    client, session, _, calls = launch
    token, _scan = report(launch)
    result = client.post(f"/api/v1/free-reports/{token}/checkout")
    assert result.status_code == 200, result.json()
    order = session.scalar(select(DomainOrder))
    assert calls[0][0]["line_items[0][price_data][unit_amount]"] == "1900"
    event = event_for(order)
    assert webhook(client, event).status_code == 200
    session.refresh(order)
    until = order.rescan_until
    assert order.status == "PAID"
    assert timedelta(days=29) < until - datetime.now(UTC) <= timedelta(days=30)
    assert webhook(client, event).status_code == 200
    duplicate = event_for(order)
    assert webhook(client, duplicate).status_code == 200
    session.refresh(order)
    assert order.rescan_until == until
    assert client.get(f"/api/v1/free-reports/{token}").json()["full_report_unlocked"] is True
    assert client.get(f"/api/v1/free-reports/{token}/fix-center").status_code == 200
    rescan = client.post(f"/api/v1/free-reports/{token}/rescan")
    assert rescan.status_code == 201, rescan.json()
    next_token = rescan.json()["report_path"].rsplit("/", 1)[-1]
    assert client.get(f"/api/v1/free-reports/{next_token}").json()["full_report_unlocked"] is True
    assert (
        client.post(
            "/api/v1/free-scans", json={"website_url": "https://other.example/"}
        ).status_code
        == 401
    )
    order.rescan_until = datetime.now(UTC) - timedelta(seconds=1)
    session.commit()
    assert client.post(f"/api/v1/free-reports/{token}/rescan").status_code == 402
    # Previously bought report remains available after only the rescan window expires.
    assert client.get(f"/api/v1/free-reports/{token}").json()["full_report_unlocked"] is True


@pytest.mark.parametrize(
    "change", [{"amount_total": 1}, {"currency": "eur"}, {"payment_status": "unpaid"}]
)
def test_wrong_amount_currency_or_unpaid_checkout_never_unlocks(launch, change):
    client, session, _, _ = launch
    token, _ = report(launch)
    assert client.post(f"/api/v1/free-reports/{token}/checkout").status_code == 200
    order = session.scalar(select(DomainOrder))
    response = webhook(client, event_for(order, **change))
    assert response.status_code in (200, 400)
    assert client.get(f"/api/v1/free-reports/{token}").json()["full_report_unlocked"] is False


def test_forged_expired_and_live_mode_mismatched_webhooks_are_rejected(launch):
    client, session, _, _ = launch
    token, _ = report(launch)
    client.post(f"/api/v1/free-reports/{token}/checkout")
    order = session.scalar(select(DomainOrder))
    event = event_for(order)
    assert webhook(client, event, tamper=True).status_code == 400
    assert webhook(client, event, timestamp=int(time.time()) - 600).status_code == 400
    event["livemode"] = True
    assert webhook(client, event).status_code == 400
    assert client.get(f"/api/v1/free-reports/{token}").json()["full_report_unlocked"] is False


def test_refund_before_or_after_fulfillment_cannot_grant_paid_access(launch):
    client, session, _, _ = launch
    token, _ = report(launch)
    client.post(f"/api/v1/free-reports/{token}/checkout")
    order = session.scalar(select(DomainOrder))
    paid = event_for(order)
    refund = {
        "id": "evt_refund",
        "livemode": False,
        "type": "charge.refunded",
        "data": {
            "object": {"payment_intent": paid["data"]["object"]["payment_intent"], "refunded": True}
        },
    }
    assert webhook(client, refund).status_code == 200
    assert webhook(client, paid).status_code == 200
    assert client.get(f"/api/v1/free-reports/{token}").json()["full_report_unlocked"] is False


def test_configuration_missing_fails_closed(launch, monkeypatch):
    client, session, _, _ = launch
    monkeypatch.setattr(get_settings(), "verification_secret", SecretStr(""))
    response = client.post(
        "/api/v1/verification/request",
        json={"website_url": "https://fixture.example", "email": "owner@fixture.example"},
    )
    assert response.status_code == 503
    assert session.scalar(select(func.count()).select_from(WebsiteVerification)) == 0


def test_email_failure_invalidates_the_challenge_without_starting_scan(launch, monkeypatch):
    from fastapi import HTTPException

    client, session, _, _ = launch

    def fail(*args):
        raise HTTPException(503, "Email unavailable")

    monkeypatch.setattr(access, "send_code", fail)
    response = client.post(
        "/api/v1/verification/request",
        json={"website_url": "https://fixture.example", "email": "owner@fixture.example"},
    )
    assert response.status_code == 503
    row = session.scalar(select(WebsiteVerification))
    assert row.otp_digest is None
    assert session.scalar(select(func.count()).select_from(Scan)) == 0


def test_delivery_cooldown_and_session_expiry_are_enforced(launch):
    client, session, sent, _ = launch
    challenge = verify(launch)
    repeated = client.post(
        "/api/v1/verification/request",
        json={"website_url": "https://fixture.example", "email": "owner@fixture.example"},
    )
    assert repeated.status_code == 429
    assert len(sent) == 1
    row = session.get(WebsiteVerification, UUID(challenge))
    row.session_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    session.commit()
    assert (
        client.post(
            "/api/v1/free-scans", json={"website_url": "https://fixture.example"}
        ).status_code
        == 401
    )


def test_another_verified_mailbox_cannot_open_or_buy_someone_elses_report(launch):
    client, _session, _, _ = launch
    token, _ = report(launch)
    verify(launch, email="colleague@fixture.example")
    assert client.get(f"/api/v1/free-reports/{token}").status_code == 403
    assert client.post(f"/api/v1/free-reports/{token}/checkout").status_code == 403


def test_paid_refund_revokes_existing_report_and_rescans(launch):
    client, session, _, _ = launch
    token, _ = report(launch)
    client.post(f"/api/v1/free-reports/{token}/checkout")
    order = session.scalar(select(DomainOrder))
    assert webhook(client, event_for(order)).status_code == 200
    event = {
        "id": "evt_later_refund",
        "livemode": False,
        "type": "charge.refunded",
        "data": {"object": {"payment_intent": order.payment_intent_id, "refunded": True}},
    }
    assert webhook(client, event).status_code == 200
    assert client.get(f"/api/v1/free-reports/{token}").json()["full_report_unlocked"] is False
    assert client.post(f"/api/v1/free-reports/{token}/rescan").status_code == 402


def test_checkout_configuration_pending_scan_and_empty_report_fail_closed(launch, monkeypatch):
    client, session, _, calls = launch
    token, scan = report(launch)
    monkeypatch.setattr(get_settings(), "stripe_secret_key", SecretStr(""))
    assert client.post(f"/api/v1/free-reports/{token}/checkout").status_code == 503
    monkeypatch.setattr(get_settings(), "stripe_secret_key", SecretStr("sk_test_fixture"))
    scan.status = ScanStatus.RUNNING
    session.commit()
    assert client.post(f"/api/v1/free-reports/{token}/checkout").status_code == 409
    scan.status = ScanStatus.FAILED
    scan.audit_summary = {"scan_mode": "FREE_REPORT", "checks": []}
    scan.pages_crawled = 0
    session.commit()
    assert client.post(f"/api/v1/free-reports/{token}/checkout").status_code == 422
    assert calls == []
    # Failed inspections may be retried without buying an empty report.
    assert (
        client.post(
            "/api/v1/free-scans", json={"website_url": "https://fixture.example"}
        ).status_code
        == 201
    )
    assert session.scalar(select(func.count()).select_from(Scan)) == 2


def test_active_domain_purchase_unlocks_existing_preview_alias_without_double_charge(launch):
    client, session, _, calls = launch
    token, _ = report(launch)
    alias = (
        client.post("/api/v1/free-scans", json={"website_url": "https://fixture.example/"})
        .json()["report_path"]
        .rsplit("/", 1)[-1]
    )
    assert client.post(f"/api/v1/free-reports/{token}/checkout").status_code == 200
    order = session.scalar(select(DomainOrder))
    assert webhook(client, event_for(order)).status_code == 200
    assert client.get(f"/api/v1/free-reports/{alias}").json()["full_report_unlocked"] is True
    assert client.post(f"/api/v1/free-reports/{alias}/checkout").status_code == 409
    assert len(calls) == 1


def test_customer_mode_never_probes_the_model(launch, monkeypatch):
    from app import main

    client, _, _, _ = launch

    def forbidden(*args):
        raise AssertionError("Customer release must not call a model provider")

    monkeypatch.setattr(main, "get_agent_provider", forbidden)
    response = client.get("/health/llm")
    assert response.status_code == 503
    assert response.json()["status"] == "coming_soon"


def test_live_key_cannot_accidentally_charge_with_test_configuration(launch, monkeypatch):
    client, _, _, calls = launch
    token, _ = report(launch)
    monkeypatch.setattr(get_settings(), "stripe_secret_key", SecretStr("sk_live_fixture"))
    assert client.post(f"/api/v1/free-reports/{token}/checkout").status_code == 503
    assert calls == []


@pytest.fixture
def dev_launch(launch, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "app_environment", "development")
    monkeypatch.setattr(settings, "dev_email_shortcut_enabled", True)
    monkeypatch.setattr(settings, "dev_access_email", "developer@example.test")
    return launch


def dev_verify(client, website="https://fixture.example"):
    result = client.post(
        "/api/v1/verification/skip",
        json={"website_url": website, "email": "developer@example.test"},
    )
    assert result.status_code == 200, result.json()
    assert result.json()["verified"] is True
    assert result.json()["development_access"] is True
    assert "challenge_id" not in result.json()
    return result


def test_dev_email_skips_domain_email_otp_and_smtp_configuration(dev_launch, monkeypatch):
    client, session, sent, _ = dev_launch
    monkeypatch.setattr(get_settings(), "verification_secret", SecretStr(""))
    dev_verify(client)
    assert sent == []
    row = session.scalar(select(WebsiteVerification))
    assert row.verification_method == "DEV_SHORTCUT"
    assert row.otp_digest is None
    assert session.scalar(select(func.count()).select_from(DomainOrder)) == 0
    assert (
        client.get(
            "/api/v1/verification/status", params={"website_url": "https://fixture.example"}
        ).json()["development_access"]
        is True
    )
    assert (
        client.post("/api/v1/free-scans", json={"website_url": "https://other.example"}).status_code
        == 401
    )


def test_dev_report_fixes_and_rescans_need_no_payment_record(dev_launch):
    client, session, sent, _ = dev_launch
    token, _ = report(dev_launch)
    sent_before = len(sent)
    dev_verify(client)
    assert len(sent) == sent_before
    result = client.get(f"/api/v1/free-reports/{token}")
    assert result.status_code == 200, result.json()
    assert result.json()["full_report_unlocked"] is False
    assert result.json()["development_access"] is True
    assert client.get(f"/api/v1/free-reports/{token}/fix-center").status_code == 402
    assert client.post(f"/api/v1/free-reports/{token}/skip-payment").status_code == 200
    result = client.get(f"/api/v1/free-reports/{token}")
    assert result.json()["full_report_unlocked"] is True
    assert result.json()["development_payment_skipped"] is True
    assert result.json()["checks"]
    assert client.get(f"/api/v1/free-reports/{token}/fix-center").status_code == 200
    assert client.get(f"/api/v1/free-reports/{token}/fix-pack.zip").status_code == 200
    assert client.post(f"/api/v1/free-reports/{token}/rescan").status_code == 201
    assert session.scalar(select(func.count()).select_from(DomainOrder)) == 0


@pytest.mark.parametrize(
    "field,value",
    [
        ("app_environment", "production"),
        ("dev_email_shortcut_enabled", False),
        ("stripe_live_mode", True),
        ("public_site_url", "https://app.example.com"),
    ],
)
def test_dev_shortcut_is_disabled_outside_explicit_local_configuration(
    dev_launch, monkeypatch, field, value
):
    client, _session, sent, _ = dev_launch
    monkeypatch.setattr(get_settings(), field, value)
    result = client.post(
        "/api/v1/verification/request",
        json={"website_url": "https://fixture.example", "email": "developer@example.test"},
    )
    # Any mailbox may request a normal code, but no development shortcut is granted.
    assert result.status_code == 200, result.text
    assert [email for email, _code, _domain in sent] == ["developer@example.test"]
    row = _session.get(WebsiteVerification, UUID(result.json()["challenge_id"]))
    assert row.verification_method == "EMAIL_OTP" and row.verified_at is None
    status = client.get(
        "/api/v1/verification/status", params={"website_url": "https://fixture.example"}
    ).json()
    assert status["verified"] is False
    assert not status.get("development_email")


def test_disabling_dev_mode_revokes_previously_issued_dev_sessions(dev_launch, monkeypatch):
    client, _session, _sent, _ = dev_launch
    dev_verify(client)
    monkeypatch.setattr(get_settings(), "app_environment", "production")
    assert (
        client.post(
            "/api/v1/free-scans", json={"website_url": "https://fixture.example"}
        ).status_code
        == 401
    )
    assert (
        client.get(
            "/api/v1/verification/status", params={"website_url": "https://fixture.example"}
        ).json()["verified"]
        is False
    )


def test_local_dev_normal_otp_supports_personal_email_without_automatic_skip(dev_launch):
    client, session, sent, calls = dev_launch
    token, _ = report(dev_launch)
    client.cookies.clear()
    before = len(sent)
    verify(dev_launch, email="developer+other@example.test")
    assert len(sent) == before + 1
    row = session.scalar(
        select(WebsiteVerification).where(
            WebsiteVerification.email == "developer+other@example.test"
        )
    )
    assert row.verification_method == "DEV_EMAIL_OTP"
    assert client.get(f"/api/v1/free-reports/{token}").json()["full_report_unlocked"] is False
    assert client.post(f"/api/v1/free-reports/{token}/checkout").status_code == 200
    assert len(calls) == 1


def test_dev_request_does_not_automatically_verify_when_smtp_unavailable(dev_launch, monkeypatch):
    from fastapi import HTTPException

    client, _, _, _ = dev_launch

    def unavailable(*args):
        raise HTTPException(503, "SMTP is not configured")

    monkeypatch.setattr(access, "send_code", unavailable)
    result = client.post(
        "/api/v1/verification/request",
        json={"website_url": "https://fixture.example", "email": "developer@example.test"},
    )
    assert result.status_code == 503
    assert (
        client.get(
            "/api/v1/verification/status", params={"website_url": "https://fixture.example"}
        ).json()["verified"]
        is False
    )
    dev_verify(client)


def test_production_disallows_explicit_skips(launch):
    client, _, _, _ = launch
    token, _ = report(launch)
    assert (
        client.post(
            "/api/v1/verification/skip",
            json={"website_url": "https://fixture.example", "email": "developer@example.test"},
        ).status_code
        == 403
    )
    assert client.post(f"/api/v1/free-reports/{token}/skip-payment").status_code == 403


def test_payment_skip_requires_matching_verified_session(dev_launch):
    client, _, _, _ = dev_launch
    token, _ = report(dev_launch)
    client.cookies.clear()
    assert client.post(f"/api/v1/free-reports/{token}/skip-payment").status_code == 401
    dev_verify(client, "https://other.example")
    assert client.post(f"/api/v1/free-reports/{token}/skip-payment").status_code == 401


@pytest.mark.parametrize(
    "website", ["http://127.0.0.1", "http://169.254.169.254", "http://8.8.8.8"]
)
def test_dev_email_does_not_bypass_destination_validation(dev_launch, website):
    client, _session, sent, _ = dev_launch
    result = client.post(
        "/api/v1/verification/request",
        json={"website_url": website, "email": "developer@example.test"},
    )
    assert result.status_code == 422
    assert sent == []


def test_test_mode_payment_cannot_unlock_live_reports(launch, monkeypatch):
    client, session, _, _ = launch
    token, _ = report(launch)
    assert client.post(f"/api/v1/free-reports/{token}/checkout").status_code == 200
    order = session.scalar(select(DomainOrder))
    assert webhook(client, event_for(order)).status_code == 200
    assert client.get(f"/api/v1/free-reports/{token}").json()["full_report_unlocked"] is True
    monkeypatch.setattr(get_settings(), "stripe_live_mode", True)
    assert client.get(f"/api/v1/free-reports/{token}").json()["full_report_unlocked"] is False
    assert client.get(f"/api/v1/free-reports/{token}/fix-center").status_code == 402


def test_development_payment_skip_expires_when_mode_is_disabled(dev_launch, monkeypatch):
    client, _, _, _ = dev_launch
    token, _ = report(dev_launch)  # ordinary, domain-matching OTP session
    assert client.post(f"/api/v1/free-reports/{token}/skip-payment").status_code == 200
    assert client.get(f"/api/v1/free-reports/{token}").json()["full_report_unlocked"] is True
    monkeypatch.setattr(get_settings(), "dev_email_shortcut_enabled", False)
    assert client.get(f"/api/v1/free-reports/{token}").json()["full_report_unlocked"] is False
    assert client.get(f"/api/v1/free-reports/{token}/fix-center").status_code == 402


def test_free_report_exposes_ten_prioritized_solutions_without_paid_details(launch):
    client, session, _, _ = launch
    token, scan = report(launch)
    for index in range(12):
        session.add(
            Finding(
                scan_id=scan.id,
                category=Category.DISCOVERABILITY,
                severity=Severity.MEDIUM,
                title=f"Issue {index}",
                description=f"Observed issue {index}",
                recommendation=f"Fix {index}",
                evidence={
                    "rule": f"fixture.rule.{index}",
                    "url": "https://fixture.example/page",
                    "examples": [{"example": "private raw evidence"}],
                },
            )
        )
    session.commit()
    response = client.get(f"/api/v1/free-reports/{token}")
    assert response.status_code == 200
    data = response.json()
    assert len(data["insights"]) == 10
    assert data["insights"][0]["title"] == "Unnamed control"  # high severity before medium
    assert all(item["recommendation"] for item in data["insights"])
    assert all(
        item["evidence_summary"] is None and item["evidence_url"] is None
        for item in data["insights"]
    )
    assert data["checks"] == []
    assert data["full_report_unlocked"] is False
    assert "private raw evidence" not in response.text
    assert client.get(f"/api/v1/free-reports/{token}/fix-center").status_code == 402


def test_free_fix_preview_is_usable_bounded_and_keeps_full_kit_locked(launch):
    client, session, _, _ = launch
    token, scan = report(launch)
    checks = list(scan.audit_summary["checks"])
    for index in range(6):
        checks.append(
            Check(
                f"sample.issue.{index}",
                "Readability",
                "FAIL",
                f"Sample fix {index}",
                "An observed issue",
                f"Make change {index}",
                url="https://fixture.example/page",
                severity="MEDIUM",
            ).dump()
        )
    scan.audit_summary = {**scan.audit_summary, "checks": checks}
    session.commit()
    response = client.get(f"/api/v1/free-reports/{token}/fix-preview")
    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data["fixes"]) == 3
    assert data["assets"] == []
    assert data["remaining_fixes"] == 4
    assert all("re-scan" in fix["prompts"]["coding_assistant"].lower() for fix in data["fixes"])
    assert "Sample fix 5" not in response.text
    assert client.get(f"/api/v1/free-reports/{token}/fix-center").status_code == 402
    assert client.get(f"/api/v1/free-reports/{token}/fix-pack.zip").status_code == 402
    client.cookies.clear()
    assert client.get(f"/api/v1/free-reports/{token}/fix-preview").status_code == 401


@pytest.mark.parametrize("include_issue", [True, False])
def test_free_fix_preview_fills_unused_slots_only_with_validated_crawl_assets(
    launch, include_issue
):
    from app.engines.fixes.assets import validate_asset
    from app.models.domain import Page

    client, session, _, _ = launch
    token, scan = report(launch)
    if not include_issue:
        scan.audit_summary = {**scan.audit_summary, "checks": []}
    session.add(
        Page(
            scan_id=scan.id,
            url="https://fixture.example/",
            status_code=200,
            title="Observed fixture name",
            meta_description="Observed homepage summary",
            crawl_depth=0,
            content_type="text/html",
            page_metadata={},
        )
    )
    session.commit()
    response = client.get(f"/api/v1/free-reports/{token}/fix-preview")
    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data["fixes"]) == int(include_issue)
    assert 0 < len(data["assets"]) <= 3
    assert len(data["fixes"]) + len(data["assets"]) <= 3
    for asset in data["assets"]:
        assert asset["validated"] is True
        assert validate_asset(asset["filename"], asset["content"]) == []
        assert (
            client.get(f"/api/v1/free-reports/{token}/assets/{asset['filename']}").status_code
            == 402
        )
    assert "Observed fixture name" in response.text


def test_free_fix_preview_rejects_foreign_mailbox_and_expired_links(launch):
    client, session, _, _ = launch
    token, _ = report(launch)
    owner_cookies = dict(client.cookies)
    verify(launch, email="another@fixture.example")
    assert client.get(f"/api/v1/free-reports/{token}/fix-preview").status_code == 403
    client.cookies.clear()
    client.cookies.update(owner_cookies)
    share = session.scalar(
        select(ReportShare).where(ReportShare.token_digest == access.digest(token))
    )
    share.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    session.commit()
    assert client.get(f"/api/v1/free-reports/{token}/fix-preview").status_code == 404


def test_standards_reference_coverage_respects_full_report_access_and_score(launch):
    from app.services.free_reports import score_summary

    client, session, _, _ = launch
    token, scan = report(launch)
    preview = client.get(f"/api/v1/free-reports/{token}").json()
    assert preview["standards_coverage"] is None
    expected_score = score_summary(scan.audit_summary)[0]
    assert preview["score"] == expected_score
    assert client.post(f"/api/v1/free-reports/{token}/checkout").status_code == 200
    order = session.scalar(select(DomainOrder))
    assert webhook(client, event_for(order)).status_code == 200
    paid = client.get(f"/api/v1/free-reports/{token}").json()
    assert paid["score"] == expected_score
    coverage = paid["standards_coverage"]
    assert coverage["conformance"] == "NOT_ASSESSED"
    assert len(coverage["requirements"]) == 24
    assert all(row["assessment"] == "NOT_TESTED" for row in coverage["requirements"])
    client.cookies.clear()
    assert client.get(f"/api/v1/free-reports/{token}").status_code == 401
