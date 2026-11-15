"""Persist deterministic findings and static-only scores; no inference is involved."""

import hashlib
from dataclasses import asdict
from urllib.parse import urlsplit

from sqlalchemy import delete, select

from app.engines.agent.privacy import public_url
from app.engines.static_audit.checks import Check, finding_values, normalize_access_check, summarize
from app.engines.static_audit.html import html_checks
from app.engines.static_audit.render import render_pages
from app.engines.static_audit.resources import diagnostic_checks, pricing_presence_check
from app.engines.static_audit.site import site_checks
from app.models.domain import Finding, Page, Scan, ScanStatus


def page_checks(page):
    url = public_url(page.url)
    status = page.status_code
    if status is None:
        http_status = "UNKNOWN"
        http_title = "Page request could not be confirmed"
        http_description = "The scanner did not receive a usable HTTP status for this URL. This may be a timeout, network, or policy issue; it is inconclusive and is not counted as a website failure."
        http_evidence = {}
    elif status >= 400:
        http_status = "FAIL"
        http_title = (
            "Discovered URL returned not found"
            if status in (404, 410)
            else "Discovered URL returned an HTTP error"
        )
        http_description = f"The crawler received HTTP {status} from this discovered URL. Review whether the URL is intentionally unavailable or whether an internal link or sitemap entry should be updated."
        http_evidence = {"status": status}
    else:
        http_status = "PASS"
        http_title = "Page returned a successful HTTP response"
        http_description = "The inspected URL returned an HTTP response below 400. This does not verify that its content is usable by an AI agent."
        http_evidence = {"status": status}
    if status is None:
        http_recommendation = "Retry the scan later. If the same URL repeatedly has no HTTP response, check whether the site is reachable from a public network."
    elif status == 429:
        http_recommendation = "Review the request rate and return Retry-After with 429 responses. Preserve any intentional rate limits."
    elif status in (404, 410):
        http_recommendation = "Review links and sitemap entries that point here. Keep the response if this URL is intentionally retired."
    elif status is not None and status >= 400:
        http_recommendation = "Review whether this URL is intentionally restricted or unavailable, and correct internal links if it should be public."
    else:
        http_recommendation = "No HTTP error was observed for this URL. Review the other checks and their coverage for content or interaction concerns."
    checks = [
        Check(
            "http.status",
            "Reliability",
            http_status,
            http_title,
            http_description,
            http_recommendation,
            "HIGH",
            url,
            http_evidence,
            3,
        )
    ]
    headers = page.page_metadata.get("http", {}).get("headers", {})
    if status == 429:
        checks.append(
            Check(
                "http.rate_limit",
                "Reliability",
                "PASS" if headers.get("retry-after") else "FAIL",
                "Retry-After header was provided"
                if headers.get("retry-after")
                else "Rate-limited response has no Retry-After",
                "A client cannot determine a recommended retry time from this response.",
                "Return Retry-After: <seconds> or an HTTP date with 429 responses.",
                "MEDIUM",
                url,
                {"headers": headers},
            )
        )
    if status is not None and status < 400:
        evidence = page.page_metadata.get("http", {})
        checks.append(
            Check(
                "http.redirects",
                "Reliability",
                "FAIL" if len(evidence.get("redirects", [])) >= 3 else "PASS",
                "Long redirect chain"
                if len(evidence.get("redirects", [])) >= 3
                else "No long redirect chain was observed",
                "Three or more redirects add latency and more points of failure.",
                "Link directly to the canonical final HTTPS URL and consolidate redirect rules.",
                "LOW",
                url,
                evidence,
            )
        )
    if status in (401, 403, 429) or headers.get("cf-mitigated") == "challenge":
        checks.append(
            Check(
                "http.restriction",
                "Access",
                "FAIL",
                "Access restriction encountered",
                "Authentication, bot mitigation or rate limiting restricted this request. The response does not prove which other providers are blocked.",
                "Review the observed status and mitigation headers. Configure intended read-only access while preserving sensitive route protections.",
                "HIGH",
                url,
                {"status": status, "headers": headers},
                3,
            )
        )
    measurements = page.page_metadata.get("audit", {})
    if page.status_code == 200 and measurements.get("soft_error"):
        checks.append(
            Check(
                "http.soft_error",
                "Reliability",
                "FAIL",
                "Possible error page returns HTTP 200",
                "The document title resembles an error page despite a successful HTTP status; review the evidence.",
                "Return the appropriate 4xx/5xx status for genuine errors, or clarify the title if the page is valid content.",
                "MEDIUM",
                url,
                {"title": page.title, "status": 200},
            )
        )
    if page.status_code == 200 and page.page_metadata.get("audit"):
        measured = page.page_metadata["audit"]
        page_html_checks = html_checks(url, measured)
        for check in page_html_checks:
            if check.rule == "page.title":
                check.evidence["observed_title"] = page.title or ""
                check.evidence["title_present"] = bool(page.title and page.title.strip())
        checks.extend(page_html_checks)
        if measured.get("canonical_present"):
            checks.append(
                Check(
                    "page.canonical",
                    "Access",
                    "PASS" if page.canonical_url else "FAIL",
                    "Canonical URL is within the inspected site scope"
                    if page.canonical_url
                    else "Canonical URL needs review",
                    "A canonical link was present, but it did not resolve to an allowed HTTP(S) page in this scan’s website scope.",
                    "Point the canonical link to the intended public URL for this page, using the same authorized website host.",
                    "MEDIUM",
                    url,
                    {"canonical_url": page.canonical_url}
                    if page.canonical_url
                    else {"canonical_present": True},
                    2,
                )
            )
        checks.append(
            Check(
                "page.meta_description",
                "Readability",
                "PASS" if (page.meta_description or "").strip() else "FAIL",
                "Meta description is present"
                if (page.meta_description or "").strip()
                else "Meta description is missing",
                "A concise page description gives people and automated systems another clear summary of the page.",
                'Add an accurate meta name="description" value in the page head. Keep it specific to the visible page content.',
                "LOW",
                url,
                {"description_present": bool((page.meta_description or "").strip())},
                1,
            )
        )
    if urlsplit(page.url).query:
        key = hashlib.sha256(page.url.encode()).hexdigest()[:20]
        for check in checks:
            check.evidence["page_key"] = key
    return [Check(**normalize_access_check(asdict(check))) for check in checks]


def persist_audit(scan_id, checks, session_factory, phase="REPORT_READY"):
    summary = summarize(checks)
    summary["phase"] = phase
    with session_factory() as session:
        scan = session.get(Scan, scan_id)
        if not scan or scan.status != ScanStatus.RUNNING:
            return
        rows = list(session.scalars(select(Page).where(Page.scan_id == scan_id)))
        pages = {public_url(p.url): p.id for p in rows}
        private_keys = {hashlib.sha256(p.url.encode()).hexdigest()[:20]: p.id for p in rows}
        session.execute(
            delete(Finding).where(
                Finding.scan_id == scan_id,
                Finding.evidence["engine"].as_string().in_(["static-v1", "static-v2"]),
            )
        )
        for check in checks:
            values = finding_values(check)
            if values:
                values["evidence"]["engine"] = "static-v2"
                session.add(
                    Finding(
                        scan_id=scan_id,
                        page_id=private_keys.get(
                            check.evidence.get("page_key"), pages.get(check.url)
                        ),
                        **values,
                    )
                )
        previous = scan.audit_summary
        summary["static_score"] = summary["score"]
        summary["limits"] = previous.get("limits", {})
        summary["agent_policy"] = previous.get("agent_policy")
        if previous.get("scan_mode"):
            summary["scan_mode"] = previous["scan_mode"]
        for key in ("pages_discovered", "pages_crawled", "pages_failed"):
            if key in previous:
                summary[key] = previous[key]
        scan.audit_summary = summary
        scan.overall_score = summary["score"]
        session.commit()


async def run_static_audits(scan_id, settings, session_factory, transport=None):
    with session_factory() as session:
        scan = session.get(Scan, scan_id)
        url = scan.project.website_url
        pages = list(
            session.scalars(
                select(Page).where(Page.scan_id == scan_id).order_by(Page.crawl_depth, Page.url)
            )
        )
        metadata = scan.crawl_metadata
        # Keep only loaded page attributes after the independent session closes.
        for page in pages:
            session.expunge(page)
    checks = site_checks(url, metadata) + diagnostic_checks(url, metadata)
    for page in pages:
        checks.extend(page_checks(page))
    checks.extend(
        pricing_presence_check(
            url,
            [page.page_metadata.get("audit") for page in pages if page.status_code == 200],
        )
    )
    persist_audit(scan_id, checks, session_factory, "BROWSER_CHECKS")

    def progress(done, total):
        with session_factory() as session:
            scan = session.get(Scan, scan_id)
            if scan and scan.status == ScanStatus.RUNNING:
                scan.audit_summary = {
                    **scan.audit_summary,
                    "phase": "BROWSER_CHECKS",
                    "browser_pages_done": done,
                    "browser_pages_total": total,
                }
                session.commit()

    if settings.audit_browser_enabled:
        checks.extend(await render_pages(pages, settings, progress, transport))
    else:
        checks.append(
            Check(
                "render.js_dependency",
                "Readability",
                "UNKNOWN",
                "Browser checks disabled",
                "Rendered comparisons were disabled by the operator.",
                url=url,
            )
        )
    persist_audit(scan_id, checks, session_factory)
