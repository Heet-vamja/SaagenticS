"""Reference existing measurements to AgentReady v2.0.x without claiming conformance."""

import json
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

from app.engines.static_audit.checks import normalize_access_check
from app.schemas.standards import RequirementCoverage, SignalCounts, StandardsCoverage

REFERENCE = json.loads(Path(__file__).with_name("agentready-v2.json").read_text())
MAX_CHECKS = 10000
STATUSES = {"PASS", "FAIL", "UNKNOWN", "INFO", "NOT_APPLICABLE"}


def _homepage(check, website_url):
    try:
        url = urlsplit(str(check.get("url") or ""))
        target = urlsplit(website_url)
        return bool(
            url.scheme in {"http", "https"}
            and not url.username
            and not url.password
            and url.hostname
            and target.hostname
            and url.hostname.removeprefix("www.") == target.hostname.removeprefix("www.")
            and url.path in ("", "/")
            and not url.query
        )
    except ValueError:
        return False


def reference_coverage(checks, website_url):
    checks = checks if isinstance(checks, list) else []
    signals = [
        normalize_access_check(check)
        for check in checks[:MAX_CHECKS]
        if isinstance(check, dict)
        and isinstance(check.get("status"), str)
        and check["status"] in STATUSES
    ]
    requirements = []
    for item in REFERENCE["requirements"]:
        counts = Counter(
            check["status"]
            for check in signals
            if str(check.get("rule", "")).removeprefix("render.") in item["rules"]
            and (item["scope"] != "homepage" or _homepage(check, website_url))
        )
        if counts["PASS"] + counts["FAIL"] + counts["INFO"]:
            assessment = "PARTIAL_EVIDENCE"
        elif counts["UNKNOWN"]:
            assessment = "INCONCLUSIVE"
        else:
            assessment = "NOT_TESTED"
        requirements.append(
            RequirementCoverage(
                **{key: item[key] for key in ("id", "stage", "level", "title", "limitations")},
                implementation="PARTIAL" if item["rules"] else "NOT_IMPLEMENTED",
                assessment=assessment,
                observations=SignalCounts(
                    passed=counts["PASS"],
                    issues=counts["FAIL"],
                    inconclusive=counts["UNKNOWN"],
                    informational=counts["INFO"],
                    not_applicable=counts["NOT_APPLICABLE"],
                ),
            )
        )
    return StandardsCoverage(
        **{
            key: REFERENCE[key]
            for key in ("mapping_version", "spec_version", "reviewed_on", "source_url")
        },
        checks_truncated=len(checks) > MAX_CHECKS,
        requirements=requirements,
    )
