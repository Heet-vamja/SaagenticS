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


def summarize(checks: list[Check]):
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
        "version": "static-v1",
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
