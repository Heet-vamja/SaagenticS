"""External reference mapping is deterministic, bounded and never certification."""

import json

import pytest

from app.cli.agentready_sync import SNAPSHOT, compare
from app.engines.standards.coverage import MAX_CHECKS, REFERENCE, reference_coverage


def row(result, id):
    return next(item for item in result.requirements if item.id == id)


def check(rule, status="PASS", url="https://fixture.example/", **extra):
    return {"rule": rule, "status": status, "url": url, **extra}


def test_reviewed_spec_inventory_and_explicit_unmapped_gaps():
    result = reference_coverage([], "https://fixture.example/")
    ids = {item.id for item in result.requirements}
    assert len(ids) == len(result.requirements) == 24
    assert "AR-READ-10" not in ids
    assert result.spec_version == "2.0.1"
    assert result.mapping_version == "1.2.0"
    assert sum(item.implementation == "PARTIAL" for item in result.requirements) == 14
    assert all(item.assessment == "NOT_TESTED" for item in result.requirements)
    # Only discovery-level ACT signals are mapped; operating an API/MCP is never assessed.
    assert {
        item.id
        for item in result.requirements
        if item.stage == "ACT" and item.implementation == "PARTIAL"
    } == {"AR-ACT-02", "AR-ACT-04"}
    assert {item.id for item in result.requirements if item.level == "MUST"} == {
        "AR-FIND-01",
        "AR-READ-01",
        "AR-READ-02",
        "AR-ACT-10",
    }


def test_passing_local_signals_never_become_requirement_passes_or_conformance():
    signals = [check(rule) for item in REFERENCE["requirements"] for rule in item["rules"]]
    result = reference_coverage(signals, "https://fixture.example/")
    assert result.conformance == "NOT_ASSESSED"
    assert all(item.assessment != "PASS" for item in result.requirements)
    assert row(result, "AR-READ-08").assessment == "PARTIAL_EVIDENCE"
    assert row(result, "AR-ACT-10").assessment == "NOT_TESTED"


def test_unknown_and_not_applicable_signals_cannot_establish_a_pass():
    result = reference_coverage(
        [
            check("render.js_dependency", "UNKNOWN"),
            check("schema.syntax", "NOT_APPLICABLE"),
        ],
        "https://fixture.example/",
    )
    assert row(result, "AR-READ-01").assessment == "INCONCLUSIVE"
    assert row(result, "AR-READ-01").observations.passed == 0
    assert row(result, "AR-READ-08").assessment == "NOT_TESTED"
    assert row(result, "AR-READ-08").observations.not_applicable == 1


def test_training_policy_and_restricted_response_are_not_access_success():
    result = reference_coverage(
        [
            check("robots.ai_policy", "INFO", evidence={"known": True, "allowed": False}),
            check("http.status", "FAIL", evidence={"status": 403}),
        ],
        "https://fixture.example/",
    )
    assert row(result, "AR-FIND-01").observations.informational == 1
    assert row(result, "AR-READ-02").observations.inconclusive == 1
    assert row(result, "AR-READ-02").observations.passed == 0
    assert result.conformance == "NOT_ASSESSED"


@pytest.mark.parametrize(
    "url",
    [
        "https://fixture.example/docs",
        "https://other.example/",
        "https://docs.fixture.example/",
        "https://fixture.example/?variant=x",
        "javascript://fixture.example/",
    ],
)
def test_homepage_requirement_cannot_use_other_page_evidence(url):
    result = reference_coverage(
        [check("render.js_dependency", url=url)], "https://fixture.example/"
    )
    assert row(result, "AR-READ-03").assessment == "NOT_TESTED"
    assert row(result, "AR-READ-01").assessment == "PARTIAL_EVIDENCE"


def test_www_homepage_alias_and_mixed_measurements_are_disclosed():
    result = reference_coverage(
        [
            check("render.js_dependency", url="https://www.fixture.example/"),
            check("render.js_dependency", "UNKNOWN"),
        ],
        "https://fixture.example/",
    )
    item = row(result, "AR-READ-03")
    assert item.assessment == "PARTIAL_EVIDENCE"
    assert item.observations.passed == item.observations.inconclusive == 1


def test_html_labels_our_commerce_and_unrelated_checks_do_not_prove_action_capabilities():
    result = reference_coverage(
        [
            check("semantic.inputs"),
            check("navigation.links"),
            check("payments.stripe"),
            check("authentication.otp"),
            check("mcp.available"),
        ],
        "https://fixture.example/",
    )
    assert all(item.assessment == "NOT_TESTED" for item in result.requirements)


def test_malformed_empty_and_unknown_inputs_fail_closed():
    for checks in (
        None,
        {},
        "not checks",
        [None, "x", check("schema.syntax", "BOGUS"), {"status": []}],
    ):
        result = reference_coverage(checks, "https://fixture.example/")
        assert all(item.assessment == "NOT_TESTED" for item in result.requirements)


def test_measurement_budget_and_no_raw_evidence_leakage():
    result = reference_coverage(
        [check("schema.syntax", evidence={"secret": "not-for-output"})] * (MAX_CHECKS + 1),
        "https://fixture.example/",
    )
    assert result.checks_truncated is True
    assert row(result, "AR-READ-08").observations.passed == MAX_CHECKS
    assert "not-for-output" not in result.model_dump_json()
    assert "fixture.example" not in result.model_dump_json()


def test_mapping_matches_pinned_upstream_requirement_facts():
    snapshot = json.loads(SNAPSHOT.read_text())
    assert compare(REFERENCE, snapshot) == []
    assert snapshot["version"] == REFERENCE["spec_version"]
    assert "AR-READ-10" in snapshot["retired"]
    assert "requirement" not in json.dumps(snapshot["requirements"])  # No copied spec text.


def test_upstream_drift_is_reported_not_silently_accepted():
    snapshot = json.loads(SNAPSHOT.read_text())
    changed = {
        **snapshot,
        "version": "2.1",
        "requirements": [
            {**item, "level": "MUST"} if item["id"] == "AR-READ-11" else item
            for item in snapshot["requirements"]
            if item["id"] != "AR-ACT-09"
        ]
        + [{"id": "AR-READ-12", "category": "READ", "level": "SHOULD"}],
        "retired": [*snapshot["retired"], "AR-FIND-04"],
    }
    drift = compare(REFERENCE, changed)
    assert "Missing locally: AR-READ-12" in drift
    assert "Not upstream: AR-ACT-09" in drift
    assert any(line.startswith("Changed AR-READ-11") for line in drift)
    assert "Retired upstream but mapped: AR-FIND-04" in drift
    assert any(line.startswith("Spec version") for line in drift)


@pytest.mark.parametrize(
    "rule,requirement",
    [
        ("discovery.ai_catalog", "AR-FIND-04"),
        ("discovery.markdown_alternate", "AR-READ-09"),
        ("content.pricing_text", "AR-READ-11"),
        ("api.openapi_contract", "AR-ACT-02"),
        ("discovery.mcp_server_card", "AR-ACT-04"),
    ],
)
def test_new_discovery_signals_are_partial_evidence_only(rule, requirement):
    result = reference_coverage([check(rule)], "https://fixture.example/")
    item = row(result, requirement)
    assert item.assessment == "PARTIAL_EVIDENCE" and item.implementation == "PARTIAL"
    assert row(result, "AR-ACT-10").assessment == "NOT_TESTED"
    assert result.conformance == "NOT_ASSESSED"
