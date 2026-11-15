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
    components = report.get("score_components", {})
    tasks = "".join(
        "<article><h3>"
        + text(task.get("description") or task.get("task_type"))
        + " · "
        + text(task.get("outcome") or task.get("status"))
        + "</h3><p>"
        + text(task.get("eligible_runs", 0))
        + " eligible of "
        + text(task.get("runs_completed", 0))
        + " completed runs; consistency: "
        + text(task.get("consistency") if task.get("consistency") is not None else "not measured")
        + "</p>"
        + "".join(
            "<p>Run "
            + text(run.get("run_number"))
            + ": "
            + text(run.get("outcome") or run.get("status"))
            + " · verified by "
            + text(run.get("verification_method"))
            + " · "
            + text(run.get("steps", 0))
            + " steps · "
            + text(run.get("duration_seconds"))
            + " seconds"
            + (
                " · failure: " + text(run.get("failure_category"))
                if run.get("failure_category")
                else ""
            )
            + (
                "<pre>"
                + text(__import__("json").dumps(run.get("evidence", {}), ensure_ascii=False)[:1000])
                + "</pre>"
                if run.get("evidence")
                else ""
            )
            + "</p>"
            for run in task.get("runs", [])
        )
        + "</article>"
        for task in report.get("agent_tasks", [])
    )
    score_notice = (
        "Agent-aware score ("
        + text(report.get("score_kind"))
        + "). Static: "
        + text(components.get("static_score"))
        + "; agent: "
        + text(components.get("agent_score"))
        + "; effective agent weight: "
        + text(components.get("effective_weight"))
        + ". "
        + text(
            components.get("fallback_reason")
            or "Verified and judged runs are counted; infrastructure and inconclusive runs are excluded."
        )
        if report.get("agent_tasks") or components.get("agent_score") is not None
        else "Static checks only. Agent task success is not evaluated."
    )
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>AgentLane report</title><style>
    @page{{size:A4;margin:18mm}}body{{font-family:Arial,sans-serif;color:#272933;font-size:11px;line-height:1.6}}h1{{font-size:30px;line-height:1.1}}h2{{margin-top:28px;font-size:19px}}h3{{font-size:14px}}.score{{font-size:48px}}.notice{{padding:12px;background:#f0ede6;border-left:3px solid #c44f31}}table{{width:100%;border-collapse:collapse}}td{{border-bottom:1px solid #dfded9;padding:7px}}article{{break-inside:avoid;border-top:1px solid #dfded9;padding:16px 0}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;font:10px/1.6 monospace;padding:10px;background:#faf9f6}}small{{color:#6d707b}}p{{overflow-wrap:anywhere}}</style></head><body><small>AGENTREADINESS · READINESS REPORT</small><h1>{text(report["project"]["name"])}</h1><p>{text(report["project"]["website_url"])}</p><div class="score">{text(report["scan"].get("overall_score"))}<small> / 100</small></div><p class="notice">{score_notice} {"Partial coverage: some checks were inconclusive." if summary.get("provisional") else ""} This is not a full accessibility certification or a guarantee that an agent can complete tasks.</p><table>{categories}</table><h2>Agent task results</h2>{tasks or "<p>No agent task results are available.</p>"}<h2>Top priority fixes</h2><ol>{priorities}</ol><h2>Findings and evidence</h2>{findings or "<p>No findings recorded. Check coverage before interpreting this result.</p>"}<p>Export includes up to 100 findings. Use JSON or CSV for all findings. Static checks use the versioned {text(summary.get("version") or "static rubric")} rubric.</p></body></html>"""


async def pdf_export(report):
    return await _render_pdf(render_html(report))


def render_free_html(report):
    """Render only the public, free-report fields; never include the full scan report."""
    if hasattr(report, "model_dump"):
        report = report.model_dump(mode="json")

    def text(value, fallback="Not available"):
        return escape(str(value if value not in (None, "") else fallback))

    coverage = report.get("coverage", {})
    score = report.get("score")
    score_text = text(round(score)) if isinstance(score, (int, float)) else "—"
    categories = "".join(
        f"<div class='category'><div><b>{text(item.get('name'))}</b><span>{text(round(item['score'])) + '/100' if item.get('score') is not None else 'Not scored'}</span></div>"
        f"<div class='track'><i style='width:{max(0, min(100, item.get('score') or 0))}%'></i></div></div>"
        for item in report.get("category_scores", [])
    )
    insight_rows = []
    for item in report.get("insights", []):
        evidence_url = (
            f"<p class='evidence'><b>Page:</b> {text(item.get('evidence_url'))}</p>"
            if item.get("evidence_url")
            else ""
        )
        evidence_summary = (
            f"<p class='evidence'><b>Evidence:</b> {text(item.get('evidence_summary'))}</p>"
            if item.get("evidence_summary")
            else ""
        )
        recommendation = (
            f"<p class='recommendation'><b>Suggested next step</b><br>{text(item.get('recommendation'))}</p>"
            if item.get("recommendation")
            else ""
        )
        insight_rows.append(
            f"<article class='insight'><div class='meta'><span>{text(item.get('category'))}</span><span class='severity'>{text(item.get('severity'))}</span></div>"
            f"<h3>{text(item.get('title'))}</h3><p>{text(item.get('description'))}</p>"
            f"{evidence_url}{evidence_summary}{recommendation}</article>"
        )
    insights = "".join(insight_rows)
    check_rows = []
    for item in report.get("checks", []):
        url = f"<small>{text(item.get('url'))}</small>" if item.get("url") else ""
        evidence = (
            f"<small>Evidence: {text(item.get('evidence_summary'))}</small>"
            if item.get("evidence_summary")
            else ""
        )
        status_class = text(item.get("status"), "UNKNOWN").lower()
        check_rows.append(
            f"<tr><td><span class='check-status {status_class}'>{text(item.get('status'))}</span></td>"
            f"<td><b>{text(item.get('title'))}</b><small>{text(item.get('category'))}</small></td>"
            f"<td>{text(item.get('description'))}{url}{evidence}</td></tr>"
        )
    checks = "".join(check_rows)
    policy_rows = "".join(
        f"<tr><td>{text(row.get('user_agent'))}</td><td>{text(row.get('kind'))}</td><td>{text(row.get('policy'))}</td></tr>"
        for row in report.get("access_policies", [])
    )
    policy_section = (
        "<h2>Our scanner and declared AI-bot policies</h2>"
        "<p class='notice'>These are robots.txt declarations for sampled paths, not verified provider access, AI-search visibility, or task success. A restriction encountered by our scanner does not prove that other providers are blocked.</p>"
        "<table><thead><tr><th>Identity</th><th>Scope</th><th>Declared policy</th></tr></thead><tbody>"
        + policy_rows
        + "</tbody></table>"
        if policy_rows
        else ""
    )
    status = (
        "Preliminary score" if report.get("score_status") == "PRELIMINARY" else "Score unavailable"
    )
    truncation_note = (
        "This report shows the first 300 checks. Open the online report for the full available list."
        if report.get("checks_truncated")
        else ""
    )
    failed_note = (
        f"<div class='callout warning'>{text(report.get('failure_message'))}</div>"
        if report.get("failure_message")
        else ""
    )
    return f"""<!doctype html><html><head><meta charset='utf-8'><title>AgentLane report · {text(report.get("website"))}</title><style>
    @page{{size:A4;margin:17mm 16mm 20mm}}*{{box-sizing:border-box}}body{{font-family:Arial,sans-serif;color:#272933;font-size:10.5px;line-height:1.55;margin:0}}.topline{{font-size:9px;letter-spacing:.14em;font-weight:700;color:#c44f31;text-transform:uppercase}}header{{border-bottom:1px solid #dfded9;padding-bottom:18px;margin-bottom:25px}}h1{{font-size:26px;letter-spacing:-.04em;margin:12px 0 5px;line-height:1.12;overflow-wrap:anywhere}}.muted{{color:#6d707b}}.hero{{display:grid;grid-template-columns:135px 1fr;gap:23px;align-items:center;padding:22px;border:1px solid #dfded9;border-radius:16px;background:#fff}}.score{{width:126px;height:126px;border:9px solid #f0ede6;border-top-color:#304fce;border-right-color:#304fce;border-radius:50%;display:flex;align-items:center;justify-content:center;flex-direction:column;color:#304fce}}.score strong{{font-size:38px;line-height:1}}.score small{{font-size:8px;letter-spacing:.12em;margin-top:5px;color:#6d707b}}h2{{font-size:17px;letter-spacing:-.02em;margin:26px 0 12px}}h3{{font-size:13px;margin:8px 0}}p{{margin:5px 0;overflow-wrap:anywhere}}.stats{{display:grid;grid-template-columns:repeat(4,1fr);border:1px solid #dfded9;border-radius:12px;margin:13px 0 24px;overflow:hidden}}.stat{{padding:11px 13px;border-right:1px solid #dfded9}}.stat:last-child{{border:0}}.stat b{{display:block;font-size:17px}}.stat span{{font-size:9px;color:#6d707b}}.category{{margin:11px 0}}.category>div:first-child{{display:flex;justify-content:space-between;font-size:10px;margin-bottom:5px}}.category span{{color:#6d707b}}.track{{height:5px;border-radius:10px;background:#f0ede6;overflow:hidden}}.track i{{height:100%;display:block;background:#272933;border-radius:10px}}.callout{{padding:12px 14px;border:1px solid #dfded9;border-left:3px solid #c44f31;border-radius:8px;background:#faf9f6;color:#6d707b;margin-top:10px}}.warning{{border-left-color:#d39a47;background:#fffaf1}}.insight{{border:1px solid #dfded9;border-radius:11px;padding:14px 16px;margin:10px 0;break-inside:avoid}}.meta{{display:flex;justify-content:space-between;color:#6d707b;font-size:8px;font-weight:bold;text-transform:uppercase;letter-spacing:.08em}}.severity{{color:#a95649}}.evidence{{color:#6d707b;font-size:9px}}.recommendation{{margin-top:10px;padding:9px 11px;border-radius:7px;background:#f0ede6;color:#272933}}table{{width:100%;border-collapse:collapse;font-size:9px}}th{{text-align:left;color:#6d707b;font-size:8px;letter-spacing:.08em;text-transform:uppercase;padding:8px;border-bottom:1px solid #dfded9}}td{{vertical-align:top;padding:9px 8px;border-bottom:1px solid #e9e7e1;overflow-wrap:anywhere}}td small{{display:block;color:#6d707b;margin-top:3px}}.check-status{{font-size:7px;font-weight:bold;letter-spacing:.05em}}.pass{{color:#272933}}.fail{{color:#b75e53}}.unknown{{color:#a87532}}.info,.not_applicable{{color:#6d707b}}.notice{{font-size:9px;color:#6d707b;margin:13px 0}}.empty{{padding:15px;background:#faf9f6;color:#6d707b;border-radius:9px}}.new-page{{break-before:page}}footer{{color:#6d707b}}</style></head><body>
    <header><div class='topline'>AgentLane · Website readiness report</div><h1>{text(report.get("website"))}</h1><p class='muted'>Public pages · read-only checks · Rubric {text(report.get("score_version"))}</p></header>
    {"<p class='notice'>Payment skipped in local development. This is not a purchase receipt.</p>" if report.get("development_payment_skipped") else ""}
    {failed_note}<section class='hero'><div class='score'><strong>{score_text}</strong><small>OUT OF 100</small></div><div><div class='topline'>{status}</div><h2 style='margin:8px 0'>A clearer view of your website.</h2><p class='muted'>{text(report.get("score_explanation"))}</p></div></section>
    <div class='stats'><div class='stat'><b>{text(coverage.get("checks_passed"), "0")}</b><span>Checks passed</span></div><div class='stat'><b>{text(coverage.get("checks_failed"), "0")}</b><span>Issues observed</span></div><div class='stat'><b>{text(coverage.get("checks_inconclusive"), "0")}</b><span>Inconclusive</span></div><div class='stat'><b>{text(report.get("pages_crawled"), "0")}</b><span>Pages crawled</span></div></div>
    {policy_section}<h2>Readiness by area</h2>{categories or '<p class="empty">Category scores are not available for this scan.</p>'}
    <h2>Priority insights</h2>{insights or '<p class="empty">No priority insights were generated from the available evidence.</p>'}
    <p class='notice'>This is a static, preliminary assessment. Real AI agent tasks were not run, so this report does not prove that an agent can or cannot complete a task.</p>
    <section class='new-page'><h2>Checks and evidence</h2><p class='muted'>Pages discovered: {text(report.get("pages_discovered"), "0")} · Crawled: {text(report.get("pages_crawled"), "0")} · Failed: {text(report.get("pages_failed"), "0")}</p><table><thead><tr><th>Status</th><th>Check</th><th>Details and evidence</th></tr></thead><tbody>{checks or '<tr><td colspan="3">No check details available.</td></tr>'}</tbody></table>{f'<p class="notice">{text(truncation_note)}</p>' if truncation_note else ""}</section>
    <p class='notice'>Generated by AgentLane. This report reflects only checks with evidence available at scan time.</p></body></html>"""


async def free_pdf_export(report):
    return await _render_pdf(render_free_html(report))


async def _render_pdf(html):
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
                await page.set_content(html, wait_until="domcontentloaded")
                return await page.pdf(
                    format="A4",
                    print_background=True,
                    display_header_footer=True,
                    header_template="<span></span>",
                    footer_template='<div style="font-size:8px;width:100%;text-align:center">AgentLane · <span class="pageNumber"></span> / <span class="totalPages"></span></div>',
                )
            finally:
                await browser.close()
