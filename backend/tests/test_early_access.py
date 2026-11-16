from sqlalchemy import func, select

from app.core.config import get_settings
from app.models.domain import EarlyAccessRequest


def _count(session):
    return session.scalar(select(func.count()).select_from(EarlyAccessRequest))


def test_request_is_stored_once_per_email_and_domain(client, session):
    body = {"email": "Owner@Example.com", "website_url": "https://www.example.com/shop"}
    first = client.post("/api/v1/early-access", json=body)
    again = client.post("/api/v1/early-access", json=body)
    assert first.status_code == again.status_code == 202
    assert first.json() == again.json() == {"status": "received"}
    row = session.scalar(select(EarlyAccessRequest))
    assert (row.email, row.domain) == ("owner@example.com", "example.com")
    assert _count(session) == 1
    assert first.headers["cache-control"] == "no-store"


def test_invalid_email_and_website_are_rejected(client, session):
    bad_email = client.post(
        "/api/v1/early-access", json={"email": "not-an-email", "website_url": "example.com"}
    )
    bad_site = client.post(
        "/api/v1/early-access", json={"email": "a@example.com", "website_url": "http://10.0.0.1"}
    )
    assert bad_email.status_code == bad_site.status_code == 422
    assert _count(session) == 0


def test_honeypot_is_accepted_but_not_stored(client, session):
    response = client.post(
        "/api/v1/early-access",
        json={"email": "bot@example.com", "website_url": "example.com", "company": "Spam Inc"},
    )
    assert response.status_code == 202
    assert _count(session) == 0


def test_requests_are_rate_limited(client):
    statuses = [
        client.post(
            "/api/v1/early-access",
            json={"email": f"owner{i}@example.com", "website_url": "example.com"},
        ).status_code
        for i in range(6)
    ]
    assert statuses[:5] == [202] * 5 and statuses[5] == 429


def test_form_works_in_customer_mode(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "customer_mode_enabled", True)
    response = client.post(
        "/api/v1/early-access", json={"email": "owner@example.com", "website_url": "example.com"}
    )
    assert response.status_code == 202
