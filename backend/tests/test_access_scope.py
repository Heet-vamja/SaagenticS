"""Scanner access, declared provider policies and verified tasks stay distinct."""

from types import SimpleNamespace

import pytest

from app.engines.crawling.parsers import RobotsHandler
from app.engines.static_audit.checks import normalize_access_check, summarize
from app.engines.static_audit.site import site_checks
from app.services.customer_fixes import indexed_checks
from app.services.free_reports import _evidence_summary, access_policies, score_summary
from app.services.report_pdf import render_free_html
from app.services.static_audits import page_checks

URL = "https://fixture.example/"


def robots_metadata(
    status=200, body=b"User-agent: *\nDisallow: /\nUser-agent: OAI-SearchBot\nAllow: /\n"
):
    handler = RobotsHandler("AgentReadinessBot/0.1")
    handler.parse(status, body)
    return {"robots": {"https://fixture.example": handler.metadata(URL)}}


def test_scanner_denial_and_searchbot_allowance_are_independent():
    metadata = robots_metadata()
    checks = site_checks(URL, metadata)
    own = next(check for check in checks if check.rule == "robots.access")
    assert own.status == "INFO"
    assert "our crawler" in own.title
    assert own.weight == 0
    policies = access_policies(metadata)
    assert next(row for row in policies if row["kind"] == "SCANNER")["policy"] == "DISALLOWED"
    assert (
        next(row for row in policies if row["user_agent"] == "OAI-SearchBot")["policy"] == "ALLOWED"
    )
    assert not metadata["robots"]["https://fixture.example"]["permitted"]
    assert all(check.status == "INFO" for check in checks if check.rule == "robots.ai_policy")


@pytest.mark.parametrize("status", [401, 403, 429, 503])
def test_unavailable_robots_never_invents_provider_restrictions(status):
    metadata = robots_metadata(status, b"Denied")
    check = next(c for c in site_checks(URL, metadata) if c.rule == "robots.access")
    assert check.status == "UNKNOWN"
    assert check.weight == 0
    assert all(row["policy"] == "UNKNOWN" for row in access_policies(metadata))
    assert "denied" not in _evidence_summary(check.evidence).lower()
    summary = summarize([check])
    assert summary["score"] is None
    assert summary["counts"]["FAIL"] == 0


@pytest.mark.parametrize("status", [401, 403, 429])
def test_request_denial_keeps_observation_without_lowering_readiness(status):
    page = SimpleNamespace(url=URL, status_code=status, page_metadata={}, title=None)
    checks = page_checks(page)
    assert next(c for c in checks if c.rule == "http.status").status == "UNKNOWN"
    assert next(c for c in checks if c.rule == "http.restriction").status == "INFO"
    assert not [c for c in checks if c.status == "FAIL"]
    assert summarize(checks)["score"] is None


def test_real_broken_link_remains_a_failure():
    page = SimpleNamespace(url=URL, status_code=404, page_metadata={}, title=None)
    assert next(c for c in page_checks(page) if c.rule == "http.status").status == "FAIL"


def test_legacy_report_and_fix_center_do_not_recommend_bypassing_scanner_denials():
    state = robots_metadata()["robots"]["https://fixture.example"]
    old = {
        "rule": "robots.access",
        "status": "FAIL",
        "title": "Crawler access is restricted",
        "evidence": state,
        "weight": 3,
        "url": URL,
    }
    corrected = normalize_access_check(old)
    assert corrected["status"] == "INFO"
    assert old["status"] == "FAIL"  # Historical storage is not mutated.
    assert list(indexed_checks(SimpleNamespace(audit_summary={"checks": [old]})).values()) == [
        corrected
    ]
    score, _, _ = score_summary(
        {"checks": [old, {"rule": "page.title", "status": "PASS", "weight": 1}]}
    )
    assert score == 100


def test_public_policy_urls_strip_queries_and_fragments():
    metadata = robots_metadata()
    state = metadata["robots"]["https://fixture.example"]
    state["url"] = URL + "?token=private#fragment"
    assert all(row["sampled_url"] == URL for row in access_policies(metadata))


def test_pdf_explains_policy_scope_and_escapes_identities():
    html = render_free_html(
        {
            "access_policies": [
                {"user_agent": "<script>bot</script>", "kind": "AI_BOT", "policy": "ALLOWED"}
            ]
        }
    )
    assert "not verified provider access" in html
    assert "&lt;script&gt;bot&lt;/script&gt;" in html
    assert "<script>bot</script>" not in html
