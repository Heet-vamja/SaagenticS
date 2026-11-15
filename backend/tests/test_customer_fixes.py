"""The fix cycle uses stored evidence and mocked website HTTP, never inference."""

import hashlib
import io
import json
import shutil
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import httpx
import pytest
from protego import Protego
from sqlalchemy import select
from test_free_scan import run_fixture, submit

from app.cli.pilot_metrics import collect_metrics
from app.core.config import get_settings
from app.engines.fixes.assets import generate_assets, validate_asset
from app.engines.fixes.prompts import TEMPLATE, generate_prompts, prompt_batches
from app.models.domain import ReportFixEvent, ReportShare, Scan, ScanStatus
from app.schemas.fixes import CustomerFix
from app.services.customer_fixes import check_key, compare_fixes


def page(url="https://fixture.example/", title="Workshop Cloud", description="Observed summary"):
    return SimpleNamespace(
        url=url,
        title=title,
        meta_description=description,
        status_code=200,
        crawl_error=None,
        content_type="text/html",
        page_metadata={"internal_links": ["https://fixture.example/docs"]},
    )


def check(state="FAIL", rule="semantic.buttons", url="https://fixture.example/"):
    return {
        "rule": rule,
        "status": state,
        "url": url,
        "bucket": "Actionability",
        "title": "Controls lack accessible names",
        "description": "An observed button has no name",
        "recommendation": "Give the existing button an accurate accessible name.",
        "severity": "HIGH",
        "weight": 3,
        "evidence": {"examples": [{"tag": "button", "example": "<button></button>"}]},
    }


def scan(checks):
    return SimpleNamespace(
        id=uuid4(),
        project_id="same-project",
        status=ScanStatus.COMPLETED,
        completed_at=None,
        started_at=None,
        audit_summary={"version": "static-v1", "checks": checks},
    )


@pytest.mark.parametrize("rule", list(TEMPLATE["rules"]))
def test_each_prompt_has_context_constraints_and_verification(rule):
    prompts = generate_prompts(
        check(rule=rule, url="https://fixture.example/?token=private"),
        "Example <button></button>; password=secret123",
    )
    assert set(prompts) == {"coding_assistant", "general_llm", "developer_ticket"}
    for prompt in prompts.values():
        assert "fix-prompts-v1" in prompt and "https://fixture.example/" in prompt
        assert "token=private" not in prompt and "secret123" not in prompt
        assert "re-scan to confirm" in prompt and "untrusted data" in prompt
        assert "Preserve visual design" in prompt and "<button></button>" in prompt


def test_assets_are_grounded_in_successful_public_pages():
    blocked = page("https://fixture.example/private")
    blocked.status_code = 403
    assets, missing = generate_assets(
        [
            page(),
            page("https://fixture.example/docs", "Documentation", None),
            blocked,
            page("https://other.example/", "External"),
            page("https://fixture.example/search?secret=123", "Query"),
        ],
        "https://fixture.example/",
    )
    files = {asset.filename: asset for asset in assets}
    assert set(files) == {
        "llms.txt",
        "website.jsonld",
        "breadcrumbs.jsonld",
        "sitemap-suggestions.xml",
    }
    assert "needs a description" in files["llms.txt"].content
    assert "Observed summary" in files["llms.txt"].content
    assert all(not validate_asset(asset.filename, asset.content) for asset in assets)
    combined = "\n".join(asset.content for asset in assets)
    assert all(
        value not in combined
        for value in ("private", "other.example", "secret=123", "Organization", '"price"')
    )
    assert any("Organization" in item for item in missing)


def test_missing_name_or_unobserved_hierarchy_is_not_invented():
    assets, missing = generate_assets([page(title=None)], "https://fixture.example/")
    assert {asset.filename for asset in assets} == {"sitemap-suggestions.xml"}
    assert any("homepage" in item for item in missing)
    home = page()
    home.page_metadata = {"internal_links": []}
    assets, _ = generate_assets([home, page("https://fixture.example/deep/page")], home.url)
    assert "breadcrumbs.jsonld" not in {asset.filename for asset in assets}


@pytest.mark.parametrize(
    "filename,content",
    [
        ("website.jsonld", "{broken}"),
        ("website.jsonld", '{"@context":"https://evil.example","@type":"WebSite"}'),
        (
            "website.jsonld",
            '{"@context":"https://schema.org","@type":"WebSite","name":"A","url":"http://127.0.0.1/"}',
        ),
        ("website.jsonld", '{"@context":"https://schema.org","@type":"Product"}'),
        ("llms.txt", "# Site\n## Docs\n- [Bad](javascript:alert(1))"),
        ("llms.txt", "<html>error</html>"),
        ("robots-policy-proposal.txt", "Allow: /"),
        ("robots-policy-proposal.txt", "User-agent:\nDisallow: /"),
        (
            "sitemap-suggestions.xml",
            '<!DOCTYPE foo [<!ENTITY x SYSTEM "file:///etc/passwd">]><foo>&x;</foo>',
        ),
        (
            "sitemap-suggestions.xml",
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>http://localhost/</loc></url></urlset>',
        ),
    ],
)
def test_invalid_assets_are_rejected(filename, content):
    assert validate_asset(filename, content)


def test_explicit_robots_preset_does_not_allow_unseen_private_paths():
    assets, _ = generate_assets(
        [page(), page("https://fixture.example/docs")],
        "https://fixture.example/",
        "block_training",
    )
    policy = Protego.parse(
        next(asset.content for asset in assets if asset.filename.startswith("robots-"))
    )
    assert policy.can_fetch("https://fixture.example/docs", "OAI-SearchBot")
    assert not policy.can_fetch("https://fixture.example/private", "OAI-SearchBot")
    assert not policy.can_fetch("https://fixture.example/docs", "GPTBot")


@pytest.mark.parametrize(
    "state,expected",
    [
        ("PASS", "VERIFIED_FIXED"),
        ("FAIL", "STILL_FAILING"),
        ("UNKNOWN", "NOT_RETESTED"),
        ("NOT_APPLICABLE", "NOT_RETESTED"),
        ("INFO", "NOT_RETESTED"),
        (None, "NOT_RETESTED"),
    ],
)
def test_fix_requires_same_rule_page_and_explicit_pass(state, expected):
    result = compare_fixes(scan([check()]), scan([check(state)] if state else []))
    assert result.results[0].status == expected
    assert result.confirmed == int(expected == "VERIFIED_FIXED")


def test_duplicate_unknown_failed_scan_different_rubric_and_other_page_never_verify():
    before = scan([check()])
    assert compare_fixes(before, scan([check("PASS"), check("UNKNOWN")])).confirmed == 0
    after = scan([check("PASS")])
    after.status = ScanStatus.FAILED
    assert compare_fixes(before, after).confirmed == 0
    after.status = ScanStatus.COMPLETED
    after.audit_summary["version"] = "different"
    assert compare_fixes(before, after).confirmed == 0
    assert (
        compare_fixes(before, scan([check("PASS", url="https://fixture.example/other")])).confirmed
        == 0
    )
    assert check_key(check()) != check_key(check(rule="render.semantic.buttons"))


@pytest.fixture
def scheduled(client, monkeypatch):
    jobs = []

    async def capture(scan_id):
        jobs.append(scan_id)

    monkeypatch.setattr("app.api.routes.execute_scan", capture)
    monkeypatch.setattr("app.api.fix_routes.execute_scan", capture)
    return jobs


def test_local_saas_site_apply_and_rescan_verifies_real_checks(
    client, session, scheduled, monkeypatch, tmp_path
):
    settings = get_settings()
    monkeypatch.setattr(settings, "audit_browser_enabled", False)
    monkeypatch.setattr(settings, "crawl_min_delay", 0)
    original = Path(__file__).parent / "fixtures" / "saas_site"
    fixed = tmp_path / "fixed"
    shutil.copytree(original, fixed)
    active = original

    def serve(request):
        file = active / (request.url.path.lstrip("/") or "index.html")
        if not file.is_file():
            return httpx.Response(404, stream=httpx.ByteStream(b""))
        return httpx.Response(
            200,
            headers={"content-type": "text/html" if file.suffix == ".html" else "text/plain"},
            stream=httpx.ByteStream(file.read_bytes()),
        )

    forbidden = Mock(side_effect=AssertionError("The fix cycle must not call an LLM"))
    _, token, before, _ = submit(client, session)
    run_fixture(before.id, session, serve, agent_provider_factory=forbidden)
    path = f"/api/v1/free-reports/{token}"
    response = client.get(path + "/fix-center")
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    center = response.json()
    assert center["agent_status"] == "NOT_RUN"
    button = next(fix for fix in center["fixes"] if "Controls lack" in fix["title"])
    assert "<button" in button["evidence"]
    for event in ("PROMPT_COPIED", "FIX_APPLIED"):
        assert (
            client.post(
                path + "/fix-events", json={"event_type": event, "fix_key": button["key"]}
            ).status_code
            == 200
        )
    assert client.get(path + "/fix-center").json()["comparison"]["confirmed"] == 0
    for event in ("USEFUL", "USEFUL", "PRICE_INTERESTED"):
        assert client.post(path + "/fix-events", json={"event_type": event}).status_code == 200
    asset = client.get(path + "/assets/llms.txt")
    assert asset.status_code == 200 and "Workshop Cloud" in asset.text
    pack = client.get(path + "/fix-pack.zip")
    assert pack.status_code == 200
    with zipfile.ZipFile(io.BytesIO(pack.content)) as archive:
        assert {
            "llms.txt",
            "website.jsonld",
            "fix-everything-01.md",
            "READ-ME.txt",
            "report-fixes.json",
        } <= set(archive.namelist())
        assert "re-scan to confirm" in archive.read("fix-everything-01.md").decode()
        assert all(".." not in name and "/" not in name for name in archive.namelist())

    html = (
        (fixed / "index.html")
        .read_text()
        .replace('<button type="button">', '<button type="button" aria-label="Open navigation">')
    )
    html = html.replace(
        "{broken}",
        json.dumps(
            {
                "@context": "https://schema.org",
                "@type": "WebSite",
                "name": "Workshop Cloud",
                "url": "https://fixture.example/",
            }
        ),
    )
    html = html.replace(
        "</head>", '<meta name="description" content="Public sample SaaS site."></head>'
    )
    (fixed / "index.html").write_text(html)
    html = (
        (fixed / "signup.html")
        .read_text()
        .replace(
            '<input id="work-email"',
            '<label for="work-email">Work email</label><input id="work-email"',
        )
    )
    (fixed / "signup.html").write_text(html)
    active = fixed
    accepted = client.post(path + "/rescan")
    assert accepted.status_code == 201, accepted.text
    next_token = accepted.json()["report_path"].rsplit("/", 1)[-1]
    child = session.scalar(
        select(ReportShare).where(
            ReportShare.token_digest == hashlib.sha256(next_token.encode()).hexdigest()
        )
    )
    assert child.baseline_scan_id == before.id
    assert child.scan_id != before.id and scheduled[-1] == child.scan_id
    run_fixture(child.scan_id, session, serve, agent_provider_factory=forbidden)
    comparison = client.get(f"/api/v1/free-reports/{next_token}/fix-center").json()["comparison"]
    assert comparison["available"] is True and comparison["confirmed"] >= 4
    verified = {
        item["title"] for item in comparison["results"] if item["status"] == "VERIFIED_FIXED"
    }
    assert {
        "Controls lack accessible names",
        "Form fields lack accessible labels",
        "JSON-LD could not be validated",
        "Meta description is missing",
    } <= verified
    forbidden.assert_not_called()
    assert list(session.scalars(select(ReportFixEvent)))
    metrics = collect_metrics(session)
    assert metrics["confirmed_fix_domains"] >= 1
    assert metrics["self_reported_fix_applied_domains"] >= 1
    assert metrics["hypothetical_39_dollar_interest_domains"] >= 1
    assert "fixture.example" not in json.dumps(metrics)


def test_capability_expiry_pending_invalid_event_and_download(client, session, scheduled):
    _, token, record, share = submit(client, session)
    path = f"/api/v1/free-reports/{token}"
    assert client.get(path + "/fix-center").status_code == 409
    record.status = ScanStatus.COMPLETED
    record.audit_summary = {**record.audit_summary, "version": "static-v1", "checks": [check()]}
    session.commit()
    assert (
        client.post(
            path + "/fix-events", json={"event_type": "FIX_APPLIED", "fix_key": "other-report"}
        ).status_code
        == 404
    )
    assert (
        client.post(path + "/fix-events", json={"event_type": "VERIFIED_FIXED"}).status_code == 422
    )
    assert client.get(path + "/fix-center?robots_preset=unsafe").status_code == 422
    assert client.get(path + "/assets/unlisted.jsonld").status_code == 404
    share.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    session.commit()
    for suffix in ("/fix-center", "/fix-pack.zip", "/assets/llms.txt"):
        assert client.get(path + suffix).status_code == 404
    assert client.post(path + "/rescan").status_code == 404
    assert client.post(path + "/fix-events", json={"event_type": "USEFUL"}).status_code == 404


def test_prompt_pack_is_split_into_bounded_batches():
    fix = CustomerFix(
        key="sample",
        title="Sample",
        category="Readability",
        severity="HIGH",
        url=None,
        evidence="Sample",
        recommendation="Fix",
        template_version="v1",
        prompts={"coding_assistant": "x" * 4000},
        status="OPEN",
    )
    batches = prompt_batches([fix] * 20)
    assert len(batches) > 1 and all(len(batch) <= 24000 for batch in batches)


def test_newly_applied_patch_on_still_failing_rescan_awaits_further_verification(
    client, session, scheduled
):
    _, token, baseline, _ = submit(client, session)
    baseline.status = ScanStatus.COMPLETED
    baseline.audit_summary = {**baseline.audit_summary, "version": "static-v1", "checks": [check()]}
    session.commit()
    response = client.post(f"/api/v1/free-reports/{token}/rescan")
    assert response.status_code == 201
    next_token = response.json()["report_path"].rsplit("/", 1)[-1]
    share = session.scalar(
        select(ReportShare).where(
            ReportShare.token_digest == hashlib.sha256(next_token.encode()).hexdigest()
        )
    )
    after = session.get(Scan, share.scan_id)
    after.status = ScanStatus.COMPLETED
    after.audit_summary = {**after.audit_summary, "version": "static-v1", "checks": [check()]}
    session.commit()
    path = f"/api/v1/free-reports/{next_token}"
    center = client.get(path + "/fix-center").json()
    assert center["fixes"][0]["status"] == "STILL_FAILING"
    key = center["fixes"][0]["key"]
    assert (
        client.post(
            path + "/fix-events", json={"event_type": "FIX_APPLIED", "fix_key": key}
        ).status_code
        == 200
    )
    updated = client.get(path + "/fix-center").json()
    assert updated["fixes"][0]["status"] == "FIX_APPLIED"
    assert updated["comparison"]["confirmed"] == 0


def test_new_diagnostics_persist_generate_prompts_and_verify_on_rescan(
    client, session, scheduled, monkeypatch
):
    settings = get_settings()
    monkeypatch.setattr(settings, "audit_browser_enabled", False)
    monkeypatch.setattr(settings, "crawl_min_delay", 0)
    fixed = False

    def serve(request):
        path = request.url.path
        if path == "/robots.txt":
            return httpx.Response(404, stream=httpx.ByteStream(b""))
        if path in ("/llms.txt", "/sitemap.xml"):
            return httpx.Response(404, stream=httpx.ByteStream(b""))
        if path.startswith("/.agentreadiness-missing-"):
            return httpx.Response(
                404 if fixed else 200,
                headers={"content-type": "text/html"},
                stream=httpx.ByteStream(b"<title>Fallback</title>"),
            )
        if path == "/openapi.json":
            return httpx.Response(
                200 if fixed else 404,
                headers={"content-type": "application/json"},
                stream=httpx.ByteStream(b'{"openapi":"3.1.0","paths":{}}'),
            )
        annotation = ' class="language-python"' if fixed else ""
        html = (
            '<html><head><title>Fixture</title><meta name="description" content="Fixture"><link rel="canonical" href="https://fixture.example/"><link href="/openapi.json"></head><body><h1>Fixture</h1><nav><a href="/">Home</a></nav><pre><code'
            + annotation
            + ">print(1)</code></pre></body></html>"
        )
        return httpx.Response(
            200, headers={"content-type": "text/html"}, stream=httpx.ByteStream(html.encode())
        )

    def no_model(*args):
        raise AssertionError("Diagnostic scans must not call a model")

    _, token, before, _ = submit(client, session)
    run_fixture(before.id, session, serve, agent_provider_factory=no_model)
    path = f"/api/v1/free-reports/{token}"
    center = client.get(path + "/fix-center").json()
    titles = {
        "Code examples need language annotations",
        "Linked discovery resource needs review",
        "Missing-path probe returned a success response",
    }
    assert titles <= {item["title"] for item in center["fixes"]}
    assert all(item["template_version"] == "fix-prompts-v1.1" for item in center["fixes"])
    payload = client.get(path).json()
    assert payload["standards_coverage"]["mapping_version"] == "1.2.0"
    assert payload["standards_coverage"]["spec_version"] == "2.0.1"
    assert any(
        item["id"] == "AR-READ-05" and item["assessment"] == "PARTIAL_EVIDENCE"
        for item in payload["standards_coverage"]["requirements"]
    )
    score = payload["score"]
    fixed = True
    accepted = client.post(path + "/rescan")
    assert accepted.status_code == 201, accepted.text
    next_token = accepted.json()["report_path"].rsplit("/", 1)[-1]
    child = session.scalar(
        select(ReportShare).where(
            ReportShare.token_digest == hashlib.sha256(next_token.encode()).hexdigest()
        )
    )
    run_fixture(child.scan_id, session, serve, agent_provider_factory=no_model)
    after = client.get(f"/api/v1/free-reports/{next_token}/fix-center").json()
    confirmed = {
        item["title"]
        for item in after["comparison"]["results"]
        if item["status"] == "VERIFIED_FIXED"
    }
    assert titles <= confirmed
    assert client.get(f"/api/v1/free-reports/{next_token}").json()["score"] == score
