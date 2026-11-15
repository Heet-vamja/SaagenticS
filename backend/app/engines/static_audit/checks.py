"""Bounded checks and a versioned, coverage-aware static-only scoring rubric."""

from collections import defaultdict
from dataclasses import asdict, dataclass, field
from typing import Any

from app.models.domain import Category, Severity

BUCKETS = {"Access": 30, "Readability": 25, "Actionability": 30, "Reliability": 15}
CATEGORY = {
    "Access": Category.DISCOVERABILITY,
    "Readability": Category.UNDERSTANDABILITY,
    "Actionability": Category.INTERACTABILITY,
    "Reliability": Category.RELIABILITY,
}


@dataclass
class Check:
    rule: str
    bucket: str
    status: str  # PASS, FAIL, UNKNOWN, INFO, NOT_APPLICABLE
    title: str
    description: str
    recommendation: str = ""
    severity: str = "MEDIUM"
    url: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)
    weight: int = 1

    def dump(self):
        result = asdict(self)
        if self.status == "PASS":
            result["description"] = (
                "No issue was detected by this deterministic check in the inspected sample. Review the evidence and coverage limits."
            )
        elif self.status == "NOT_APPLICABLE":
            result["description"] = "No applicable elements were present in the inspected sample."
        return result


def normalize_access_check(check: dict) -> dict:
    """Scanner-specific denials do not establish a general website failure.

    Also used when projecting persisted older reports; never converts unknown
    evidence into a pass or changes the crawler's permission enforcement.
    """
    result = dict(check)
    rule = str(check.get("rule", "")).removeprefix("render.")
    evidence = check.get("evidence") or {}
    status = evidence.get("status")
    if rule == "robots.access":
        parsed = status == 200 and evidence.get("reason") == "robots.txt parsed"
        absent = status in (404, 410) or evidence.get("reason") == "robots.txt absent"
        if parsed and isinstance(evidence.get("permitted"), bool):
            permitted = evidence.get("permitted") is True
            result.update(
                status="INFO",
                title="Robots policy permits our crawler"
                if permitted
                else "Robots policy restricts our crawler",
                description="This is the declared robots.txt permission for the AgentLane crawler on the sampled path, not proof of access or restriction for ChatGPT or other providers.",
            )
        elif absent:
            result.update(status="INFO", title="No robots policy was published")
        else:
            result.update(
                status="UNKNOWN",
                title="Our scanner could not inspect robots.txt",
                description="Our robots.txt request was not usable"
                + (f" (HTTP {status})" if status else "")
                + ". Crawling stopped conservatively. Other providers may have different permissions or network access; their access was not verified.",
            )
        result.update(
            weight=0,
            recommendation="Review the recorded response and intended policy with the site owner. If appropriate, allowlist our declared crawler or its deployment IP. Preserve security controls; do not impersonate another bot or bypass restrictions.",
        )
    elif rule in {"http.status", "http.restriction"} and (
        status in (401, 403, 429) or rule == "http.restriction"
    ):
        result.update(
            status="UNKNOWN" if rule == "http.status" else "INFO",
            title=f"Our scanner received HTTP {status}"
            if status
            else "Our scanner encountered an access restriction",
            description="This response restricted our request. It does not establish whether ChatGPT or another provider can access the page. Unavailable content is not assessed as a website failure.",
            weight=0,
        )
    elif rule == "http.rate_limit" and check.get("status") == "FAIL":
        result.update(status="INFO", weight=0)
    return result


def summarize(checks: list[Check]):
    checks = [Check(**normalize_access_check(asdict(check))) for check in checks]
    # Average occurrences per rule first, so one repeated issue cannot dominate
    # merely because more pages were crawled. Unknown checks never count as passes.
    groups = defaultdict(list)
    for check in checks:
        if check.status in ("PASS", "FAIL", "UNKNOWN"):
            groups[(check.bucket, check.rule)].append(check)
    scores = {}
    coverage = {}
    for bucket in BUCKETS:
        numerator = denominator = known = total = 0
        for (group, _), values in groups.items():
            if group != bucket:
                continue
            evaluated = [c for c in values if c.status != "UNKNOWN"]
            total += len(values)
            known += len(evaluated)
            if evaluated:
                weight = values[0].weight
                numerator += weight * sum(c.status == "PASS" for c in evaluated) / len(evaluated)
                denominator += weight
        scores[bucket] = round(100 * numerator / denominator, 1) if denominator else None
        coverage[bucket] = {"evaluated": known, "total": total}
    available = {key: value for key, value in scores.items() if value is not None}
    score = (
        round(
            sum(available[k] * BUCKETS[k] for k in available) / sum(BUCKETS[k] for k in available),
            1,
        )
        if available
        else None
    )
    counts = {
        status: sum(c.status == status for c in checks)
        for status in ("PASS", "FAIL", "UNKNOWN", "INFO", "NOT_APPLICABLE")
    }
    return {
        "version": "static-v3",
        "score_kind": "STATIC_READINESS",
        "score": score,
        "category_scores": scores,
        "weights": BUCKETS,
        "coverage": coverage,
        "counts": counts,
        "provisional": counts["UNKNOWN"] > 0 or len(available) < 4,
        "agent_evaluation": "NOT_INCLUDED",
        "checks": [c.dump() for c in checks],
        "limitations": [
            "Static readiness is not verified agent task success. No model was called.",
            "Unknown or restricted checks are excluded from score and shown as incomplete coverage.",
            "Semantic checks cover common HTML patterns, not full WCAG conformance.",
            "JSON-LD checks validate syntax, recognized schema.org context, local type/property names and common fields; not rich-result eligibility.",
            "Browser rendering uses restricted same-host GET requests; blocked resources can make results inconclusive.",
        ],
    }


def finding_values(check: Check):
    if check.status != "FAIL":
        return None
    return {
        "category": CATEGORY[check.bucket],
        "severity": Severity(check.severity),
        "title": check.title[:300],
        "description": check.description,
        "recommendation": check.recommendation or None,
        "confidence": 0.75 if check.rule.endswith(("access.challenge", "js_dependency")) else 0.95,
        "evidence": {
            "rule": check.rule,
            "bucket": check.bucket,
            "url": check.url,
            **check.evidence,
        },
    }
