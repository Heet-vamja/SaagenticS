"""Dashboard site onboarding and the site job queue (phase 5). No model is called: job
execution is replaced by stubs, so these tests cover queueing, claiming and recording."""

import asyncio
from contextlib import nullcontext
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.engines.agent.provider import InferenceError
from app.models.domain import EdgeSite, SiteJob, SiteVariant
from app.services import site_jobs
from app.services.site_jobs import claim_next, expire_stale, run_claimed

TOKEN = "test-dashboard-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
SITE = {"host": "Store.Localhost", "origin": "http://demo-store:4000", "name": "Northstar"}


@pytest.fixture
def dashboard(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(
        settings, "edge_dashboard_token", type(settings.edge_dashboard_token)(TOKEN)
    )
    monkeypatch.setattr(settings, "edge_allow_private_origins", True)
    return client


@pytest.fixture
def factory(session):
    return lambda: nullcontext(session)


def test_site_routes_require_the_token(dashboard):
    assert dashboard.post("/api/v1/dashboard/sites", json=SITE).status_code == 401
    wrong = {"Authorization": "Bearer nope"}
    assert dashboard.get("/api/v1/dashboard/sites/x/jobs", headers=wrong).status_code == 401


def test_owner_registers_a_site_and_queues_one_job_per_kind(dashboard, session):
    created = dashboard.post("/api/v1/dashboard/sites", json=SITE, headers=AUTH)
    assert created.status_code == 201
    assert created.json()["host"] == "store.localhost"
    duplicate = dashboard.post("/api/v1/dashboard/sites", json=SITE, headers=AUTH)
    assert duplicate.status_code == 422
    assert duplicate.json()["error"]["message"] == "store.localhost is already registered"

    queued = dashboard.post(
        "/api/v1/dashboard/sites/store.localhost/jobs", json={"kind": "build_variant"}, headers=AUTH
    )
    assert queued.status_code == 202
    assert queued.json()["status"] == "PENDING"
    again = dashboard.post(
        "/api/v1/dashboard/sites/store.localhost/jobs", json={"kind": "build_variant"}, headers=AUTH
    )
    assert again.status_code == 409
    other = dashboard.post(
        "/api/v1/dashboard/sites/store.localhost/jobs", json={"kind": "run_qa"}, headers=AUTH
    )
    assert other.status_code == 202

    listed = dashboard.get("/api/v1/dashboard/sites/store.localhost/jobs", headers=AUTH).json()
    assert sorted(job["kind"] for job in listed["jobs"]) == ["build_variant", "run_qa"]
    assert all(job["status"] == "PENDING" for job in listed["jobs"])
    # Queueing never runs anything in the request.
    assert session.scalars(select(SiteJob).where(SiteJob.status != "PENDING")).all() == []


def test_unknown_kind_and_host_are_rejected(dashboard):
    dashboard.post("/api/v1/dashboard/sites", json=SITE, headers=AUTH)
    bad_kind = dashboard.post(
        "/api/v1/dashboard/sites/store.localhost/jobs", json={"kind": "delete"}, headers=AUTH
    )
    assert bad_kind.status_code == 422
    missing = dashboard.post(
        "/api/v1/dashboard/sites/nope.localhost/jobs", json={"kind": "run_qa"}, headers=AUTH
    )
    assert missing.status_code == 404


@pytest.mark.parametrize(
    "origin",
    ["http://demo-store:4000", "http://127.0.0.1", "http://shop.localhost", "http://10.0.0.5"],
)
def test_private_origin_is_rejected_unless_allowed(dashboard, monkeypatch, origin):
    monkeypatch.setattr(get_settings(), "edge_allow_private_origins", False)
    site = {**SITE, "origin": origin}
    response = dashboard.post("/api/v1/dashboard/sites", json=site, headers=AUTH)
    assert response.status_code == 422
    assert dashboard.get("/api/v1/dashboard/sites", headers=AUTH).json()["sites"] == []


def _site(session):
    site = EdgeSite(host="store.localhost", origin_url="http://demo-store:4000", name="N")
    session.add(site)
    session.flush()
    return site


def _job(session, site, kind="build_variant", **values):
    job = SiteJob(site_id=site.id, kind=kind, **values)
    session.add(job)
    session.flush()
    return job


def test_worker_records_success_from_the_real_result(session, factory, monkeypatch):
    site = _site(session)
    job = _job(session, site)

    async def execute(kind, host, settings, session_factory):
        assert (kind, host) == ("build_variant", "store.localhost")
        return {"version": 1, "status": "REJECTED", "parity_passed": False}

    monkeypatch.setattr(site_jobs, "_execute", execute)
    claimed = claim_next(factory)
    assert claimed == (job.id, "build_variant", "store.localhost")
    assert session.get(SiteJob, job.id).status == "RUNNING"
    assert claim_next(factory) is None  # Nothing else is pending.

    assert asyncio.run(run_claimed(*claimed, get_settings(), factory)) == "SUCCEEDED"
    done = session.get(SiteJob, job.id)
    # A rejected build finished; the result carries the real parity outcome.
    assert done.status == "SUCCEEDED"
    assert done.result == {"version": 1, "status": "REJECTED", "parity_passed": False}
    assert done.finished_at is not None


@pytest.mark.parametrize(
    "error,detail",
    [
        (InferenceError("Configure GEMINI_API_KEY"), "InferenceError: Configure GEMINI_API_KEY"),
        (KeyError("secret-internal"), "Unexpected error (KeyError)"),
    ],
)
def test_worker_records_failures_without_leaking_internals(
    session, factory, monkeypatch, error, detail
):
    site = _site(session)
    job = _job(session, site, kind="run_qa")

    async def execute(*_):
        raise error

    monkeypatch.setattr(site_jobs, "_execute", execute)
    assert asyncio.run(run_claimed(*claim_next(factory), get_settings(), factory)) == "FAILED"
    failed = session.get(SiteJob, job.id)
    assert (failed.status, failed.detail, failed.result) == ("FAILED", detail, None)


def test_qa_job_without_a_gemini_key_fails_honestly(session, factory, monkeypatch):
    monkeypatch.setattr(get_settings(), "gemini_api_key", type(get_settings().gemini_api_key)(""))
    site = _site(session)
    job = _job(session, site, kind="run_qa")
    assert asyncio.run(run_claimed(*claim_next(factory), get_settings(), factory)) == "FAILED"
    assert "GEMINI_API_KEY" in session.get(SiteJob, job.id).detail
    assert session.scalars(select(SiteVariant)).all() == []


def test_stale_running_jobs_are_failed_and_fresh_ones_kept(session, factory):
    site = _site(session)
    now = datetime.now(UTC)
    stale = _job(session, site, status="RUNNING", started_at=now - timedelta(hours=3))
    fresh = _job(session, site, kind="run_qa", status="RUNNING", started_at=now)
    assert expire_stale(factory, get_settings()) == 1
    session.expire_all()
    assert session.get(SiteJob, stale.id).status == "FAILED"
    assert session.get(SiteJob, fresh.id).status == "RUNNING"


def test_build_without_a_gemini_key_fails_before_rendering(session, factory, monkeypatch):
    settings = get_settings().model_copy(
        update={
            "agent_llm_provider": "gemini",
            "agent_llm_base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
            "gemini_api_key": type(get_settings().gemini_api_key)(""),
        }
    )

    async def never(*_):
        pytest.fail("Pages must not be rendered when the model is not configured")

    monkeypatch.setattr("app.services.variants.collect_evidence", never)
    site = _site(session)
    job = _job(session, site)
    assert asyncio.run(run_claimed(*claim_next(factory), settings, factory)) == "FAILED"
    assert session.get(SiteJob, job.id).detail == (
        "InferenceError: Configure GEMINI_API_KEY for Gemini inference"
    )


def _registered(dashboard):
    assert dashboard.post("/api/v1/dashboard/sites", json=SITE, headers=AUTH).status_code == 201


def test_owner_edits_a_site_and_pauses_routing(dashboard, session):
    _registered(dashboard)
    url = "/api/v1/dashboard/sites/store.localhost"
    changed = dashboard.patch(
        url, json={"name": "Northstar Shoes", "routing_enabled": False}, headers=AUTH
    )
    assert changed.status_code == 200
    assert changed.json() == {
        "host": "store.localhost",
        "name": "Northstar Shoes",
        "origin": "http://demo-store:4000",
        "routing_enabled": False,
        "delivery_rules": None,
    }
    assert dashboard.patch(url, json={"host": "other.localhost"}, headers=AUTH).status_code == 422
    assert dashboard.patch(url, json={"origin": "ftp://x"}, headers=AUTH).status_code == 422
    settings = dashboard.get(f"{url}/settings", headers=AUTH).json()
    assert settings["origin"] == "http://demo-store:4000"  # Unchanged after a rejected edit.


def test_owner_sets_and_clears_delivery_rules(dashboard):
    _registered(dashboard)
    url = "/api/v1/dashboard/sites/store.localhost/delivery"
    rules = {
        "pin_pattern": "^\\d{6}$",
        "estimates": [{"prefixes": ["56"], "estimate": "2–3 working days"}],
        "default_estimate": "3–5 working days",
        "free_delivery_over": 1500,
    }
    saved = dashboard.put(url, json=rules, headers=AUTH)
    assert saved.status_code == 200
    assert saved.json()["delivery_rules"] == rules
    bad = dashboard.put(url, json={**rules, "pin_pattern": "([0-9"}, headers=AUTH)
    assert bad.status_code == 422
    assert dashboard.delete(url, headers=AUTH).json()["delivery_rules"] is None


def test_removing_a_site_cascades_and_waits_for_running_jobs(dashboard, session):
    from app.models.domain import AgentRequest

    _registered(dashboard)
    site = session.scalar(select(EdgeSite).where(EdgeSite.host == "store.localhost"))
    session.add(
        AgentRequest(
            site_id=site.id,
            received_at=datetime.now(UTC),
            agent="ChatGPT-User",
            agent_kind="agent",
            method="GET",
            path="/",
            status=200,
            duration_ms=5,
            served_by="origin",
            response_bytes=10,
            client_hash="a" * 64,
            user_agent="x",
        )
    )
    job = _job(session, site, kind="run_qa", status="RUNNING", started_at=datetime.now(UTC))
    url = "/api/v1/dashboard/sites/store.localhost"
    busy = dashboard.delete(url, headers=AUTH)
    assert busy.status_code == 409
    job.status = "FAILED"
    session.flush()
    assert dashboard.delete(url, headers=AUTH).status_code == 204
    session.expire_all()
    assert session.scalars(select(EdgeSite)).all() == []
    assert session.scalars(select(AgentRequest)).all() == []
    assert session.scalars(select(SiteJob)).all() == []
    assert dashboard.delete(url, headers=AUTH).status_code == 404
