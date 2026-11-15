"""The anonymous customer journey uses real audits and mocked website HTTP only."""

import asyncio
import hashlib
import json
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import httpx
import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.engines.crawling.crawler import WebsiteCrawler
from app.engines.crawling.transport import Fetcher
from app.engines.crawling.urls import URLValidator
from app.models.domain import AgentTaskTest, Finding, Page, ReportShare, Scan, ScanStatus
from app.services.crawls import execute_scan
from app.services.free_reports import score_summary


@pytest.fixture
def scheduled(client, monkeypatch):
    """Capture the background job without letting TestClient fetch a real site."""
    jobs = []

    async def capture(scan_id):
        jobs.append(scan_id)

    monkeypatch.setattr("app.api.routes.execute_scan", capture)
    return jobs


def submit(client, session, url="https://fixture.example/"):
    response = client.post("/api/v1/free-scans", json={"website_url": url})
    assert response.status_code == 201, response.text
    accepted = response.json()
    assert set(accepted) == {"report_path", "status", "expires_at"}
    assert accepted["report_path"].startswith("/free-reports/")
    token = accepted["report_path"].rsplit("/", 1)[-1]
    share = session.scalar(
        select(ReportShare).where(
            ReportShare.token_digest == hashlib.sha256(token.encode()).hexdigest()
        )
    )
    assert share is not None
    scan = session.get(Scan, share.scan_id)
    assert str(scan.id) not in response.text
    assert str(scan.project_id) not in response.text
    assert token != share.token_digest
    return accepted, token, scan, share


def read_report(client, token):
    response = client.get(f"/api/v1/free-reports/{token}")
    assert response.status_code == 200, response.text
    return response.json()


def run_fixture(scan_id, session, serve, **kwargs):
    @contextmanager
    def factory():
        yield session

    def crawler_factory(url, settings):
        return WebsiteCrawler(
            url,
            settings,
            Fetcher(URLValidator(url), settings, httpx.MockTransport(serve)),
        )

    execute_scan(scan_id, factory, crawler_factory, **kwargs)
    session.expire_all()


def test_free_scan_submission_is_opaque_bounded_static_and_reuses_pending_scan(
    client, session, scheduled, monkeypatch
):
    settings = get_settings()
    monkeypatch.setattr(settings, "crawl_max_pages", 30)
    monkeypatch.setattr(settings, "agent_pipeline_enabled", True)
    accepted, token, scan, _share = submit(
        client, session, "https://fixture.example/?token=must-not-leak"
    )
    assert accepted["status"] == "PENDING"
    assert scheduled == [scan.id]
    assert scan.audit_summary["scan_mode"] == "FREE_REPORT"
    assert scan.audit_summary["limits"]["max_pages"] == 10
    assert scan.audit_summary["agent_policy"]["pipeline_enabled"] is False

    pending = read_report(client, token)
    assert pending["status"] == "PENDING"
    assert pending["score"] is None
    assert pending["score_status"] == "UNAVAILABLE"
    assert pending["insights"] == []
    assert pending["website"] == "https://fixture.example/"
    assert "must-not-leak" not in json.dumps(pending)
    assert str(scan.id) not in json.dumps(pending)
    assert str(scan.project_id) not in json.dumps(pending)
    assert "agent_tasks" not in pending
    assert "project" not in pending

    _accepted, _token, duplicate, _share = submit(
        client, session, "https://fixture.example/?token=must-not-leak"
    )
    assert duplicate.id == scan.id
    assert len(list(session.scalars(select(Scan)))) == 1


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "https://localhost/",
        "http://127.0.0.1/",
        "http://[::1]/",
        "http://169.254.169.254/latest/meta-data/",
        "https://user:password@fixture.example/",
        "https://fixture.example:8443/",
    ],
)
def test_free_scan_rejects_invalid_or_unsafe_submission_without_scheduling(
    client, session, scheduled, url
):
    response = client.post("/api/v1/free-scans", json={"website_url": url})
    assert response.status_code == 422, response.text
    assert response.json()["error"]["message"]
    assert scheduled == []
    assert list(session.scalars(select(Scan))) == []


def test_free_report_capability_expiry_revocation_and_response_headers(client, session, scheduled):
    _accepted, token, _scan, share = submit(client, session)
    response = client.get(f"/api/v1/free-reports/{token}")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-robots-tag"] == "noindex, nofollow"
    assert response.headers["referrer-policy"] == "no-referrer"
    share.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    session.commit()
    assert client.get(f"/api/v1/free-reports/{token}").status_code == 404

    _accepted, token, _scan, share = submit(client, session)
    share.revoked_at = datetime.now(UTC)
    session.commit()
    assert client.get(f"/api/v1/free-reports/{token}").status_code == 404
    assert client.get("/api/v1/free-reports/not-a-live-capability").status_code == 404


@pytest.mark.parametrize("sitemap_mode", ["missing", "malformed"])
def test_free_scan_runs_real_static_audits_with_ten_page_cap_and_no_llm(
    client, session, scheduled, monkeypatch, sitemap_mode
):
    settings = get_settings()
    monkeypatch.setattr(settings, "agent_pipeline_enabled", True)
    monkeypatch.setattr(settings, "audit_browser_enabled", False)
    monkeypatch.setattr(settings, "crawl_max_pages", 30)
    monkeypatch.setattr(settings, "crawl_min_delay", 0)
    _accepted, token, scan, _share = submit(client, session)
    requested = []
    links = "".join(f'<a href="/page-{number}">Page {number}</a>' for number in range(15))

    def serve(request):
        requested.append(request.url.path)
        if request.url.path == "/robots.txt":
            body = b"User-agent: *\nAllow: /\n"
        elif request.url.path == "/sitemap.xml":
            if sitemap_mode == "missing":
                return httpx.Response(404, stream=httpx.ByteStream(b""))
            body = b"<urlset><url>"
        elif request.url.path == "/llms.txt":
            return httpx.Response(404, stream=httpx.ByteStream(b""))
        elif request.url.path == "/broken":
            return httpx.Response(
                404,
                headers={"content-type": "text/html"},
                stream=httpx.ByteStream(b"<title>Not found</title><h1>Missing</h1>"),
            )
        else:
            content = (
                '<html><head><script type="application/ld+json">{malformed}</script></head>'
                '<body><h1>Fixture</h1><button></button><a href="/broken">Broken</a>'
                + links
                + "</body></html>"
            )
            return httpx.Response(
                200,
                headers={"content-type": "text/html"},
                stream=httpx.ByteStream(content.encode()),
            )
        return httpx.Response(200, stream=httpx.ByteStream(body))

    forbidden_provider = Mock(side_effect=AssertionError("Free scans must not load an LLM"))
    forbidden_agent_browser = Mock(side_effect=AssertionError("No browser-agent task should run"))
    run_fixture(
        scheduled[0],
        session,
        serve,
        agent_provider_factory=forbidden_provider,
        agent_browser_factory=forbidden_agent_browser,
    )
    forbidden_provider.assert_not_called()
    forbidden_agent_browser.assert_not_called()
    assert list(session.scalars(select(AgentTaskTest))) == []

    stored = session.get(Scan, scan.id)
    assert stored.status == ScanStatus.COMPLETED
    pages = list(session.scalars(select(Page).where(Page.scan_id == scan.id)))
    assert len(pages) == 10
    assert stored.pages_crawled == 10
    assert stored.pages_discovered > stored.pages_crawled
    assert stored.pages_failed == 1
    assert "/broken" in requested
    rules = {
        finding.evidence["rule"]
        for finding in session.scalars(select(Finding).where(Finding.scan_id == scan.id))
    }
    assert {
        "page.title",
        "page.meta_description",
        "schema.syntax",
        "http.status",
    } <= rules
    if sitemap_mode == "malformed":
        assert "sitemap.health" in rules
    else:
        assert "sitemap.health" not in rules
    report = read_report(client, token)
    assert report["status"] == "COMPLETED"
    assert report["score_version"] == "free-static-v4"
    assert report["score_status"] == "PRELIMINARY"
    assert 0 <= report["score"] <= 100
    assert 3 < len(report["insights"]) <= 10
    assert len({item["title"] for item in report["insights"]}) == len(report["insights"])
    persisted_titles = {
        finding.title
        for finding in session.scalars(select(Finding).where(Finding.scan_id == scan.id))
    }
    assert all(item["title"] in persisted_titles for item in report["insights"])
    assert all(item["description"] and item["evidence_url"] for item in report["insights"])
    assert report["coverage"]["problems"] > 0
    assert report["coverage"]["checks_total"] == len(report["checks"])
    assert report["coverage"]["checks_informational"] > 0
    assert report["coverage"]["checks_inconclusive"] > 0
    assert all("?" not in (check["url"] or "") for check in report["checks"])
    assert any(check["status"] == "FAIL" and check["url"] for check in report["checks"])
    assert any(check["status"] == "INFO" for check in report["checks"])
    categories = {item["name"]: item for item in report["category_scores"]}
    assert {name: item["weight"] for name, item in categories.items()} == {
        "Discoverability": 30,
        "Content understanding": 25,
        "Structured data": 20,
        "Agent usability": 25,
    }
    assert categories["Agent usability"]["score"] is None
    assert categories["Agent usability"]["tested"] is False
    assert read_report(client, token)["score"] == report["score"]
    assert str(scan.id) not in json.dumps(report)


def test_valid_saas_fixture_gets_evidence_based_score_without_placeholder_insights(
    client, session, scheduled, monkeypatch
):
    monkeypatch.setattr(get_settings(), "audit_browser_enabled", False)
    monkeypatch.setattr(get_settings(), "crawl_min_delay", 0)
    _accepted, token, _scan, _share = submit(client, session)

    def serve(request):
        if request.url.path.startswith("/.agentreadiness-missing-"):
            return httpx.Response(404, stream=httpx.ByteStream(b"Missing fixture path"))
        if request.url.path == "/robots.txt":
            body = b"User-agent: *\nAllow: /\nSitemap: https://fixture.example/sitemap.xml"
        elif request.url.path == "/sitemap.xml":
            body = b"<urlset><url><loc>https://fixture.example/</loc></url><url><loc>https://fixture.example/docs</loc></url></urlset>"
        elif request.url.path == "/llms.txt":
            body = b"# Fixture\n\n## Documentation\n- [Docs](https://fixture.example/docs): Product documentation"
        else:
            canonical = str(request.url)
            body = (
                '<html lang="en"><head><title>Fixture product</title>'
                '<meta name="description" content="Fixture provides product documentation.">'
                f'<link rel="canonical" href="{canonical}">'
                '<script type="application/ld+json">'
                '{"@context":"https://schema.org","@type":"WebSite",'
                '"name":"Fixture","url":"https://fixture.example/"}'
                "</script></head><body><h1>Fixture product</h1>"
                '<nav><a href="/docs">Documentation</a></nav>'
                "<h2>Product documentation</h2><p>Read our product documentation.</p>"
                "</body></html>"
            ).encode()
            return httpx.Response(
                200,
                headers={"content-type": "text/html"},
                stream=httpx.ByteStream(body),
            )
        return httpx.Response(200, stream=httpx.ByteStream(body))

    run_fixture(scheduled[0], session, serve)
    report = read_report(client, token)
    assert report["status"] == "COMPLETED"
    assert report["score"] == 100
    assert report["score_status"] == "PRELIMINARY"
    assert report["insights"] == []
    assert report["coverage"]["passed"] > 0
    assert report["coverage"]["problems"] == 0


def test_slow_site_preserves_partial_evidence_and_returns_a_terminal_report(
    client, session, scheduled, monkeypatch
):
    settings = get_settings()
    monkeypatch.setattr(settings, "audit_browser_enabled", False)
    monkeypatch.setattr(settings, "crawl_min_delay", 0)
    # Shorten only this injected test configuration; production validation keeps
    # its normal minimum. The mock transport never touches an external website.
    monkeypatch.setattr(settings, "scan_duration", 1)
    _accepted, token, scan, _share = submit(client, session)

    async def serve(request):
        if request.url.path in ("/robots.txt", "/sitemap.xml", "/llms.txt"):
            return httpx.Response(404, stream=httpx.ByteStream(b""))
        if request.url.path == "/slow":
            await asyncio.sleep(2)
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            stream=httpx.ByteStream(
                b'<title>Fixture</title><h1>Fixture</h1><a href="/slow">Slow page</a>'
            ),
        )

    run_fixture(scheduled[0], session, serve)
    report = read_report(client, token)
    assert report["status"] == "FAILED"
    assert report["failure_message"]
    assert report["pages_crawled"] >= 1
    assert len(list(session.scalars(select(Page).where(Page.scan_id == scan.id)))) >= 1
    assert report["score_status"] == "PRELIMINARY"
    assert "Partial inspection" in report["score_explanation"]


@pytest.mark.parametrize("failure", ["unreachable", "robots"])
def test_inaccessible_site_returns_honest_failure_without_manufactured_score(
    client, session, scheduled, monkeypatch, failure
):
    monkeypatch.setattr(get_settings(), "audit_browser_enabled", False)
    monkeypatch.setattr(get_settings(), "crawl_min_delay", 0)
    _accepted, token, _scan, _share = submit(client, session)

    def serve(request):
        if request.url.path == "/robots.txt":
            content = (
                b"User-agent: *\nDisallow: /" if failure == "robots" else b"User-agent: *\nAllow: /"
            )
            return httpx.Response(200, stream=httpx.ByteStream(content))
        if request.url.path in ("/sitemap.xml", "/llms.txt"):
            return httpx.Response(404, stream=httpx.ByteStream(b""))
        raise httpx.ConnectError("Fixture origin unavailable", request=request)

    run_fixture(scheduled[0], session, serve)
    report = read_report(client, token)
    assert report["status"] == "FAILED"
    assert report["failure_message"]
    assert report["score"] is None
    assert report["score_status"] == "UNAVAILABLE"
    assert "not" in report["score_explanation"].lower()
    if failure == "robots":
        assert "robots" in report["failure_message"].lower()
    else:
        http_checks = [
            check for check in report["checks"] if check["title"].startswith("Page request")
        ]
        assert http_checks and http_checks[0]["status"] == "UNKNOWN"
        assert all(
            check["status"] != "FAIL"
            for check in report["checks"]
            if check["title"].startswith("Page request")
        )


def test_score_normalizes_only_tested_categories_and_ignores_infrastructure_failures():
    checks = [
        {"rule": "robots.access", "status": "PASS", "weight": 1},
        {"rule": "sitemap.health", "status": "UNKNOWN", "weight": 3},
        {"rule": "page.title", "status": "FAIL", "weight": 1},
        {"rule": "page.h1", "status": "NOT_APPLICABLE", "weight": 1},
        {"rule": "schema.syntax", "status": "PASS", "weight": 1},
        {"rule": "http.status", "status": "FAIL", "weight": 100},
    ]
    score, categories, coverage = score_summary({"checks": checks})
    assert score == 44.4  # Our own crawler policy is not provider readiness: (0*25 + 100*20) / 45
    assert coverage.passed == 1
    assert coverage.problems == 1
    assert coverage.untested == 1
    assert next(item for item in categories if item.name == "Agent usability").score is None
    reordered = score_summary({"checks": list(reversed(checks))})
    assert reordered == (score, categories, coverage)


def test_robots_http_denial_returns_partial_diagnostics_without_false_site_failure(
    client, session, scheduled, monkeypatch
):
    monkeypatch.setattr(get_settings(), "audit_browser_enabled", False)
    _accepted, token, _scan, _share = submit(client, session)
    paths = []

    def serve(request):
        paths.append(request.url.path)
        return httpx.Response(403, stream=httpx.ByteStream(b"Access denied"))

    run_fixture(scheduled[0], session, serve)
    report = read_report(client, token)
    assert report["status"] == "FAILED"
    assert report["score"] is None
    assert report["coverage"]["checks_failed"] == 0
    assert report["access_policies"]
    assert all(row["policy"] == "UNKNOWN" for row in report["access_policies"])
    assert any("Our scanner could not inspect" in row["title"] for row in report["checks"])
    assert paths == ["/robots.txt"]  # No bypass or provider impersonation.
    assert report["insights"] == []


def test_access_denied_on_one_page_retains_other_page_results_with_partial_coverage(
    client, session, scheduled, monkeypatch
):
    monkeypatch.setattr(get_settings(), "audit_browser_enabled", False)
    monkeypatch.setattr(get_settings(), "crawl_min_delay", 0)
    _accepted, token, _scan, _share = submit(client, session)

    def serve(request):
        if request.url.path.startswith("/.agentreadiness-missing-"):
            return httpx.Response(404, stream=httpx.ByteStream(b"Missing fixture path"))
        if request.url.path == "/robots.txt":
            return httpx.Response(200, stream=httpx.ByteStream(b"User-agent: *\nAllow: /"))
        if request.url.path in ("/sitemap.xml", "/llms.txt"):
            return httpx.Response(404, stream=httpx.ByteStream(b""))
        if request.url.path == "/denied":
            return httpx.Response(403, stream=httpx.ByteStream(b"Denied"))
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            stream=httpx.ByteStream(
                b'<title>Fixture</title><meta name="description" content="Fixture product"><h1>Fixture</h1><a href="/denied">Details</a>'
            ),
        )

    run_fixture(scheduled[0], session, serve)
    report = read_report(client, token)
    assert report["status"] == "COMPLETED"  # Execution finished; coverage remains partial.
    assert report["pages_crawled"] == 2  # Existing API counts attempted page requests.
    assert report["pages_failed"] == 1
    assert report["score_status"] == "PRELIMINARY"
    assert "Partial inspection" in report["score_explanation"]
    denied = [row for row in report["checks"] if row["title"] == "Our scanner received HTTP 403"]
    assert {row["status"] for row in denied} == {"INFO", "UNKNOWN"}
    assert report["coverage"]["checks_failed"] == 0
    assert report["insights"] == []


def test_valid_sitemap_does_not_manufacture_score_when_all_pages_are_denied(
    client, session, scheduled, monkeypatch
):
    monkeypatch.setattr(get_settings(), "audit_browser_enabled", False)
    monkeypatch.setattr(get_settings(), "crawl_min_delay", 0)
    _accepted, token, _scan, _share = submit(client, session)

    def serve(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, stream=httpx.ByteStream(b"User-agent: *\nAllow: /"))
        if request.url.path == "/sitemap.xml":
            return httpx.Response(
                200,
                stream=httpx.ByteStream(
                    b'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://fixture.example/</loc></url></urlset>'
                ),
            )
        if request.url.path == "/llms.txt":
            return httpx.Response(404, stream=httpx.ByteStream(b""))
        return httpx.Response(403, stream=httpx.ByteStream(b"Denied"))

    run_fixture(scheduled[0], session, serve)
    report = read_report(client, token)
    assert report["status"] == "FAILED"
    assert report["score"] is None
    assert report["score_status"] == "UNAVAILABLE"
    assert report["coverage"]["checks_failed"] == 0
    assert any(row["title"] == "Sitemap is available" for row in report["checks"])
    assert all(row["score"] is None for row in report["category_scores"])
