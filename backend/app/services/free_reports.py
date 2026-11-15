"""Customer-safe report projection and deterministic preliminary score."""

from collections import Counter, defaultdict

from app.engines.agent.privacy import public_url, redact, sanitize
from app.engines.standards.coverage import reference_coverage
from app.engines.static_audit.checks import normalize_access_check
from app.models.domain import Finding, Project, Scan
from app.schemas.reports import FreeCategoryScore, FreeCoverage, FreeInsight, FreeReportRead
from app.services.reports import rank

FREE_INSIGHT_LIMIT = 10

CATEGORIES = (
    (
        "Discoverability",
        30,
        frozenset(
            {
                "sitemap.health",
                "sitemap.freshness",
                "page.canonical",
            }
        ),
    ),
    (
        "Content understanding",
        25,
        frozenset(
            {
                "page.title",
                "page.h1",
                "page.heading_hierarchy",
                "page.meta_description",
                "js_dependency",
            }
        ),
    ),
    ("Structured data", 20, frozenset({"schema.syntax"})),
    # Agent task execution is intentionally excluded from the free scan. Static
    # signals still appear as findings, but they do not masquerade as an agent run.
    ("Agent usability", 25, frozenset()),
)

PROGRESS = {
    "QUEUED": "Your scan is queued.",
    "CRAWLING": "Finding important pages on your website.",
    "BROWSER_CHECKS": "Checking page content and technical signals.",
    "REPORT_READY": "Preparing your results.",
    "AGENT_TASKS": "Finalizing deterministic checks.",
    "COMPLETED": "Your readiness report is ready.",
    "FAILED": "The scan could not be completed.",
}


def _rule(check):
    return str(check.get("rule", "")).removeprefix("render.")


def _category_score(checks, rules):
    groups = defaultdict(list)
    total = 0
    evaluated = 0
    for check in checks:
        rule = _rule(check)
        if rule not in rules:
            continue
        status = check.get("status")
        if status not in ("PASS", "FAIL", "UNKNOWN"):
            continue
        total += 1
        if status in ("PASS", "FAIL"):
            evaluated += 1
            groups[rule].append((status == "PASS", max(0.0, float(check.get("weight", 1)))))
    numerator = denominator = 0.0
    for values in groups.values():
        weight = sum(value[1] for value in values) / len(values)
        passed = sum(value[0] for value in values) / len(values)
        numerator += passed * weight
        denominator += weight
    return (round(100 * numerator / denominator, 1) if denominator else None, evaluated, total)


def _evidence_summary(evidence: dict, check_status: str | None = None):
    if "probe_url" in evidence or ("kind" in evidence and "linked_from" in evidence):
        origin = public_url(str(evidence.get("linked_from") or evidence.get("probe_url") or ""))
        return redact(
            f"{evidence.get('kind', 'Missing-path probe')}: {origin}. HTTP {evidence.get('status', 'unconfirmed')}. {evidence.get('detail', '')}",
            600,
        )
    if str(evidence.get("scope") or "").startswith("HTML block-code"):
        blocks = ", ".join(
            str(item.get("block")) for item in evidence.get("missing_language", [])[:10]
        )
        return f"{evidence.get('count', 0)} nonempty block-code examples sampled. Missing language annotations in blocks: {blocks or 'none observed'}. Source code was not retained."

    if isinstance(evidence.get("permitted"), bool):
        parsed = evidence.get("status") == 200 and evidence.get("reason") == "robots.txt parsed"
        if not parsed:
            status = evidence.get("status")
            return (
                f"Our robots.txt request returned HTTP {status}; provider permissions could not be determined."
                if status not in (None, 404, 410)
                else "No usable robots policy was inspected; provider access was not verified."
            )
        http_status = evidence.get("status")
        if http_status is not None:
            return f"Robots request returned HTTP {http_status}; sampled path permission was {'allowed' if evidence['permitted'] else 'denied'}."
        return (
            "The sampled path was "
            + ("permitted" if evidence["permitted"] else "disallowed")
            + " by the retrieved robots policy."
        )
    title = evidence.get("observed_title")
    if isinstance(title, str) and title.strip():
        return redact("Observed page title: " + title.strip(), 240)
    title = evidence.get("title")
    if isinstance(title, str) and title.strip():
        return redact("Observed document title: " + title.strip(), 240)
    status = evidence.get("status")
    if isinstance(status, int):
        return f"Observed HTTP status: {status}."
    if isinstance(evidence.get("description_present"), bool):
        return (
            "Meta description was present."
            if evidence["description_present"]
            else "Meta description was absent."
        )
    if isinstance(evidence.get("h1_present"), bool):
        return (
            "An H1 heading was present." if evidence["h1_present"] else "No H1 heading was found."
        )
    if isinstance(evidence.get("title_present"), bool):
        return (
            "A page title was present." if evidence["title_present"] else "No page title was found."
        )
    if "canonical_url" in evidence:
        canonical = evidence.get("canonical_url")
        return (
            "Observed canonical URL: " + public_url(canonical)
            if isinstance(canonical, str)
            else "A canonical link was present but no in-scope HTTP(S) URL was accepted."
        )
    if isinstance(evidence.get("blocks"), int):
        return f"Observed {evidence['blocks']} JSON-LD block(s)."
    if isinstance(evidence.get("redirects"), list):
        return f"Observed {len(evidence['redirects'])} redirect(s) before the final response."
    if isinstance(evidence.get("robots_meta"), str):
        return redact("Observed robots meta directive: " + evidence["robots_meta"], 240)
    if isinstance(evidence.get("heading_jumps"), list):
        jumps = evidence["heading_jumps"]
        return f"Observed {len(jumps)} heading-level jump(s)."
    if isinstance(evidence.get("raw_text_characters"), int):
        return (
            f"Observed {evidence['raw_text_characters']} text characters in the initial HTML; "
            f"{evidence.get('rendered_text_characters', 0)} after the restricted render."
        )
    if isinstance(evidence.get("invalid_or_future"), int):
        return (
            f"Observed {evidence['invalid_or_future']} invalid or future sitemap date(s) "
            f"among {evidence.get('dated_samples', 0)} dated sample(s)."
        )
    headers = evidence.get("headers")
    if isinstance(headers, dict) and headers:
        safe_headers = [
            f"{str(key)[:40]}: {redact(str(value), 80)}" for key, value in list(headers.items())[:3]
        ]
        return "Observed response headers: " + "; ".join(safe_headers)
    signals = evidence.get("signals")
    if isinstance(signals, list) and signals:
        return ("Observed signals: " + ", ".join(str(item) for item in signals[:3]))[:240]
    examples = evidence.get("examples")
    if isinstance(examples, list) and examples:
        sample = examples[0]
        if isinstance(sample, dict):
            observed = sample.get("example") or sample.get("tag")
            if isinstance(observed, str) and observed:
                return ("Example inspected element: " + observed)[:240]
    missing = evidence.get("missing")
    if isinstance(missing, list) and missing:
        names = [
            str(item.get("recommended_field"))
            for item in missing[:5]
            if isinstance(item, dict) and item.get("recommended_field")
        ]
        if names:
            return "Missing recommended fields: " + ", ".join(names)
    if evidence.get("rule") == "sitemap.health":
        locations = evidence.get("locations")
        if isinstance(locations, list) and locations:
            parsed_count = sum(
                1 for item in locations if isinstance(item, dict) and item.get("parsed")
            )
            if parsed_count:
                return f"A valid sitemap was parsed from {parsed_count} inspected location(s)."
            location = locations[0]
            if isinstance(location, dict) and isinstance(location.get("status"), int):
                return f"A sitemap request returned HTTP {location['status']}."
            if isinstance(location, dict) and location.get("error"):
                code = location.get("error")
                return "A sitemap response could not be parsed" + (
                    f" ({redact(str(code), 40)})." if isinstance(code, str) else "."
                )
    errors = evidence.get("errors")
    if isinstance(errors, list) and errors:
        messages = [
            item.get("error")
            for item in errors[:2]
            if isinstance(item, dict) and isinstance(item.get("error"), str)
        ]
        if messages:
            return redact("Validation observations: " + "; ".join(messages), 240)
    if check_status == "UNKNOWN":
        return "This check could not be completed reliably and was excluded from the score."
    return None


def score_summary(summary: dict):
    """Score only supported completed checks; infrastructure and unknowns do not fail."""
    checks = [
        normalize_access_check(check)
        for check in summary.get("checks", [])
        if isinstance(check, dict)
    ]
    categories = []
    available_weight = 0
    weighted_score = 0.0
    evaluated = passed = problems = untested = 0
    for name, weight, rules in CATEGORIES:
        if name == "Agent usability":
            categories.append(
                FreeCategoryScore(
                    name=name,
                    score=None,
                    weight=weight,
                    tested=False,
                    evaluated=0,
                    total=0,
                )
            )
            continue
        value, checked, total = _category_score(checks, rules)
        categories.append(
            FreeCategoryScore(
                name=name,
                score=value,
                weight=weight,
                tested=total > 0,
                evaluated=checked,
                total=total,
            )
        )
        evaluated += checked
        untested += max(0, total - checked)
        category_checks = [
            item
            for item in checks
            if _rule(item) in rules and item.get("status") in ("PASS", "FAIL")
        ]
        passed += sum(item.get("status") == "PASS" for item in category_checks)
        problems += sum(item.get("status") == "FAIL" for item in category_checks)
        if value is not None:
            available_weight += weight
            weighted_score += value * weight
    overall = round(weighted_score / available_weight, 1) if available_weight else None
    return (
        overall,
        categories,
        FreeCoverage(
            evaluated=evaluated,
            total=evaluated + untested,
            passed=passed,
            problems=problems,
            untested=untested,
            checks_total=0,
            checks_passed=0,
            checks_failed=0,
            checks_inconclusive=0,
            checks_informational=0,
            checks_not_applicable=0,
        ),
    )


def access_policies(metadata: dict):
    rows = []
    for origin, state in list(metadata.get("robots", {}).items())[:8]:
        known = state.get("status") == 200 and state.get("reason") == "robots.txt parsed"
        source = public_url(str(origin).rstrip("/") + "/robots.txt")
        rows.append(
            {
                "user_agent": redact(
                    str(state.get("user_agent") or "AgentReadinessBot (identity not recorded)"), 100
                ),
                "kind": "SCANNER",
                "policy": ("ALLOWED" if state.get("permitted") else "DISALLOWED")
                if known and isinstance(state.get("permitted"), bool)
                else "UNKNOWN",
                "sampled_url": public_url(str(state.get("url") or origin)),
                "source_url": source,
                "http_status": state.get("status"),
            }
        )
        for agent, policy in list(state.get("ai_agents", {}).items())[:16]:
            rows.append(
                {
                    "user_agent": redact(str(agent), 100),
                    "kind": "AI_BOT",
                    "policy": ("ALLOWED" if policy.get("allowed") else "DISALLOWED")
                    if known and policy.get("known") and isinstance(policy.get("allowed"), bool)
                    else "UNKNOWN",
                    "sampled_url": public_url(str(state.get("url") or origin)),
                    "source_url": source,
                    "http_status": state.get("status"),
                }
            )
    return rows


def free_report(scan: Scan, project: Project, findings: list[Finding]):
    summary = scan.audit_summary or {}
    phase = str(summary.get("phase") or scan.status.value)
    score, categories, coverage = score_summary(summary)
    raw_checks = summary.get("checks", [])
    if not isinstance(raw_checks, list):
        raw_checks = []
    raw_checks = [normalize_access_check(check) for check in raw_checks if isinstance(check, dict)]
    has_page_evidence = any(
        _rule(check) in {"page.title", "page.h1", "page.meta_description", "schema.syntax"}
        and check.get("status") in {"PASS", "FAIL"}
        for check in raw_checks
    )
    if not has_page_evidence:
        score = None
        categories = [category.model_copy(update={"score": None}) for category in categories]

    allowed_statuses = {"PASS", "FAIL", "UNKNOWN", "INFO", "NOT_APPLICABLE"}
    status_counts = Counter(
        check.get("status")
        for check in raw_checks
        if isinstance(check, dict) and check.get("status") in allowed_statuses
    )
    coverage = coverage.model_copy(
        update={
            "checks_total": sum(status_counts.values()),
            "checks_passed": status_counts["PASS"],
            "checks_failed": status_counts["FAIL"],
            "checks_inconclusive": status_counts["UNKNOWN"],
            "checks_informational": status_counts["INFO"],
            "checks_not_applicable": status_counts["NOT_APPLICABLE"],
        }
    )
    category_names = {
        "Access": "Discoverability",
        "Readability": "Content understanding",
        "Actionability": "Navigation and interaction",
        "Reliability": "Reliability",
    }
    check_rows = []
    for check in raw_checks[:300]:
        if not isinstance(check, dict) or check.get("status") not in allowed_statuses:
            continue
        raw_url = check.get("url")
        evidence = check.get("evidence")
        evidence = evidence if isinstance(evidence, dict) else {}
        check_rows.append(
            {
                "category": category_names.get(check.get("bucket"), "Website readiness"),
                "status": check["status"],
                "title": redact(str(check.get("title") or "Check"), 200),
                "description": redact(str(check.get("description") or ""), 700),
                "url": public_url(raw_url) if isinstance(raw_url, str) else None,
                "evidence_summary": _evidence_summary(evidence, check["status"]),
                "recommendation": (
                    redact(str(check.get("recommendation") or ""), 500) or None
                    if check["status"] in ("FAIL", "UNKNOWN")
                    else None
                ),
            }
        )
    partial = (
        (scan.status.value == "FAILED" or scan.pages_failed > 0)
        and scan.pages_crawled > scan.pages_failed
        and score is not None
    )
    if scan.status.value == "FAILED" and not partial:
        score = None
        categories = [category.model_copy(update={"score": None}) for category in categories]
        score_status = "UNAVAILABLE"
        explanation = (
            "The scan stopped before it could gather enough reliable evidence to score this site. "
            "The failure is not treated as a readiness failure."
        )
    elif score is None:
        explanation = (
            "There is not enough completed evidence to calculate a score. "
            "Unknown and inaccessible checks are not counted as passes."
        )
        score_status = "UNAVAILABLE"
    else:
        explanation = (
            "Preliminary score from completed PASS/FAIL discoverability, content and "
            "structured-data checks in rubric free-static-v4. Inconclusive and informational "
            "checks are not counted as passes; categories with no scoreable evidence were "
            "excluded and remaining weights normalized. Missing optional llms.txt or JSON-LD "
            "does not lower the score. Real AI agent task testing is not included, so this "
            "static assessment does not prove that an agent can or cannot complete a task. "
            "Linked-resource, missing-path and code-annotation diagnostics are reported "
            "separately without changing these score weights."
        )
        if partial:
            explanation = (
                "Partial inspection: some pages or checks could not be completed. This score reflects only completed checks on inspected pages, not the whole website. "
                + explanation
            )
        score_status = "PRELIMINARY"
    insights = []
    category_names = {
        "DISCOVERABILITY": "Discoverability",
        "UNDERSTANDABILITY": "Content understanding",
        "NAVIGABILITY": "Agent usability",
        "INTERACTABILITY": "Agent usability",
        "RELIABILITY": "Reliability",
    }
    used_rules = set()
    for finding in rank(findings):
        if (
            normalize_access_check(
                {
                    "rule": finding.evidence.get("rule", ""),
                    "status": "FAIL",
                    "evidence": finding.evidence,
                }
            ).get("status")
            != "FAIL"
        ):
            continue
        rule = str(finding.evidence.get("rule", finding.title)).removeprefix("render.")
        if rule in used_rules:
            continue
        used_rules.add(rule)
        raw_url = finding.evidence.get("url")
        safe_url = public_url(raw_url) if isinstance(raw_url, str) else None
        insights.append(
            FreeInsight(
                category=category_names.get(finding.category.value, "Website readiness"),
                severity=finding.severity.value,
                title=finding.title,
                description=finding.description,
                evidence_url=safe_url,
                evidence_summary=_evidence_summary(finding.evidence),
                recommendation=finding.recommendation,
            )
        )
        if len(insights) == FREE_INSIGHT_LIMIT:
            break
    clean_error = sanitize(scan.error_summary) if scan.error_summary else None
    if isinstance(clean_error, dict):
        clean_error = "The scan could not be completed. Please try again later."
    return FreeReportRead(
        standards_coverage=reference_coverage(raw_checks, project.website_url),
        status=scan.status.value,
        website=public_url(project.website_url),
        phase=phase,
        progress_message=PROGRESS.get(phase, "Checking your website."),
        score_version="free-static-v4",
        score=score,
        score_status=score_status,
        score_explanation=explanation,
        category_scores=categories,
        coverage=coverage,
        checks=check_rows,
        checks_truncated=len(raw_checks) > 300,
        access_policies=access_policies(scan.crawl_metadata or {}),
        insights=insights,
        pages_crawled=scan.pages_crawled,
        pages_discovered=scan.pages_discovered,
        pages_failed=scan.pages_failed,
        failure_message=(str(clean_error)[:500] if clean_error else None),
    )
