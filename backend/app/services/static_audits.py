"""Persist deterministic findings and static-only scores; no inference is involved."""

import hashlib
from urllib.parse import urlsplit

from sqlalchemy import delete, select

from app.engines.agent.privacy import public_url
from app.engines.static_audit.checks import Check, finding_values, summarize
from app.engines.static_audit.html import html_checks
from app.engines.static_audit.render import render_pages
from app.engines.static_audit.site import site_checks
from app.models.domain import Finding, Page, Scan, ScanStatus


def page_checks(page):
    url = public_url(page.url)
    known = page.status_code is not None
    checks = [
        Check(
            "http.status",
            "Reliability",
            "PASS" if known and page.status_code < 400 else "FAIL",
            "Page request failed",
            "The inspected URL returned an HTTP error or could not be fetched.",
            "Repair broken destinations and origin errors. For 429, reduce request rate and provide a Retry-After header. Preserve intentional access restrictions.",
            "HIGH",
            url,
            {"status": page.status_code, "error": page.crawl_error},
            3,
        )
    ]
    headers = page.page_metadata.get("http", {}).get("headers", {})
    if page.status_code == 429:
        checks.append(
            Check(
                "http.rate_limit",
                "Reliability",
                "PASS" if "retry-after" in headers else "FAIL",
                "Rate-limited response has no Retry-After",
                "A client cannot determine a recommended retry time from this response.",
                "Return Retry-After: <seconds> or an HTTP date with 429 responses.",
                "MEDIUM",
                url,
                {"headers": headers},
            )
        )
    if page.status_code and page.status_code < 400:
        evidence = page.page_metadata.get("http", {})
        checks.append(
            Check(
                "http.redirects",
                "Reliability",
                "FAIL" if len(evidence.get("redirects", [])) >= 3 else "PASS",
                "Long redirect chain",
                "Three or more redirects add latency and more points of failure.",
                "Link directly to the canonical final HTTPS URL and consolidate redirect rules.",
                "LOW",
                url,
                evidence,
            )
        )
    if page.status_code in (401, 403, 429) or headers.get("cf-mitigated") == "challenge":
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
                {"status": page.status_code, "headers": headers},
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
    if page.page_metadata.get("audit"):
        checks.extend(html_checks(url, page.page_metadata["audit"]))
    if urlsplit(page.url).query:
        key = hashlib.sha256(page.url.encode()).hexdigest()[:20]
        for check in checks:
            check.evidence["page_key"] = key
    return checks


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
                Finding.scan_id == scan_id, Finding.evidence["engine"].as_string() == "static-v1"
            )
        )
        for check in checks:
            values = finding_values(check)
            if values:
                values["evidence"]["engine"] = "static-v1"
                session.add(
                    Finding(
                        scan_id=scan_id,
                        page_id=private_keys.get(
                            check.evidence.get("page_key"), pages.get(check.url)
                        ),
                        **values,
                    )
                )
        summary["limits"] = scan.audit_summary.get("limits", {})
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
    checks = site_checks(url, metadata)
    for page in pages:
        checks.extend(page_checks(page))
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
