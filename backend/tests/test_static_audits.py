import asyncio
import json
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import httpx
from sqlalchemy import select

from app.core.config import Settings
from app.engines.crawling.crawler import WebsiteCrawler
from app.engines.crawling.parsers import RobotsHandler
from app.engines.crawling.transport import Fetcher
from app.engines.crawling.urls import URLValidator
from app.engines.static_audit.checks import Check, summarize
from app.engines.static_audit.html import html_checks, inspect_html
from app.engines.static_audit.render import render_pages
from app.engines.static_audit.site import llms_measurements, site_checks
from app.models.domain import Finding, Project, ReportShare, Scan, ScanStatus
from app.repositories.records import Records
from app.services.crawls import execute_scan
from app.services.report_pdf import render_html
from app.services.reports import ReportService
from app.services.static_audits import page_checks

GOOD = b"""<html lang="en"><head><title>Northstar</title><script type="application/ld+json">{"@context":"https://schema.org","@type":"Product","name":"Northstar"}</script></head><body><h1>Northstar</h1><a href="/pricing">Pricing</a><button aria-label="Open menu"></button><label for="email">Email</label><input id="email" type="email"></body></html>"""


def test_html_names_labels_schema_and_bounded_private_evidence():
    good = inspect_html(GOOD, "https://fixture.example/")
    good_checks = html_checks("https://fixture.example/", good)
    assert not [c for c in good_checks if c.status == "FAIL"]
    titles = {c.rule: c.title for c in good_checks}
    assert titles["page.title"] == "Page title is present"
    assert titles["page.h1"] == "Main heading is present"
    assert titles["semantic.buttons"] == "Buttons have accessible names"
    assert titles["schema.syntax"] == "JSON-LD passed the supported syntax checks"
    bad = inspect_html(
        b"""<button></button><input type="password" value="do-not-store"><a href="/x"></a><div onclick="alert(1)">Open</div><script type="application/ld+json">{"@context":"https://schema.org","@type":"Product","badProperty":1}</script>""",
        "https://fixture.example/",
    )
    rules = {c.rule for c in html_checks("https://fixture.example/", bad) if c.status == "FAIL"}
    assert {
        "semantic.buttons",
        "semantic.inputs",
        "semantic.links",
        "semantic.clickable_divs",
        "schema.syntax",
    } <= rules
    assert (
        next(
            c for c in html_checks("https://fixture.example/", bad) if c.rule == "schema.fields"
        ).status
        == "INFO"
    )
    assert "do-not-store" not in json.dumps(bad)
    assert bad["structured_data"]["errors"][0]["property"] == "badProperty"
    unknown = inspect_html(
        b'<script type="application/ld+json">{"@context":"https://schema.org","@type":"NotARealSchemaType"}</script>',
        "https://fixture.example/",
    )
    assert unknown["structured_data"]["errors"]
    malformed = inspect_html(
        b'<script type="application/ld+json">{oops}</script>', "https://fixture.example/"
    )
    assert malformed["structured_data"]["errors"]
    hidden = inspect_html(b'<input hidden><input type="hidden">', "https://fixture.example/")
    assert (
        next(
            c
            for c in html_checks("https://fixture.example/", hidden)
            if c.rule == "semantic.inputs"
        ).status
        == "NOT_APPLICABLE"
    )


def test_llms_format_optional_sections_relative_links_and_no_fetches():
    assert llms_measurements(b"# Northstar")["valid"]
    assert llms_measurements(b"\xef\xbb\xbf# Northstar\n\n## Docs\n- [Guide](/docs.md)")["valid"]
    assert not llms_measurements(b"<html>not markdown</html>")["valid"]
    assert not llms_measurements(b"# First\n# Second")["valid"]
    assert not llms_measurements(b"# Project\n## Docs\n- Missing link")["valid"]
    assert not llms_measurements(b"# Project\n## Docs\n- [Link](file:///etc/passwd)")["valid"]
    assert not llms_measurements(b"\xff# invalid encoding")["valid"]


def test_robots_ai_policy_and_sitemap_unknown_freshness_not_unearned_pass():
    handler = RobotsHandler("AgentReadinessBot/0.1")
    handler.parse(
        200,
        b"User-agent: *\nAllow: /\n\nUser-agent: GPTBot\nDisallow: /\n\nUser-agent: ClaudeBot\nDisallow: /private",
    )
    state = handler.metadata("https://fixture.example/private")
    assert not state["ai_agents"]["GPTBot"]["allowed"]
    assert not state["ai_agents"]["ClaudeBot"]["allowed"]
    assert state["ai_agents"]["PerplexityBot"]["allowed"]
    checks = site_checks(
        "https://fixture.example/",
        {
            "robots": {"https://fixture.example": state},
            "sitemaps": [{"parsed": True, "entries": 2}],
            "llms": {"status": 404},
        },
    )
    assert all(c.status == "INFO" for c in checks if c.rule == "robots.ai_policy")
    assert next(c for c in checks if c.rule == "sitemap.freshness").status == "UNKNOWN"
    assert next(c for c in checks if c.rule == "llms.presence").status == "INFO"


def test_score_weights_unknown_and_repeated_pages_are_transparent():
    checks = [
        Check("a", "Access", "PASS", "A", ""),
        Check("b", "Access", "FAIL", "B", ""),
        Check("r", "Readability", "UNKNOWN", "R", ""),
    ]
    score = summarize(checks)
    assert score["score"] == 50
    assert score["provisional"]
    assert score["category_scores"]["Readability"] is None
    assert score["counts"]["UNKNOWN"] == 1
    assert summarize(checks + [checks[0]])["score"] == 50
    assert summarize([checks[-1]])["score"] is None


def test_fetch_failure_is_inconclusive_and_optional_assets_are_not_score_failures():
    page = SimpleNamespace(
        url="https://fixture.example/unreachable",
        status_code=None,
        crawl_error="ConnectError",
        page_metadata={},
    )
    request_check = next(c for c in page_checks(page) if c.rule == "http.status")
    assert request_check.status == "UNKNOWN"
    assert request_check.evidence == {}

    optional = site_checks(
        "https://fixture.example/",
        {
            "robots": {},
            "sitemaps": [{"url": "https://fixture.example/sitemap.xml", "status": 404}],
            "llms": {"url": "https://fixture.example/llms.txt", "status": 404},
        },
    )
    statuses = {c.rule: c.status for c in optional}
    assert statuses["sitemap.health"] == "INFO"
    assert statuses["llms.presence"] == "INFO"
    assert not [
        c for c in optional if c.rule in ("sitemap.health", "llms.presence") and c.status == "FAIL"
    ]


def test_http_redirect_error_and_challenge_checks_use_observed_evidence():
    error_page = SimpleNamespace(
        url="https://fixture.example/missing",
        status_code=404,
        crawl_error="HTTP 404",
        page_metadata={},
    )
    error_check = next(c for c in page_checks(error_page) if c.rule == "http.status")
    assert error_check.status == "FAIL"
    assert error_check.evidence == {"status": 404}
    assert "intentionally" in error_check.recommendation

    redirected_page = SimpleNamespace(
        url="https://fixture.example/",
        status_code=200,
        crawl_error=None,
        page_metadata={"http": {"redirects": ["/one", "/two", "/three"]}},
    )
    redirect_check = next(c for c in page_checks(redirected_page) if c.rule == "http.redirects")
    assert redirect_check.status == "FAIL"

    challenge = inspect_html(
        b"<html><title>One more step</title><body>Checking your browser"
        b"<div class='cf-turnstile'></div></body></html>",
        "https://fixture.example/",
    )
    challenge_check = next(
        c
        for c in html_checks("https://fixture.example/", challenge)
        if c.rule == "access.challenge"
    )
    assert challenge_check.status == "FAIL"
    assert challenge_check.evidence["signals"]


def test_robots_transient_failure_is_unknown_but_explicit_rule_is_observed():
    handler = RobotsHandler("AgentReadinessBot/0.1")
    handler.parse(503, b"maintenance")
    transient = handler.metadata("https://fixture.example/")
    checks = site_checks(
        "https://fixture.example/", {"robots": {"https://fixture.example": transient}}
    )
    assert next(c for c in checks if c.rule == "robots.access").status == "UNKNOWN"
    assert not transient["ai_agents"]["GPTBot"]["known"]

    handler.parse(200, b"User-agent: AgentReadinessBot/0.1\nDisallow: /")
    denied = handler.metadata("https://fixture.example/")
    checks = site_checks(
        "https://fixture.example/", {"robots": {"https://fixture.example": denied}}
    )
    assert next(c for c in checks if c.rule == "robots.access").status == "INFO"
    assert denied["ai_agents"]["GPTBot"]["known"]


def test_real_browser_js_comparison_through_mock_gateway_without_llm(tmp_path):
    calls = []

    def serve(request):
        calls.append(str(request.url))
        if request.url.path == "/robots.txt":
            return httpx.Response(404, stream=httpx.ByteStream(b""))
        body = b'<title>Dynamic</title><script>document.addEventListener("DOMContentLoaded",()=>{document.body.innerHTML="<h1>Pricing</h1><p>"+"Useful product content ".repeat(80)+"</p><button></button>"})</script><body></body>'
        return httpx.Response(
            200, headers={"content-type": "text/html"}, stream=httpx.ByteStream(body)
        )

    raw = inspect_html(b"<title>Dynamic</title><body></body>", "https://fixture.example/")
    page = SimpleNamespace(
        id=uuid4(), url="https://fixture.example/", status_code=200, page_metadata={"audit": raw}
    )
    checks = asyncio.run(
        render_pages(
            [page],
            Settings(
                crawl_min_delay=0, audit_render_timeout=10, agent_screenshot_dir=str(tmp_path)
            ),
            transport=httpx.MockTransport(serve),
        )
    )
    assert next(c for c in checks if c.rule == "render.js_dependency").status == "FAIL"
    assert next(c for c in checks if c.rule == "render.semantic.buttons").status == "FAIL"
    assert calls and all(url.startswith("https://fixture.example/") for url in calls)


def make_scan(session, project=None, checks=None, days=0):
    if project is None:
        project = Project(name="Audit fixture", website_url="https://fixture.example/")
        session.add(project)
        session.flush()
    summary = summarize(checks or [])
    scan = Scan(
        project_id=project.id,
        status=ScanStatus.COMPLETED,
        created_at=datetime.now(UTC) + timedelta(days=days),
        started_at=datetime.now(UTC) + timedelta(days=days),
        completed_at=datetime.now(UTC) + timedelta(days=days),
        audit_summary=summary,
        overall_score=summary["score"],
    )
    session.add(scan)
    session.flush()
    return project, scan


def test_reports_comparison_shares_expiry_revoke_and_exports(client, session):
    old = [
        Check(
            "semantic.inputs",
            "Actionability",
            "FAIL",
            "Label missing",
            "",
            url="https://fixture.example/form",
        ),
        Check(
            "http.status", "Reliability", "FAIL", "Missing", "", url="https://fixture.example/old"
        ),
    ]
    project, _before = make_scan(session, checks=old, days=-2)
    _, after = make_scan(
        session,
        project,
        [
            Check(
                "semantic.inputs",
                "Actionability",
                "PASS",
                "Label missing",
                "",
                url="https://fixture.example/form",
            )
        ],
        days=-1,
    )
    session.add(
        Finding(
            scan_id=after.id,
            category="INTERACTABILITY",
            severity="HIGH",
            title="=Spreadsheet formula",
            description="Evidence",
            recommendation="<button>Open menu</button>",
            evidence={
                "rule": "semantic.buttons",
                "url": "https://fixture.example/?token=secret",
                "engine": "static-v1",
            },
        )
    )
    session.commit()
    comparison = client.get(f"/api/v1/scans/{after.id}/comparison").json()
    assert comparison["available"] and len(comparison["resolved"]) == 1
    assert len(comparison["not_retested"]) == 1
    assert comparison["score_delta"] is not None
    response = client.get(f"/api/v1/scans/{after.id}/report")
    assert response.status_code == 200 and response.json()["audited"]
    assert response.json()["priority_fixes"]
    link = client.post(f"/api/v1/scans/{after.id}/shares").json()
    token = link["path"].split("/")[-1]
    stored = session.scalar(select(ReportShare).where(ReportShare.scan_id == after.id))
    assert stored.token_digest != token and len(stored.token_digest) == 64
    shared = client.get(f"/api/v1/shares/{token}")
    assert shared.status_code == 200
    assert shared.headers["cache-control"] == "no-store"
    assert "id" not in shared.json()["project"]
    assert "scan_id" not in shared.json()["findings"][0]
    assert "token=secret" not in shared.text
    assert client.get(f"/api/v1/scans/{after.id}/export?format=json").status_code == 200
    csv = client.get(f"/api/v1/scans/{after.id}/export?format=csv")
    assert "'=Spreadsheet" in csv.text
    assert client.get(f"/api/v1/scans/{after.id}/export?format=exe").status_code == 422
    assert client.post(f"/api/v1/scans/{after.id}/shares/revoke").status_code == 200
    assert client.get(f"/api/v1/shares/{token}").status_code == 404
    link = client.post(f"/api/v1/scans/{after.id}/shares").json()
    for row in session.scalars(select(ReportShare).where(ReportShare.scan_id == after.id)):
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    session.commit()
    assert client.get("/api/v1/shares/" + link["path"].split("/")[-1]).status_code == 404
    assert client.get(f"/api/v1/projects/{project.id}/history").json()[0]["id"] == str(after.id)
    assert client.get("/api/v1/scans/" + str(uuid4()) + "/report").status_code == 404


def test_pdf_escapes_untrusted_content_and_exports_real_pdf(client, session):
    _, scan = make_scan(session, checks=[Check("a", "Access", "PASS", "A", "")])
    session.commit()
    report = ReportService(session).report(scan.id)
    report["project"]["name"] = '<script>fetch("http://127.0.0.1/")</script>'
    html = render_html(report)
    assert "<script>" not in html and "&lt;script&gt;" in html
    pdf = client.get(f"/api/v1/scans/{scan.id}/export?format=pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF-")


def test_queue_admission_deduplication_and_capacity(client, session, monkeypatch):
    monkeypatch.setattr(
        "app.repositories.records.get_settings", lambda: Settings(scan_max_active=1)
    )
    project = client.post(
        "/api/v1/projects",
        json={"name": "Queue fixture", "website_url": "https://fixture.example/"},
    ).json()
    first = client.post(f"/api/v1/projects/{project['id']}/scans").json()
    assert client.post(f"/api/v1/projects/{project['id']}/scans").json()["id"] == first["id"]
    assert Records(session).claim_scan(__import__("uuid").UUID(first["id"]))
    another = Project(name="Queued", website_url="https://second.example/")
    session.add(another)
    session.flush()
    pending = Scan(project_id=another.id, status=ScanStatus.PENDING)
    session.add(pending)
    session.flush()
    assert not Records(session).claim_scan(pending.id)
    assert pending.id in Records(session).pending_scans(10)


def test_pipeline_persists_real_findings_without_provider_calls(session, monkeypatch):
    settings = Settings(audit_browser_enabled=False, crawl_min_delay=0)
    monkeypatch.setattr("app.services.crawls.get_settings", lambda: settings)

    async def forbidden(*args, **kwargs):
        raise AssertionError("A static scan must never call an LLM")

    monkeypatch.setattr("app.engines.agent.provider.HuggingFaceProvider.generate_action", forbidden)
    project = Project(name="Fixture", website_url="https://fixture.example/")
    session.add(project)
    session.flush()
    scan = Scan(project_id=project.id, status=ScanStatus.PENDING)
    session.add(scan)
    session.commit()

    def serve(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, stream=httpx.ByteStream(b"User-agent: *\nAllow: /"))
        if request.url.path == "/sitemap.xml":
            return httpx.Response(
                200,
                stream=httpx.ByteStream(
                    b"<urlset><url><loc>https://fixture.example/</loc><lastmod>2000-01-01</lastmod></url></urlset>"
                ),
            )
        if request.url.path == "/llms.txt":
            return httpx.Response(
                200, stream=httpx.ByteStream(b"# Fixture\n## Docs\n- [Guide](/docs)")
            )
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            stream=httpx.ByteStream(b"<title>Fixture</title><h1>Fixture</h1><button></button>"),
        )

    @contextmanager
    def factory():
        yield session

    execute_scan(
        scan.id,
        factory,
        lambda url, config: WebsiteCrawler(
            url, config, Fetcher(URLValidator(url), config, httpx.MockTransport(serve))
        ),
    )
    session.expire_all()
    result = session.get(Scan, scan.id)
    assert result.status == ScanStatus.COMPLETED
    assert result.overall_score is not None
    assert result.audit_summary["phase"] == "COMPLETED"
    findings = list(session.scalars(select(Finding).where(Finding.scan_id == scan.id)))
    assert any(f.evidence["rule"] == "semantic.buttons" for f in findings)
    assert all(f.recommendation and f.evidence for f in findings)


def test_comparison_keeps_query_variants_distinct_without_exposing_queries(session):
    old = [
        Check(
            "semantic.inputs",
            "Actionability",
            "FAIL",
            "Label",
            "",
            url="https://fixture.example/form",
            evidence={"page_key": "query-one"},
        ),
        Check(
            "semantic.inputs",
            "Actionability",
            "FAIL",
            "Label",
            "",
            url="https://fixture.example/form",
            evidence={"page_key": "query-two"},
        ),
    ]
    project, _ = make_scan(session, checks=old, days=-2)
    _, after = make_scan(
        session,
        project,
        [
            Check(
                "semantic.inputs",
                "Actionability",
                "PASS",
                "Label",
                "",
                url="https://fixture.example/form",
                evidence={"page_key": "query-one"},
            )
        ],
        days=-1,
    )
    result = ReportService(session).compare(after.id)
    assert len(result["resolved"]) == 1
    assert len(result["not_retested"]) == 1


def test_browser_csp_restricted_api_content_is_unknown_not_pass():
    calls = []

    def serve(request):
        calls.append(request.url.path)
        if request.url.path == "/robots.txt":
            return httpx.Response(404, stream=httpx.ByteStream(b""))
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            stream=httpx.ByteStream(
                b'<html><title>App</title><script>fetch("/api/content").then(r=>r.text()).then(t=>document.body.innerHTML=t)</script><body>Loading</body></html>'
            ),
        )

    raw = inspect_html(b"<title>App</title><body>Loading</body>", "https://fixture.example/")
    page = SimpleNamespace(
        id=uuid4(), url="https://fixture.example/", status_code=200, page_metadata={"audit": raw}
    )
    checks = asyncio.run(
        render_pages(
            [page],
            Settings(crawl_min_delay=0, audit_render_timeout=10),
            transport=httpx.MockTransport(serve),
        )
    )
    result = next(c for c in checks if c.rule == "render.js_dependency")
    assert result.status == "UNKNOWN"
    assert (
        result.evidence["policy_violations"]
        or result.evidence["failed_requests"]
        or result.evidence["script_errors"]
    )
    assert "/api/content" not in calls
