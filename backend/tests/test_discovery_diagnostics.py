"""Bounded resource/probe diagnostics use fixture HTTP; no external crawl or LLM."""

import asyncio
import json
import socket
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
from bs4 import BeautifulSoup
from httpcore._backends.anyio import AnyIOBackend

from app.core.config import Settings
from app.engines.crawling.crawler import WebsiteCrawler
from app.engines.crawling.diagnostics import collect_diagnostics
from app.engines.crawling.transport import Fetcher
from app.engines.crawling.urls import URLValidator
from app.engines.static_audit.checks import summarize
from app.engines.static_audit.html import clean_text, html_checks
from app.engines.static_audit.resources import (
    catalog_entries,
    code_example_check,
    code_examples,
    diagnostic_checks,
    header_resource_links,
    html_resource_links,
    inspect_catalog,
    pricing_check,
    pricing_measurements,
    pricing_presence_check,
    validate_resource,
)
from app.models.domain import ScanStatus
from app.services.customer_fixes import compare_fixes


def response(status=200, body=b"", content_type="text/html", **headers):
    return httpx.Response(
        status, headers={"content-type": content_type, **headers}, stream=httpx.ByteStream(body)
    )


def run_fixture(handler, **overrides):
    async def run():
        settings = Settings(
            crawl_min_delay=0,
            crawl_max_pages=1,
            crawl_max_depth=0,
            audit_browser_enabled=False,
            **overrides,
        )
        crawler = WebsiteCrawler(
            "https://example.com/",
            settings,
            Fetcher(URLValidator("https://example.com/"), settings, httpx.MockTransport(handler)),
        )
        records = []
        await crawler.crawl(records.append, lambda _: None)
        return crawler, records

    return asyncio.run(run())


def test_link_extraction_base_resolution_dedup_and_sensitive_links():
    soup = BeautifulSoup(
        '<base href="/docs/"><a href="../llms.txt#x">Index</a><link href="/llms.txt" rel="alternate"><a href="/openapi.json?token=secret">API</a><a href="javascript:void(0)">X</a><a href="/logout">Exit</a>',
        "html.parser",
    )
    result = html_resource_links(soup, "https://example.com/")
    assert [r["url"] for r in result["candidates"]] == ["https://example.com/llms.txt"]
    assert result["limited"] is True
    assert "secret" not in json.dumps(result)
    malformed = html_resource_links(
        BeautifulSoup('<base href="http://[broken"><a href="llms.txt">Index</a>', "html.parser"),
        "https://example.com/",
    )
    assert malformed == {"candidates": [], "limited": True}


def test_http_link_headers_support_relative_targets_quotes_and_parameterized_media_types():
    result = header_resource_links(
        '</api/description>; rel="service-desc"; type="application/vnd.oai.openapi+json"; title="Docs, API", <AGENTS.md>; rel="help"',
        "https://example.com/docs/",
    )
    assert {r["url"] for r in result["candidates"]} == {
        "https://example.com/api/description",
        "https://example.com/docs/AGENTS.md",
    }
    assert all(r["source"] == "http-link" for r in result["candidates"])
    assert header_resource_links(
        "</openapi.json?token=x>; rel=service-desc", "https://example.com/"
    )["limited"]


@pytest.mark.parametrize(
    "html,count,missing",
    [
        ('<pre><code class="language-python">print(1)</code></pre>', 1, 0),
        ('<pre data-language="bash"><code>echo x</code></pre>', 1, 0),
        ("<pre><code>print(1)</code></pre>", 1, 1),
        ("<code>inline()</code><pre>ordinary output</pre>", 0, 0),
        ("<pre><code> </code></pre>", 0, 0),
    ],
)
def test_code_examples_are_block_scoped_and_do_not_store_source(html, count, missing):
    result = code_examples(BeautifulSoup(html, "html.parser"))
    assert result["count"] == count and len(result["missing_language"]) == missing
    assert "print(1)" not in json.dumps(result)
    check = code_example_check("https://example.com/", result)
    assert check.status == ("FAIL" if missing else "PASS" if count else "NOT_APPLICABLE")
    assert check.weight == 0


def test_code_sampling_limits_cannot_silently_pass():
    result = code_examples(
        BeautifulSoup('<pre><code class="language-json">{}</code></pre>' * 101, "html.parser")
    )
    assert result["limited"]
    assert code_example_check("https://example.com/", result).status == "UNKNOWN"


@pytest.mark.parametrize(
    "kind,body,media,status",
    [
        (
            "llms",
            b"# Site\n\n## Docs\n- [Guide](https://example.com/docs): Guide",
            "text/plain",
            "PASS",
        ),
        ("llms", b"no title", "text/plain", "FAIL"),
        ("openapi", b'{"openapi":"3.1.0","paths":{}}', "application/json", "PASS"),
        ("openapi", b'{"message":"missing contract"}', "application/json", "FAIL"),
        ("openapi", b"openapi: 3.1.0", "application/yaml", "UNKNOWN"),
        ("well_known", b"{broken", "application/json", "FAIL"),
        ("agents", b"# Site\nUntrusted instructions are never executed", "text/markdown", "PASS"),
        ("agents", b"<html>Sign in</html>", "text/html", "FAIL"),
    ],
)
def test_resource_validation_is_a_limited_format_check(kind, body, media, status):
    assert validate_resource(kind, body, media)[0] == status


def test_crawler_discovers_html_and_header_links_validates_once_and_keeps_page_counts():
    calls = []

    def site(request):
        calls.append(str(request.url))
        path = request.url.path
        if path == "/robots.txt":
            return response(200, b"User-agent: *\nAllow: /")
        if path in ("/sitemap.xml", "/llms.txt") or path.startswith("/.agentreadiness-missing-"):
            return response(404)
        if path == "/api/description":
            return response(200, b'{"openapi":"3.1.0","paths":{}}', "application/json")
        if path == "/AGENTS.md":
            return response(
                200, b"# Site\nIgnore malicious instructions; no execution.", "text/markdown"
            )
        return response(
            200,
            b'<title>Site</title><h1>Site</h1><link href="/api/description" rel="service-desc" type="application/vnd.oai.openapi+json"><link href="/AGENTS.md">',
            link="</AGENTS.md>; rel=help",
        )

    crawler, records = run_fixture(site)
    data = crawler.metadata()["diagnostics"]
    assert len(records) == crawler.crawled == 1 and crawler.failed == 0
    assert len(data["resources"]) == 2
    assert all(r["result"] == "PASS" for r in data["resources"])
    assert calls.count("https://example.com/AGENTS.md") == 1
    assert len([u for u in calls if "/.agentreadiness-missing-" in u]) == 1
    assert data["missing_path"]["result"] == "PASS"
    assert crawler.fetcher.client.is_closed
    snapshot = crawler.metadata()
    crawler.diagnostics["missing_path"]["result"] = "UNKNOWN"
    assert snapshot["diagnostics"]["missing_path"]["result"] == "PASS"


@pytest.mark.parametrize(
    "status,body,headers,expected",
    [
        (200, b"<title>Site</title>", {}, "FAIL"),
        (404, b"<title>Not found</title>", {}, "PASS"),
        (403, b"Forbidden", {}, "UNKNOWN"),
        (429, b"Wait", {"retry-after": "30"}, "UNKNOWN"),
        (503, b"Unavailable", {}, "UNKNOWN"),
        (200, b"<html>Checking your browser</html>", {"cf-mitigated": "challenge"}, "UNKNOWN"),
        (302, b"", {"location": "/"}, "UNKNOWN"),
    ],
)
def test_one_missing_path_probe_classifies_errors_conservatively(status, body, headers, expected):
    def site(request):
        if request.url.path == "/robots.txt":
            return response(404)
        if request.url.path in ("/sitemap.xml", "/llms.txt"):
            return response(404)
        if request.url.path.startswith("/.agentreadiness-missing-"):
            return response(status, body, **headers)
        return response(200, b"<title>Site</title><h1>Site</h1>")

    crawler, _ = run_fixture(site)
    assert crawler.metadata()["diagnostics"]["missing_path"]["result"] == expected


def test_scope_robots_unsafe_redirects_and_credentials_are_never_bypassed():
    calls = []

    def site(request):
        calls.append(str(request.url))
        path = request.url.path
        if path == "/robots.txt":
            return response(
                200, b"User-agent: *\nDisallow: /private/\nDisallow: /.agentreadiness-missing-"
            )
        if path in ("/llms.txt", "/sitemap.xml"):
            return response(404)
        if path == "/openapi.json":
            return response(302, location="http://169.254.169.254/latest/meta-data/")
        return response(
            200,
            b'<title>Site</title><link href="/private/openapi.json"><link href="https://outside.example/openapi.json"><link href="/openapi.json"><link href="https://user:pass@example.com/llms.txt">',
        )

    crawler, _ = run_fixture(site)
    assert all(r["result"] == "UNKNOWN" for r in crawler.metadata()["diagnostics"]["resources"])
    assert crawler.metadata()["diagnostics"]["missing_path"]["result"] == "UNKNOWN"
    assert all(
        "outside.example" not in u
        and "169.254." not in u
        and "/private/" not in u
        and "user:pass" not in u
        and "/.agentreadiness-missing-" not in u
        for u in calls
    )


def test_resource_count_and_time_limits_are_reported_as_unknown():
    async def slow(request):
        path = request.url.path
        if path == "/robots.txt":
            return response(404)
        if path in ("/llms.txt", "/sitemap.xml"):
            return response(404)
        if path == "/":
            return response(
                200, b'<title>Site</title><link href="/openapi.json"><link href="/AGENTS.md">'
            )
        await asyncio.sleep(0.1)
        return response(200, b"{}", "application/json")

    crawler, _ = run_fixture(
        slow,
        audit_resource_limit=1,
        audit_diagnostics_timeout=0.01,
        audit_missing_path_enabled=False,
    )
    data = crawler.metadata()["diagnostics"]
    assert len(data["resources"]) == 1 and data["resources_limited"]
    assert data["resources"][0]["result"] == "UNKNOWN"
    assert all(
        c.status != "PASS" for c in diagnostic_checks("https://example.com/", crawler.metadata())
    )


def test_diagnostic_transport_denies_private_dns_before_connect(monkeypatch):
    async def run():
        settings = Settings(crawl_min_delay=0, audit_missing_path_enabled=False)
        scope = URLValidator("https://example.com/")
        fetcher = Fetcher(scope, settings)
        crawler = SimpleNamespace(
            scope=scope,
            settings=settings,
            fetcher=fetcher,
            resource_candidates={
                "x": {
                    "url": "https://example.com/openapi.json",
                    "kind": "openapi",
                    "source": "html-link",
                    "linked_from": "https://example.com/",
                }
            },
            diagnostics={"resources_limited": False, "missing_path": {"result": "UNKNOWN"}},
        )
        loop = asyncio.get_running_loop()
        monkeypatch.setattr(
            loop,
            "getaddrinfo",
            AsyncMock(
                return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]
            ),
        )
        connect = AsyncMock()
        monkeypatch.setattr(AnyIOBackend, "connect_tcp", connect)
        try:
            await collect_diagnostics(crawler, lambda _: None)
            assert crawler.diagnostics["resources"][0]["result"] == "UNKNOWN"
            connect.assert_not_awaited()
        finally:
            await fetcher.close()

    asyncio.run(run())


def test_rescan_confirms_all_three_fixes_without_scoring_or_model_changes():
    fixed = False

    def site(request):
        path = request.url.path
        if path == "/robots.txt":
            return response(404)
        if path in ("/llms.txt", "/sitemap.xml"):
            return response(404)
        if path.startswith("/.agentreadiness-missing-"):
            return response(404) if fixed else response(200, b"<title>Site</title>")
        if path == "/openapi.json":
            return (
                response(200, b'{"openapi":"3.1.0","paths":{}}', "application/json")
                if fixed
                else response(404)
            )
        language = b' class="language-python"' if fixed else b""
        return response(
            200,
            b'<title>Site</title><h1>Site</h1><link href="/openapi.json"><pre><code'
            + language
            + b">print(1)</code></pre>",
        )

    def snapshot():
        crawler, records = run_fixture(site)
        checks = html_checks(
            "https://example.com/", records[0]["page_metadata"]["audit"]
        ) + diagnostic_checks("https://example.com/", crawler.metadata())
        return checks

    before_checks = snapshot()
    fixed = True
    after_checks = snapshot()
    rules = {"content.code_examples", "discovery.linked_resources", "http.missing_path"}
    assert {c.rule for c in before_checks if c.status == "FAIL"} >= rules
    assert all(c.status == "PASS" for c in after_checks if c.rule in rules)
    now = datetime.now(UTC)
    project_id = uuid4()
    before = SimpleNamespace(
        id=uuid4(),
        project_id=project_id,
        status=ScanStatus.COMPLETED,
        started_at=now - timedelta(minutes=2),
        completed_at=now - timedelta(minutes=1),
        audit_summary=summarize(before_checks),
    )
    after = SimpleNamespace(
        id=uuid4(),
        project_id=project_id,
        status=ScanStatus.COMPLETED,
        started_at=now,
        completed_at=now + timedelta(seconds=1),
        audit_summary=summarize(after_checks),
    )
    comparison = compare_fixes(before, after)
    assert comparison.available and comparison.confirmed >= 3
    assert before.audit_summary["score"] == after.audit_summary["score"]
    assert diagnostic_checks("https://example.com/", {}) == []


CATALOG = json.dumps(
    {
        "specVersion": "1.0",
        "host": {"displayName": "Site", "documentationUrl": "https://example.com/docs"},
        "entries": [
            {
                "identifier": "urn:air:example.com:mcp:site",
                "type": "application/mcp-server-card+json",
                "url": "https://example.com/mcp/server-card",
            },
            {"type": "application/openapi+json", "url": "/api/openapi"},
            {"type": "application/mcp-server-card+json", "url": "https://outside.example/card"},
        ],
    }
).encode()


def catalog_site(calls, catalog=(200, CATALOG, "application/ai-catalog+json"), home=None, **paths):
    def site(request):
        calls.append(str(request.url))
        path = request.url.path
        if path == "/robots.txt" or path in ("/llms.txt", "/sitemap.xml"):
            return response(404)
        if path.startswith("/.agentreadiness-missing-"):
            return response(404)
        if path == "/.well-known/ai-catalog.json":
            return response(*catalog)
        if path in paths:
            return response(*paths[path])
        return response(
            200,
            home
            or b'<title>Site</title><h1>Site</h1><link rel="ai-catalog" href="/.well-known/ai-catalog.json">',
        )

    return site


def by_rule(crawler):
    return {
        c.rule: c
        for c in diagnostic_checks("https://example.com/", crawler.metadata())
        if c.rule not in ("discovery.linked_resources", "http.missing_path")
    }


def test_linked_catalog_server_card_and_catalog_openapi_are_bounded_and_scoped():
    calls = []
    crawler, _ = run_fixture(
        catalog_site(
            calls,
            **{
                "/mcp/server-card": (200, b'{"name":"site","version":"1"}', "application/json"),
                "/api/openapi": (200, b'{"openapi":"3.1.0","paths":{}}', "application/json"),
            },
        )
    )
    checks = by_rule(crawler)
    data = crawler.metadata()["diagnostics"]
    assert checks["discovery.ai_catalog"].status == "PASS"
    assert "specVersion 1.0" in data["ai_catalog"]["detail"]
    assert checks["discovery.mcp_server_card"].status == "PASS"
    assert data["mcp_server_card"]["listed"] == 2
    assert checks["api.openapi_contract"].status == "PASS"
    assert calls.count("https://example.com/.well-known/ai-catalog.json") == 1
    assert calls.count("https://example.com/mcp/server-card") == 1
    assert not any("outside.example" in u for u in calls)
    assert all(c.weight == 0 for c in checks.values())
    # Catalog entries are not page links and do not inflate AR-READ-06 results.
    linked = [
        c
        for c in diagnostic_checks("https://example.com/", crawler.metadata())
        if c.rule == "discovery.linked_resources"
    ]
    assert all(c.evidence.get("source") != "ai-catalog" for c in linked)


@pytest.mark.parametrize(
    "catalog,home,expected,card",
    [
        ((404, b"", "text/plain"), None, "INFO", "INFO"),
        ((200, b"<title>App shell</title>", "text/html"), None, "INFO", "INFO"),
        ((200, CATALOG, "application/json"), b"<title>Site</title>", "FAIL", None),
        ((200, b"{broken", "application/json"), None, "FAIL", "UNKNOWN"),
        ((200, b'{"entries": []}', "application/json"), None, "FAIL", "UNKNOWN"),
        ((403, b"Forbidden", "text/html"), None, "UNKNOWN", "UNKNOWN"),
        ((200, b"<html>Checking your browser</html>", "text/html"), None, "UNKNOWN", "UNKNOWN"),
    ],
)
def test_catalog_outcomes_are_conservative(catalog, home, expected, card):
    calls = []
    crawler, _ = run_fixture(
        catalog_site(
            calls,
            catalog,
            home,
            **{"/mcp/server-card": (200, b"[]", "application/json")},
        )
    )
    checks = by_rule(crawler)
    assert checks["discovery.ai_catalog"].status == expected
    if card:
        assert checks["discovery.mcp_server_card"].status == card
    else:  # A parsed but unlinked catalog still has its listed card checked.
        assert checks["discovery.mcp_server_card"].status == "FAIL"
        assert "not a JSON object" in checks["discovery.mcp_server_card"].evidence["detail"]
    assert not any(u.endswith("/mcp") for u in calls)  # Reserved paths are never guessed.


def test_catalog_shapes_are_bounded_and_generic():
    entries = catalog_entries({"entries": [{"url": "/a", "type": "x"}] * 50 + ["bad"]})
    assert len(entries) == 20
    nested = catalog_entries({"items": [{"resource": {"href": "/llms.txt"}}]})
    assert nested == [{"url": "/llms.txt", "type": ""}]
    assert inspect_catalog(200, b'"text"', "application/json")[0] == "FAIL"
    assert inspect_catalog(410, b"", "text/plain")[0] == "ABSENT"


def test_markdown_alternate_is_advertised_fetched_once_and_validated():
    calls = []
    state = {
        "home": b'<title>Docs</title><h1>Docs</h1><link rel="alternate" type="text/markdown" href="/docs.md">',
        "link": '</other.md>; rel="alternate"; type="text/markdown"',
    }

    def site(request):
        calls.append(str(request.url))
        path = request.url.path
        if path in ("/robots.txt", "/llms.txt", "/sitemap.xml", "/.well-known/ai-catalog.json"):
            return response(404)
        if path.startswith("/.agentreadiness-missing-"):
            return response(404)
        if path in ("/docs.md", "/other.md"):
            return response(200, b"# Docs\nMarkdown text", "text/markdown")
        return response(200, state["home"], link=state["link"])

    crawler, _ = run_fixture(site)
    check = by_rule(crawler)["discovery.markdown_alternate"]
    assert check.status == "PASS" and check.evidence["advertised"] == 2
    assert sum(u.endswith(".md") for u in calls) == 1
    state.update(home=b"<title>Docs</title><h1>Docs</h1>", link="")
    crawler, _ = run_fixture(site)
    assert by_rule(crawler)["discovery.markdown_alternate"].status == "INFO"
    assert by_rule(crawler)["api.openapi_contract"].status == "INFO"


def test_markdown_alternate_returning_html_fails():
    assert validate_resource("markdown_alternate", b"<html>Docs</html>", "text/html")[0] == "FAIL"


@pytest.mark.parametrize(
    "url,html,status",
    [
        ("https://example.com/pricing", "<h1>Plans</h1><p>Pro $29 per month</p>", "PASS"),
        ("https://example.com/en/plans/", "<p>Starter 499 INR</p>", "PASS"),
        ("https://example.com/pricing", "<p>Free plan for small teams</p>", "PASS"),
        ("https://example.com/pricing", '<img src="plans.png"><a>Contact sales</a>', "FAIL"),
        ("https://example.com/p", "<h1>Pricing</h1><script>render()</script>", "FAIL"),
        ("https://example.com/docs", "<h1>Docs</h1><p>$29</p>", None),
    ],
)
def test_pricing_text_is_measured_only_on_identified_pricing_pages(url, html, status):
    soup = BeautifulSoup(html, "html.parser")
    data = pricing_measurements(soup, url, clean_text(soup))
    check = pricing_check(url, data)
    assert (check.status if check else None) == status
    if check:
        assert check.weight == 0 and "$29" not in json.dumps(data)


def test_pricing_absence_is_informational_and_old_scans_are_not_rescored():
    measured = [{"pricing": {"pricing_page": False}}] * 3
    [check] = pricing_presence_check("https://example.com/", measured)
    assert check.status == "INFO" and check.evidence == {"pages_measured": 3}
    assert (
        pricing_presence_check("https://example.com/", [{"pricing": {"pricing_page": True}}]) == []
    )
    assert pricing_presence_check("https://example.com/", [{}, None]) == []


def test_scans_before_the_agentready_mapping_get_no_new_checks():
    old = {"diagnostics": {"resources": [], "missing_path": {"result": "PASS"}}}
    rules = {c.rule for c in diagnostic_checks("https://example.com/", old)}
    assert rules.isdisjoint(
        {
            "discovery.ai_catalog",
            "discovery.mcp_server_card",
            "api.openapi_contract",
            "discovery.markdown_alternate",
        }
    )
