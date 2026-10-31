"""Deterministic rendering through the same fail-closed browser gateway; no LLM."""

import asyncio
import hashlib
from urllib.parse import urlsplit
from uuid import uuid4

from app.engines.agent.browser import BrowserSession
from app.engines.agent.privacy import public_url
from app.engines.static_audit.checks import Check
from app.engines.static_audit.html import html_checks, inspect_html


async def render_pages(pages, settings, progress=None, transport=None):
    results = []
    selected = [
        p
        for p in pages
        if p.status_code and 200 <= p.status_code < 400 and p.page_metadata.get("audit")
    ][: settings.audit_render_pages]
    selected_ids = {p.id for p in selected}
    for page in pages:
        if page.id not in selected_ids and page.page_metadata.get("audit"):
            results.append(
                Check(
                    "render.js_dependency",
                    "Readability",
                    "UNKNOWN",
                    "Rendered comparison not sampled",
                    "This page was outside the bounded browser sample.",
                    url=public_url(page.url),
                    evidence={"page_key": hashlib.sha256(page.url.encode()).hexdigest()[:20]}
                    if urlsplit(page.url).query
                    else {},
                )
            )
    for index, page in enumerate(selected):
        first_result = len(results)
        browser = BrowserSession(page.url, [], settings, "static-" + str(uuid4()), transport)
        try:
            async with asyncio.timeout(settings.audit_render_timeout):
                await browser.start()
                failures = {"failed_requests": 0, "policy_violations": 0, "script_errors": 0}

                def failed_request(_, state=failures):
                    state["failed_requests"] += 1

                def script_error(_, state=failures):
                    state["script_errors"] += 1

                def console(message, state=failures):
                    if message.type == "error" and (
                        "Content Security Policy" in message.text or "Refused to" in message.text
                    ):
                        state["policy_violations"] += 1

                browser.page.on("requestfailed", failed_request)
                browser.page.on("pageerror", script_error)
                browser.page.on("console", console)
                await browser.navigate(page.url)
                await browser.page.wait_for_timeout(700)
                html = await browser.page.evaluate(
                    "document.documentElement.outerHTML.slice(0, 2097153)"
                )
                if len(html.encode("utf-8")) > settings.crawl_html_bytes:
                    raise ValueError("Rendered DOM exceeds audit budget")
                measurements = inspect_html(html.encode("utf-8"), page.url)
                visible_text = await browser.page.locator("body").inner_text(timeout=1000)
                measurements["text_length"] = min(len(visible_text), 100_000)
                raw = page.page_metadata["audit"]
                evidence = {
                    "raw_text_characters": raw["text_length"],
                    "rendered_text_characters": measurements["text_length"],
                    "blocked_requests": browser.blocked_requests,
                    "total_requests": browser.requests,
                    "same_host_only": True,
                    **failures,
                }
                restricted = browser.blocked_requests or any(failures.values())
                if restricted:
                    status = "UNKNOWN"
                else:
                    dependent = (
                        measurements["text_length"] - raw["text_length"] > 200
                        and measurements["text_length"] > max(1, raw["text_length"]) * 1.5
                    )
                    status = "FAIL" if dependent else "PASS"
                results.append(
                    Check(
                        "render.js_dependency",
                        "Readability",
                        status,
                        "Important content may depend on JavaScript",
                        "The browser-visible text grew substantially after JavaScript. A restricted or blocked render is inconclusive, never a pass.",
                        "Server-render or statically render essential product information and navigation. Keep real links in the initial HTML.",
                        "MEDIUM",
                        public_url(page.url),
                        evidence,
                        2,
                    )
                )
                # A rendered DOM reveals controls absent in initial HTML. Keep a separate
                # rule ID and source so comparisons never mix raw and rendered evidence.
                for check in html_checks(public_url(page.url), measurements):
                    if check.rule.startswith("semantic.") or check.rule == "access.challenge":
                        check.rule = "render." + check.rule
                        check.evidence["source"] = "restricted rendered DOM"
                        if restricted and check.status == "PASS":
                            check.status = "UNKNOWN"
                        results.append(check)
        except (Exception, asyncio.CancelledError) as exc:
            if isinstance(exc, asyncio.CancelledError):
                raise
            results.append(
                Check(
                    "render.js_dependency",
                    "Readability",
                    "UNKNOWN",
                    "Rendered inspection unavailable",
                    "Browser execution timed out, was restricted, or could not start.",
                    url=public_url(page.url),
                    evidence={"reason": type(exc).__name__},
                )
            )
        finally:
            # Browser resources are always closed, including partially-started contexts.
            await browser.close()
            if urlsplit(page.url).query:
                key = hashlib.sha256(page.url.encode()).hexdigest()[:20]
                for check in results[first_result:]:
                    check.evidence["page_key"] = key
            if progress:
                progress(index + 1, len(selected))
    return results
