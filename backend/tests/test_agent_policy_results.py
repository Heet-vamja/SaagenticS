from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.core.config import Settings
from app.models.domain import AdmissionBucket, WorkflowStatus
from app.services.agent_policy import client_identity, consume_admission
from app.services.agent_results import aggregate, blend


def run(
    outcome,
    *,
    status=WorkflowStatus.COMPLETED,
    verification="rules",
    category=None,
    run_number=1,
):
    return SimpleNamespace(
        status=status,
        outcome=outcome,
        verification_method=verification,
        failure_category=category,
        run_number=run_number,
    )


def request(peer: str, x_forwarded_for: str | None = None) -> Request:
    headers = []
    if x_forwarded_for is not None:
        headers.append((b"x-forwarded-for", x_forwarded_for.encode()))
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/",
            "raw_path": b"/",
            "query_string": b"",
            "headers": headers,
            "client": (peer, 12345),
            "server": ("test", 80),
        }
    )


def test_aggregate_majority_success_failure_and_tie():
    success_majority = aggregate(
        [
            run("SUCCEEDED", run_number=1),
            run("SUCCEEDED", run_number=2),
            run("FAILED", run_number=3),
        ]
    )
    assert success_majority == {
        "outcome": "SUCCEEDED",
        "consistency": False,
        "eligible_runs": 3,
        "runs_completed": 3,
        "success_rate": pytest.approx(2 / 3),
    }

    failure_majority = aggregate(
        [run("FAILED", run_number=1), run("FAILED", run_number=2), run("SUCCEEDED", run_number=3)]
    )
    assert failure_majority["outcome"] == "FAILED"
    assert failure_majority["consistency"] is False
    assert failure_majority["success_rate"] == pytest.approx(1 / 3)

    tie = aggregate([run("SUCCEEDED"), run("FAILED", run_number=2)])
    assert tie["outcome"] == "INCONCLUSIVE"
    assert tie["consistency"] is False
    assert tie["success_rate"] == pytest.approx(0.5)


def test_aggregate_consistency_and_insufficient_runs():
    consistent = aggregate([run("SUCCEEDED"), run("SUCCEEDED", run_number=2)])
    assert consistent["outcome"] == "SUCCEEDED"
    assert consistent["consistency"] is True

    one = aggregate([run("SUCCEEDED"), run("INCONCLUSIVE", run_number=2)])
    assert one["outcome"] == "SUCCEEDED"
    assert one["eligible_runs"] == 1
    assert one["runs_completed"] == 2
    assert one["consistency"] is None

    pending = aggregate([run("SUCCEEDED", status=WorkflowStatus.PENDING)])
    assert pending["outcome"] == "INCONCLUSIVE"
    assert pending["eligible_runs"] == pending["runs_completed"] == 0
    assert pending["consistency"] is None


def test_infrastructure_only_unavailable_and_mixed_infrastructure_excluded():
    only_infra = aggregate(
        [
            run("UNAVAILABLE", category="infra_error"),
            run(None, status=WorkflowStatus.FAILED, category="infra_error", run_number=2),
        ]
    )
    assert only_infra["outcome"] == "UNAVAILABLE"
    assert only_infra["eligible_runs"] == 0
    assert only_infra["runs_completed"] == 2

    mixed = aggregate([run("SUCCEEDED"), run("UNAVAILABLE", category="infra_error", run_number=2)])
    assert mixed["outcome"] == "SUCCEEDED"
    assert mixed["eligible_runs"] == 1
    assert mixed["runs_completed"] == 2
    assert mixed["success_rate"] == 1


def test_unverified_legacy_success_is_excluded_and_judged_is_disclosed():
    legacy = run("SUCCEEDED", verification="unverified")
    result = aggregate([legacy])
    assert result["outcome"] == "INCONCLUSIVE"
    assert result["eligible_runs"] == 0
    assert result["success_rate"] is None

    judged = run("SUCCEEDED", verification="judged")
    blended = blend(80, [(SimpleNamespace(task_type="FIND_PRICING"), [judged])], 0.45)
    assert blended["judged_runs"] == 1
    assert blended["provisional"] is True
    assert blended["agent_score"] == 100


def test_blend_45_percent_uses_task_majority_and_equal_task_weighting():
    task_one = SimpleNamespace(task_type="FIND_PRICING", status=WorkflowStatus.COMPLETED)
    task_two = SimpleNamespace(task_type="FIND_CONTACT", status=WorkflowStatus.COMPLETED)
    blended = blend(
        80,
        [
            (task_one, [run("SUCCEEDED")]),
            (
                task_two,
                [run("SUCCEEDED"), run("FAILED", run_number=2), run("FAILED", run_number=3)],
            ),
        ],
        0.45,
    )
    expected_agent_score = 50
    assert blended["agent_score"] == expected_agent_score
    assert blended["score"] == round(80 * 0.55 + expected_agent_score * 0.45, 1)
    assert blended["effective_weight"] == 0.45
    assert blended["eligible_runs"] == 4

    # Both tasks get one vote after majority aggregation, not one vote per run.
    assert blended["agent_score"] == 50
    assert blended["eligible_tasks"] == 2


def test_blend_excludes_repeat_ties_and_running_tasks_from_score():
    tied = SimpleNamespace(task_type="FIND_PRICING", status=WorkflowStatus.COMPLETED)
    tied_result = blend(74, [(tied, [run("SUCCEEDED"), run("FAILED", run_number=2)])], 0.45)
    assert tied_result["agent_score"] is None
    assert tied_result["score"] == 74
    assert tied_result["tasks"][0]["outcome"] == "INCONCLUSIVE"

    running = SimpleNamespace(task_type="FIND_CONTACT", status=WorkflowStatus.RUNNING)
    partial = blend(74, [(running, [run("SUCCEEDED")])], 0.45)
    assert partial["agent_score"] is None
    assert partial["score"] == 74
    assert partial["incomplete_tasks"] == 1
    assert partial["provisional"] is True


def test_blend_static_fallback_no_agent_and_no_static_score():
    legacy_task = SimpleNamespace(task_type="FIND_PRICING")
    static_fallback = blend(
        74, [(legacy_task, [run("SUCCEEDED", verification="unverified")])], 0.45
    )
    assert static_fallback["score"] == 74
    assert static_fallback["agent_score"] is None
    assert static_fallback["effective_weight"] == 0
    assert static_fallback["score_kind"] == "STATIC_READINESS"
    assert "not conclusive" in static_fallback["fallback_reason"]

    no_scores = blend(None, [], 0.45)
    assert no_scores["score"] is None
    assert no_scores["agent_score"] is None
    assert no_scores["effective_weight"] == 0
    assert no_scores["score_kind"] == "STATIC_READINESS"
    assert no_scores["fallback_reason"]

    agent_only = blend(None, [(legacy_task, [run("FAILED")])], 0.45)
    assert agent_only["score"] == 0
    assert agent_only["effective_weight"] == 1
    assert agent_only["score_kind"] == "AGENT_READINESS"


def test_client_identity_ignores_spoofed_forwarding_by_default_and_handles_ipv6():
    settings = Settings(agent_trusted_proxy_cidrs=[])
    assert client_identity(request("192.0.2.8", "198.51.100.44"), settings) == "192.0.2.8"
    assert client_identity(request("2001:db8::8", "2001:db8::99"), settings) == "2001:db8::8"


def test_client_identity_trusts_forwarded_chain_right_to_left():
    settings = Settings(agent_trusted_proxy_cidrs=["10.0.0.0/8"])
    peer = request("10.0.0.2", "203.0.113.44, 10.0.0.3")
    assert client_identity(peer, settings) == "203.0.113.44"

    ipv6_settings = Settings(agent_trusted_proxy_cidrs=["2001:db8:1::/48"])
    ipv6_peer = request("2001:db8:1::2", "2001:db8:2::44, 2001:db8:1::3")
    assert client_identity(ipv6_peer, ipv6_settings) == "2001:db8:2::44"


@pytest.mark.parametrize(
    "chain",
    [
        "not-an-ip, 10.0.0.3",
        ",".join(f"10.0.0.{index}" for index in range(1, 12)),
        "x" * 513,
    ],
)
def test_client_identity_malformed_or_overlong_chain_falls_back_to_peer(chain):
    settings = Settings(agent_trusted_proxy_cidrs=["10.0.0.0/8"])
    assert client_identity(request("10.0.0.2", chain), settings) == "10.0.0.2"


def test_consume_admission_enforces_operation_and_peer_limits(session):
    settings = Settings(agent_ip_scan_limit=2, agent_ip_task_limit=1)
    consume_admission(session, "peer-a", "scan", settings)
    consume_admission(session, "peer-a", "scan", settings)
    with pytest.raises(HTTPException) as limited_scan:
        consume_admission(session, "peer-a", "scan", settings)
    assert limited_scan.value.status_code == 429

    # Task admission has its own counter and a distinct peer gets a fresh bucket.
    consume_admission(session, "peer-a", "task", settings)
    with pytest.raises(HTTPException) as limited_task:
        consume_admission(session, "peer-a", "task", settings)
    assert limited_task.value.status_code == 429
    consume_admission(session, "peer-b", "task", settings)
    consume_admission(session, "peer-b", "scan", settings)
    session.flush()
    assert session.query(AdmissionBucket).count() == 4


def test_consume_admission_cleans_expired_buckets(session):
    session.add_all(
        [
            AdmissionBucket(
                bucket_key="expired:bucket",
                count=9,
                expires_at=datetime.now(UTC) - timedelta(seconds=1),
            ),
            AdmissionBucket(
                bucket_key="current:bucket",
                count=1,
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            ),
        ]
    )
    session.flush()

    consume_admission(session, "peer-cleanup", "scan", Settings())
    session.flush()
    remaining = {row.bucket_key for row in session.query(AdmissionBucket).all()}
    assert "expired:bucket" not in remaining
    assert "current:bucket" in remaining
