"""Site-level policies and discovery diagnostics, with no bot impersonation."""

import re
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

from app.engines.static_audit.checks import Check, normalize_access_check

AI_AGENTS = (
    "GPTBot",
    "OAI-SearchBot",
    "ChatGPT-User",
    "ClaudeBot",
    "Claude-SearchBot",
    "Claude-User",
    "PerplexityBot",
    "Perplexity-User",
)


def llms_measurements(body: bytes):
    try:
        text = body.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError:
        return {
            "valid": False,
            "errors": ["File is not valid UTF-8"],
            "links": 0,
            "title_present": False,
            "format": "llms.txt structural subset (H1 and H2 file lists)",
            "linked_urls_fetched": False,
        }
    errors = []
    if "<html" in text.lower() or "\x00" in text:
        errors.append("Expected Markdown, received HTML or invalid text")
    headings = re.findall(r"(?m)^#\s+\S.*$", text)
    if len(headings) != 1:
        errors.append("Expected exactly one nonempty H1 project/site name")
    first = next((line.strip() for line in text.splitlines() if line.strip()), "")
    if not first.startswith("# "):
        errors.append("The first nonempty line must be the H1 title")
    in_section = False
    links = 0
    for line in text.splitlines()[:5000]:
        if re.match(r"^##\s+", line):
            in_section = True
        elif re.match(r"^#{3,}\s", line):
            errors.append("File-list sections should use H2 headings")
        elif in_section and re.match(r"^\s*[-*+]\s+", line):
            match = re.match(r"^\s*[-*+]\s+\[([^]]+)\]\(([^)]+)\)", line)
            if not match:
                errors.append("A file-list entry is missing its Markdown link")
            else:
                target = match[2].strip()
                if urlsplit(target).scheme not in ("", "http", "https"):
                    errors.append("File-list link uses an unsupported scheme")
                links += 1
    return {
        "valid": not errors,
        "errors": list(dict.fromkeys(errors))[:10],
        "links": links,
        "title_present": len(headings) == 1,
        "format": "llms.txt structural subset (H1 and H2 file lists)",
        "linked_urls_fetched": False,
    }


def site_checks(start: str, metadata: dict):
    checks = []
    robots = metadata.get("robots", {})
    if not robots:
        checks.append(
            Check(
                "robots.access",
                "Access",
                "UNKNOWN",
                "Robots policy unavailable",
                "Robots permissions were not inspected.",
                url=start,
            )
        )
    for origin, state in robots.items():
        status = state.get("status")
        reason = state.get("reason")
        absent = status in (404, 410) or reason == "robots.txt absent"
        checks.append(
            Check(
                **normalize_access_check(
                    {
                        "rule": "robots.access",
                        "bucket": "Access",
                        "status": "INFO" if absent else "UNKNOWN",
                        "title": "No robots policy was published"
                        if absent
                        else "Robots policy was not available for inspection",
                        "description": "The file was absent, so no declared policy was available. This does not prove access by another agent."
                        if absent
                        else "Our crawler could not inspect the policy reliably.",
                        "recommendation": "",
                        "severity": "LOW",
                        "url": state.get("url", start),
                        "evidence": state,
                        "weight": 0,
                    }
                )
            )
        )
        for agent, policy in state.get("ai_agents", {}).items():
            checks.append(
                Check(
                    "robots.ai_policy",
                    "Access",
                    "INFO",
                    f"{agent}: {'unknown' if not policy.get('known') else ('allowed' if policy['allowed'] else 'restricted')}",
                    "This reports robots.txt policy for the sampled paths, not verified access by that provider. An intentional training-bot restriction is not a readiness failure.",
                    url=origin + "/robots.txt",
                    evidence={"user_agent": agent, **policy},
                    weight=0,
                )
            )
    maps = metadata.get("sitemaps", [])
    valid = [m for m in maps if m.get("parsed")]
    # A fetched but malformed document is a concrete sitemap problem; a
    # network failure before receiving a response remains unknown.
    unknown = not maps or all(
        (m.get("error") and m.get("status") is None)
        or (m.get("status") in (401, 403, 429))
        or (isinstance(m.get("status"), int) and m["status"] >= 500)
        for m in maps
    )
    missing = bool(maps) and all(m.get("status") in (404, 410) for m in maps)
    checks.append(
        Check(
            "sitemap.health",
            "Access",
            "PASS" if valid else ("UNKNOWN" if unknown else "INFO" if missing else "FAIL"),
            "Sitemap is available"
            if valid
            else "No sitemap was found"
            if missing
            else "Sitemap health could not be determined"
            if unknown
            else "Sitemap response could not be parsed",
            "A valid sitemap was parsed from the inspected locations."
            if valid
            else "No sitemap was found at the inspected locations. A sitemap can aid discovery but is optional; linked pages may still be found."
            if missing
            else "The inspected sitemap returned a transient or inaccessible response, so its health is inconclusive."
            if unknown
            else "A sitemap response was received but its XML could not be parsed as a supported sitemap or index.",
            "Publish a same-site XML sitemap returning HTTP 200 and declare its absolute URL with Sitemap: in robots.txt.",
            "MEDIUM",
            start,
            {"locations": maps[:10]},
            2,
        )
    )
    stale, invalid_dates, dated = 0, 0, 0
    for record in valid:
        for date in record.get("lastmod_samples", []):
            try:
                modified = datetime.fromisoformat(date)
                if modified.tzinfo is None:
                    modified = modified.replace(tzinfo=UTC)
                dated += 1
                if modified > datetime.now(UTC) + timedelta(days=1):
                    invalid_dates += 1
                elif modified < datetime.now(UTC) - timedelta(days=365):
                    stale += 1
            except ValueError:
                invalid_dates += 1
    freshness_status = (
        "NOT_APPLICABLE"
        if not valid
        else "FAIL"
        if invalid_dates
        else "INFO"
        if dated
        else "UNKNOWN"
    )
    checks.append(
        Check(
            "sitemap.freshness",
            "Access",
            freshness_status,
            "Sitemap modification dates need review"
            if invalid_dates
            else "Sitemap freshness sampled"
            if dated
            else "Sitemap freshness could not be assessed",
            "Old dates can be legitimate; modification dates are hints and do not prove content freshness. Missing dates are not an invalid sitemap.",
            "Correct malformed or future lastmod values; update lastmod only when page content changes.",
            "LOW",
            start,
            {"dated_samples": dated, "older_than_year": stale, "invalid_or_future": invalid_dates},
            1,
        )
    )
    llms = metadata.get("llms", {})
    status = llms.get("status")
    exists = status == 200
    presence_status = "INFO" if exists or status in (404, 410) else "UNKNOWN"
    checks.append(
        Check(
            "llms.presence",
            "Access",
            presence_status,
            "llms.txt is available"
            if exists
            else "llms.txt is not published"
            if status in (404, 410)
            else "llms.txt could not be inspected",
            "An llms.txt file was found. This proposal is not a standard or proof that agents use it."
            if exists
            else "This optional proposal was not found. Its absence does not establish that agents cannot discover or use the website."
            if status in (404, 410)
            else "The request did not establish whether llms.txt exists; this is inconclusive and was not treated as a site failure.",
            "Publish /llms.txt with a # Site name heading and curated Markdown links under ## section headings. Keep content concise and accurate.",
            "LOW",
            llms.get("url", start),
            llms,
            1,
        )
    )
    if exists:
        checks.append(
            Check(
                "llms.format",
                "Readability",
                "INFO",
                "llms.txt passed supported formatting checks"
                if llms.get("valid")
                else "llms.txt format needs review",
                "The optional file "
                + ("passed" if llms.get("valid") else "did not pass")
                + " the supported structural checks. Linked destinations are not fetched; this format proposal is not proof of agent compatibility.",
                "Start with one # Project name heading. Under ## sections, use - [Descriptive name](https://example.com/docs) entries.",
                "LOW",
                llms.get("url", start),
                llms,
            )
        )
    return checks
