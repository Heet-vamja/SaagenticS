"""Offline PDF rendering of escaped report data, with all network requests blocked."""

import asyncio
from html import escape

from playwright.async_api import async_playwright

from app.core.config import get_settings


def render_html(report):
    def text(value):
        return escape(str(value if value is not None else "Not available"))

    summary = report["scan"].get("audit_summary", {})
    categories = "".join(
        f"<tr><td>{text(name)}</td><td>{text(value)}</td></tr>"
        for name, value in summary.get("category_scores", {}).items()
    )
    findings = "".join(
        f"<article><small>{text(f['severity'])} · {text(f['evidence'].get('bucket', f['category']))}</small><h3>{text(f['title'])}</h3><p>{text(f['evidence'].get('url'))}</p><p>{text(f['description'])}</p><pre>{text(f['recommendation'])}</pre><details open><summary>Evidence</summary><pre>{text(__import__('json').dumps(f['evidence'], ensure_ascii=False)[:1800])}</pre></details></article>"
        for f in report["findings"][:100]
    )
    priorities = "".join(f"<li>{text(f['title'])}</li>" for f in report["priority_fixes"])
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>AgentReadiness report</title><style>
    @page{{size:A4;margin:18mm}}body{{font-family:Arial,sans-serif;color:#24372a;font-size:11px;line-height:1.6}}h1{{font-size:30px;line-height:1.1}}h2{{margin-top:28px;font-size:19px}}h3{{font-size:14px}}.score{{font-size:48px}}.notice{{padding:12px;background:#edf1e6;border-left:3px solid #47653a}}table{{width:100%;border-collapse:collapse}}td{{border-bottom:1px solid #dde5d5;padding:7px}}article{{break-inside:avoid;border-top:1px solid #dde5d5;padding:16px 0}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;font:10px/1.6 monospace;padding:10px;background:#f4f6ef}}small{{color:#55684b}}p{{overflow-wrap:anywhere}}</style></head><body><small>AGENTREADINESS · STATIC READINESS REPORT</small><h1>{text(report["project"]["name"])}</h1><p>{text(report["project"]["website_url"])}</p><div class="score">{text(report["scan"].get("overall_score"))}<small> / 100</small></div><p class="notice">Static checks only. Agent task success is not evaluated. {"Partial coverage: some checks were inconclusive." if summary.get("provisional") else ""} This is not a full accessibility certification or a guarantee that an agent can complete tasks.</p><table>{categories}</table><h2>Top priority fixes</h2><ol>{priorities}</ol><h2>Findings and evidence</h2>{findings or "<p>No findings recorded. Check coverage before interpreting this result.</p>"}<p>Export includes up to 100 findings. Use JSON or CSV for all findings. Scores use the versioned static-v1 rubric.</p></body></html>"""


async def pdf_export(report):
    async with asyncio.timeout(20):
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(
                headless=True, executable_path=get_settings().agent_browser_executable
            )
            try:
                context = await browser.new_context(
                    java_script_enabled=False, service_workers="block", offline=True
                )
                await context.route("**/*", lambda route: route.abort())
                page = await context.new_page()
                await page.set_content(render_html(report), wait_until="domcontentloaded")
                return await page.pdf(
                    format="A4",
                    print_background=True,
                    display_header_footer=True,
                    header_template="<span></span>",
                    footer_template='<div style="font-size:8px;width:100%;text-align:center">AgentReadiness · <span class="pageNumber"></span> / <span class="totalPages"></span></div>',
                )
            finally:
                await browser.close()
