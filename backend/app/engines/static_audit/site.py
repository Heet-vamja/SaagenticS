"""Site-level policies and discovery diagnostics, with no bot impersonation."""

import re
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

from app.engines.static_audit.checks import Check

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
    text = body.decode("utf-8-sig", errors="strict")
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
        known = state.get("exists") is not None
        checks.append(
            Check(
                "robots.access",
                "Access",
                "PASS" if state.get("permitted") else ("FAIL" if known else "UNKNOWN"),
                "Crawler access is restricted",
                "The declared crawler could not obtain permission for this origin.",
                "Review the matching robots.txt rules and retrieval errors. Only permit the intended read-only crawler paths; do not override intentional restrictions.",
                "HIGH",
                state.get("url", start),
                state,
                3,
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
    unknown = not maps or all(m.get("error") for m in maps)
    checks.append(
        Check(
            "sitemap.health",
            "Access",
            "PASS" if valid else ("UNKNOWN" if unknown else "FAIL"),
            "No usable sitemap was discovered",
            "The inspected sitemap locations did not yield a valid sitemap or sitemap index.",
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
    checks.append(
        Check(
            "sitemap.freshness",
            "Access",
            "FAIL" if invalid_dates else ("INFO" if dated else "UNKNOWN"),
            "Sitemap modification dates need review"
            if invalid_dates
            else "Sitemap freshness sampled",
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
    checks.append(
        Check(
            "llms.presence",
            "Access",
            "PASS" if exists else ("FAIL" if status in (404, 410) else "UNKNOWN"),
            "llms.txt is missing or unavailable",
            "This optional proposal helps agents discover curated documentation; absence does not mean your website is unusable.",
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
                "PASS" if llms.get("valid") else "FAIL",
                "llms.txt structure needs attention",
                "The file did not pass the supported structural checks. Linked destinations are not fetched.",
                "Start with one # Project name heading. Under ## sections, use - [Descriptive name](https://example.com/docs) entries.",
                "LOW",
                llms.get("url", start),
                llms,
            )
        )
    return checks
