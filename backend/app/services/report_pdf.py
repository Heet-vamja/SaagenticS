"""Offline PDF rendering of escaped report data, with all network requests blocked."""

import asyncio
import base64
from functools import lru_cache
from html import escape
from pathlib import Path

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
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>AgentLane report</title><style>{_font_faces()}
    @page{{size:A4;margin:18mm}}body{{font-family:'Instrument Sans',Arial,sans-serif;color:#0E1013;font-size:11px;line-height:1.6}}h1{{font-size:30px;line-height:1.1}}h2{{margin-top:28px;font-size:19px}}h3{{font-size:14px}}.score{{font-size:48px}}.notice{{padding:12px;background:#F6F5EF;border-left:3px solid #CBF34A}}table{{width:100%;border-collapse:collapse}}td{{border-bottom:1px solid #dfded9;padding:7px}}article{{break-inside:avoid;border-top:1px solid #dfded9;padding:16px 0}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;font:10px/1.6 'JetBrains Mono',monospace;font-variant-ligatures:none;padding:10px;background:#faf9f6}}small{{color:#62646A}}p{{overflow-wrap:anywhere}}</style></head><body><small>AgentLane · Readiness report</small><h1>{text(report["project"]["name"])}</h1><p>{text(report["project"]["website_url"])}</p><div class="score">{text(report["scan"].get("overall_score"))}<small> / 100</small></div><p class="notice">{score_notice} {"Partial coverage: some checks were inconclusive." if summary.get("provisional") else ""} This is not a full accessibility certification or a guarantee that an agent can complete tasks.</p><table>{categories}</table><h2>Agent task results</h2>{tasks or "<p>No agent task results are available.</p>"}<h2>Top priority fixes</h2><ol>{priorities}</ol><h2>Findings and evidence</h2>{findings or "<p>No findings recorded. Check coverage before interpreting this result.</p>"}<p>Export includes up to 100 findings. Use JSON or CSV for all findings. Static checks use the versioned {text(summary.get("version") or "static rubric")} rubric.</p></body></html>"""


async def pdf_export(report):
    return await _render_pdf(render_html(report))


FONT_DIR = Path(__file__).with_name("pdf_fonts")
CHECK_ORDER = {"FAIL": 0, "UNKNOWN": 1, "PASS": 2, "INFO": 3, "NOT_APPLICABLE": 4}
CHECK_LABEL = {
    "FAIL": "Issue",
    "UNKNOWN": "Inconclusive",
    "PASS": "Passed",
    "INFO": "Informational",
    "NOT_APPLICABLE": "Not applicable",
}
LOGO = (
    "<svg width='22' height='22' viewBox='0 0 64 64' aria-hidden='true'>"
    "<rect width='64' height='64' rx='18' fill='#0E1013'/>"
    "<path d='M25 50c0-13 14-14 14-26V14' fill='none' stroke='#CBF34A' stroke-width='8' "
    "stroke-linecap='round'/><path d='M25 50V14' fill='none' stroke='#F6F5EF' "
    "stroke-width='8' stroke-linecap='round'/></svg>"
)


@lru_cache
def _font_faces():
    """The product fonts as data URIs: the renderer is offline, so nothing is fetched."""
    faces = []
    for family, filename, weight in (
        ("Instrument Sans", "InstrumentSans-Latin.woff2", "400 700"),
        ("JetBrains Mono", "JetBrainsMono-Latin.woff2", "100 800"),
    ):
        path = FONT_DIR / filename
        if not path.exists():
            continue
        data = base64.b64encode(path.read_bytes()).decode("ascii")
        faces.append(
            f"@font-face{{font-family:'{family}';font-weight:{weight};"
            f"src:url(data:font/woff2;base64,{data}) format('woff2')}}"
        )
    return "".join(faces)


def _plural(count, one, many=None):
    return f"{count} {one if count == 1 else (many or one + 's')}"


def _verdict(score, domain):
    """Same sentence as the online report: the score covers finding and reading pages."""
    if score >= 85:
        return f"Agents can find and read most of {domain}."
    if score >= 65:
        return f"Agents can reach {domain}, but miss parts of it."
    return f"Agents struggle to find and read {domain}."


def _check_groups(checks):
    """One row per check across pages, issues first, like the online report."""
    categories = {}
    for check in checks:
        groups = categories.setdefault(check.get("category") or "Other", {})
        group = groups.setdefault(
            check.get("title") or "Check",
            {"title": check.get("title") or "Check", "status": check.get("status"), "rows": []},
        )
        group["rows"].append(check)
        if CHECK_ORDER.get(check.get("status"), 9) < CHECK_ORDER.get(group["status"], 9):
            group["status"] = check.get("status")
    result = []
    for category, groups in categories.items():
        rows = sorted(groups.values(), key=lambda g: (CHECK_ORDER.get(g["status"], 9), g["title"]))
        issues = sum(1 for g in rows if g["status"] == "FAIL")
        result.append((category, rows, issues))
    return sorted(result, key=lambda item: (-item[2], item[0]))


def _group_summary(group):
    pages = {row.get("url") or "" for row in group["rows"]}
    status = group["status"]
    hits = {row.get("url") or "" for row in group["rows"] if row.get("status") == status}
    if status in ("FAIL", "UNKNOWN"):
        share = (
            ("1 page" if len(hits) == 1 else f"all {_plural(len(hits), 'page')}")
            if len(hits) == len(pages)
            else f"{len(hits)} of {_plural(len(pages), 'page')}"
        )
        return f"{CHECK_LABEL[status]} on {share}", sorted(hits - {""})
    if status == "PASS":
        return f"Passed on {_plural(len(pages), 'page')}", []
    if status == "INFO":
        return f"Recorded on {_plural(len(pages), 'page')}", []
    return f"Not applicable on {_plural(len(pages), 'page')}", []


def render_free_html(report):
    """Render only the public, free-report fields; never include the full scan report."""
    if hasattr(report, "model_dump"):
        report = report.model_dump(mode="json")

    def text(value, fallback="Not available"):
        return escape(str(value if value not in (None, "") else fallback))

    def path(url):
        return text(str(url).split("://", 1)[-1])

    website = str(report.get("website") or "")
    domain = website.split("://", 1)[-1].strip("/").removeprefix("www.") or "this website"
    coverage = report.get("coverage", {})
    score = report.get("score")
    score_value = max(0, min(100, round(score))) if isinstance(score, (int, float)) else None
    insights = report.get("insights", [])[:10]
    checks = report.get("checks", [])
    categories = report.get("category_scores", [])

    # Score dial: an SVG ring, so the PDF needs no images or scripts.
    ring = (
        "<svg class='ring' viewBox='0 0 180 180' aria-hidden='true'>"
        "<circle cx='90' cy='90' r='74' fill='none' stroke='#EEEDE5' stroke-width='14'/>"
        + (
            f"<circle cx='90' cy='90' r='74' fill='none' stroke='#11744A' stroke-width='14' "
            f"stroke-linecap='round' pathLength='100' stroke-dasharray='100' "
            f"stroke-dashoffset='{100 - score_value}' transform='rotate(-90 90 90)'/>"
            if score_value
            else ""
        )
        + "</svg>"
    )
    unscored = {c.get("name") for c in categories if c.get("score") is None}
    unscored_high = sum(
        1
        for i in insights
        if str(i.get("severity")).upper() in ("HIGH", "CRITICAL") and i.get("category") in unscored
    )
    crawled = report.get("pages_crawled") or 0
    discovered = report.get("pages_discovered") or 0
    sample = (
        f"We checked {crawled} of the {discovered} pages we found."
        if discovered > crawled
        else f"We checked {_plural(crawled, 'public page')}."
    )
    partial = report.get("status") == "FAILED" or (report.get("pages_failed") or 0) > 0
    if score_value is None:
        verdict = "There isn’t enough evidence yet."
        lede = "This scan did not gather enough confirmed evidence to calculate a static score."
    else:
        verdict = _verdict(score_value, domain)
        if partial:
            follow = " Some pages couldn’t be inspected, so the score covers only what we reached."
        elif unscored_high:
            verb = "affects" if unscored_high == 1 else "affect"
            follow = (
                f" {_plural(unscored_high, 'high-priority issue')} {verb} how agents use your"
                " pages, which isn’t part of the score yet."
            )
        elif insights:
            follow = f" {_plural(len(insights), 'finding')} below, highest impact first."
        else:
            follow = " Nothing in this sample needs a priority fix."
        lede = sample + follow
    label = (
        "Score unavailable"
        if score_value is None
        else "Partial static assessment"
        if partial
        else "Preliminary static readiness"
    )

    area_cells = []
    for item in categories:
        found = [i for i in insights if i.get("category") == item.get("name")]
        high = any(str(i.get("severity")).upper() in ("HIGH", "CRITICAL") for i in found)
        if item.get("score") is not None:
            value = max(0, min(100, item["score"]))
            right = text(round(item["score"]))
            bar = f"<div class='bar'><i style='width:{value}%'></i></div>"
            note = f"{item.get('evaluated', 0)} of {_plural(item.get('total', 0), 'check')}"
            cls = ""
        else:
            right = "<span class='unscored-label'>Not scored</span>"
            bar = "<div class='bar empty'></div>"
            note = (
                _plural(len(found), "high-priority issue" if high else "issue")
                if found
                else "Needs real agent tests"
                if item.get("name") == "Agent usability"
                else "No scoreable checks"
            )
            cls = " unscored"
        area_cells.append(
            f"<div class='area{cls}'><div class='area-top'><b>{text(item.get('name'))}</b>"
            f"<span class='num'>{right}</span></div>{bar}"
            f"<p class='{'danger' if cls and high else 'muted'}'>{text(note)}</p></div>"
        )
    areas = f"<div class='areas'>{''.join(area_cells)}</div>" if area_cells else ""

    fail_pages = {}
    for check in checks:
        if check.get("status") == "FAIL" and check.get("url"):
            fail_pages.setdefault(check.get("title"), set()).add(check["url"])
    finding_rows = []
    for index, item in enumerate(insights, 1):
        severity = str(item.get("severity") or "").upper()
        tone, sev = (
            ("danger", "Critical" if severity == "CRITICAL" else "High")
            if severity in ("HIGH", "CRITICAL")
            else ("warning", "Medium")
            if severity == "MEDIUM"
            else ("muted", "Low")
        )
        url = item.get("evidence_url")
        more = len(fail_pages.get(item.get("title"), set()) - {url}) if url else 0
        seen = (
            f"<div class='seen'>Seen on <span class='mono'>{path(url)}</span>"
            + (f" and {_plural(more, 'more page')}" if more else "")
            + "</div>"
            if url
            else ""
        )
        evidence = item.get("evidence_summary") or ""
        if evidence.lower().startswith("example inspected element:"):
            evidence = evidence.split(":", 1)[1].strip()
        found = (
            f"<div class='row found'><span>Found</span><code>{text(evidence)}</code></div>"
            if evidence
            else ""
        )
        recommendation = item.get("recommendation") or ""
        fix = (
            "<div class='row fix'><span>Fix</span>"
            + (
                f"<code>{text(recommendation)}</code>"
                if recommendation.lstrip().startswith("<")
                else f"<p>{text(recommendation)}</p>"
            )
            + "</div>"
            if recommendation
            else ""
        )
        diff = f"<div class='diff'>{seen}{found}{fix}</div>" if seen or found or fix else ""
        finding_rows.append(
            f"<article class='finding'><div class='finding-top'><span class='index'>{index:02d}</span>"
            f"<div><p class='meta'><b class='{tone}'>{sev}</b> · {text(item.get('category'))}</p>"
            f"<h3>{text(item.get('title'))}</h3></div></div>"
            f"<p class='muted desc'>{text(item.get('description'))}</p>{diff}</article>"
        )
    findings = "".join(finding_rows)

    check_sections = []
    background = []
    for category, groups, _issues in _check_groups(checks):
        rows = []
        for group in groups:
            summary, pages = _group_summary(group)
            if CHECK_ORDER.get(group["status"], 9) >= CHECK_ORDER["INFO"]:
                background.append((category, group["title"], summary))
                continue
            page_list = (
                "<p class='pages mono'>"
                + ", ".join(path(page) for page in pages[:6])
                + (f" and {len(pages) - 6} more" if len(pages) > 6 else "")
                + "</p>"
                if pages
                else ""
            )
            status = text(group["status"], "UNKNOWN")
            rows.append(
                f"<tr><td><b>{text(group['title'])}</b><p class='muted'>{text(summary)}</p>"
                f"{page_list}</td><td class='status'><span class='chip {status.lower()}'>"
                f"{text(CHECK_LABEL.get(group['status'], group['status']))}</span></td></tr>"
            )
        if rows:
            check_sections.append(
                f"<h3 class='cat'>{text(category)}</h3><table>{''.join(rows)}</table>"
            )
    background_table = (
        "<h3 class='cat'>Informational and not applicable</h3><ul class='background'>"
        + "".join(
            f"<li><b>{text(title)}</b><span class='muted'>{text(category)} · {text(summary)}</span></li>"
            for category, title, summary in background
        )
        + "</ul>"
        if background
        else ""
    )

    policy_rows = "".join(
        f"<tr><td>{text(row.get('user_agent'))}</td><td>{text(row.get('kind'))}</td>"
        f"<td>{text(row.get('policy'))}</td></tr>"
        for row in report.get("access_policies", [])
    )
    policy_section = (
        "<h2>Our scanner and declared AI-bot policies</h2>"
        "<p class='note'>These are robots.txt declarations for sampled paths, not verified provider"
        " access, AI-search visibility, or task success. A restriction encountered by our scanner"
        " does not prove that other providers are blocked.</p>"
        "<table class='policies'><tr><th>Identity</th><th>Scope</th><th>Declared policy</th></tr>"
        + policy_rows
        + "</table>"
        if policy_rows
        else ""
    )
    truncation_note = (
        "<p class='note'>This report shows the first 300 checks. Open the online report for"
        " the full available list.</p>"
        if report.get("checks_truncated")
        else ""
    )
    failed_note = (
        f"<div class='callout'>{text(report.get('failure_message'))}</div>"
        if report.get("failure_message")
        else ""
    )
    dev_note = (
        "<div class='callout'>Payment skipped in local development. This is not a purchase"
        " receipt.</div>"
        if report.get("development_payment_skipped")
        else ""
    )
    style = (
        _font_faces()
        + """
@page{size:A4;margin:16mm 15mm 18mm}
*{box-sizing:border-box}
body{margin:0;font-family:'Instrument Sans',Arial,sans-serif;font-size:10.5px;line-height:1.55;color:#0E1013;background:#fff}
.mono,code{font-family:'JetBrains Mono',monospace;font-variant-ligatures:none}
.muted{color:#62646A}.danger{color:#C2183F}.warning{color:#9A5200}
p{margin:0;overflow-wrap:anywhere}
header{display:flex;justify-content:space-between;align-items:center;padding-bottom:14px;border-bottom:1px solid #E2E0D6}
.brand{display:flex;align-items:center;gap:8px;font-size:14px;font-weight:600;letter-spacing:-.01em}
.doc{font-size:9.5px;color:#62646A}
h1{margin:22px 0 4px;font-size:30px;font-weight:560;letter-spacing:-.035em;line-height:1.05;overflow-wrap:anywhere}
h2{margin:26px 0 10px;font-size:17px;font-weight:600;letter-spacing:-.02em}
h3{margin:0;font-size:12.5px;font-weight:600}
.summary{margin-top:18px;border:1px solid #E2E0D6;border-radius:16px;overflow:hidden;break-inside:avoid}
.hero{display:grid;grid-template-columns:120px 1fr;gap:24px;align-items:center;padding:20px 22px}
.dial{position:relative;width:120px;height:120px}
.ring{position:absolute;inset:0;width:100%;height:100%}
.dial div{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center}
.dial strong{font-size:36px;font-weight:600;letter-spacing:-.04em;line-height:1;color:#11744A}
.dial small{margin-top:3px;font-size:9px;color:#62646A}
.label{display:inline-block;border-radius:99px;padding:2px 9px;background:#EEF8CF;color:#4A6400;font-size:9px;font-weight:600}
.verdict{margin:8px 0 6px;font-size:19px;font-weight:600;letter-spacing:-.02em;line-height:1.2}
.areas{display:grid;grid-template-columns:repeat(4,1fr);border-top:1px solid #E2E0D6}
.area{padding:12px 14px;border-right:1px solid #E2E0D6}.area:last-child{border-right:0}
.area.unscored{background:#FBFAF6}
.area-top{display:flex;justify-content:space-between;gap:6px;font-size:10px}
.num{font-family:'JetBrains Mono',monospace;font-size:10px}
.bar{height:5px;margin:7px 0 5px;border-radius:99px;background:#EEEDE5;overflow:hidden}
.bar i{display:block;height:100%;border-radius:99px;background:#0E1013}
.bar.empty{background:repeating-linear-gradient(90deg,#E2E0D6 0 5px,transparent 5px 9px)}
.area p{font-size:9px}
.counts{padding:9px 14px;border-top:1px solid #E2E0D6;background:#FBFAF6;font-size:9px;color:#62646A}
.explain{margin-top:8px;font-size:8.5px;color:#62646A}
.finding{padding:13px 0;border-top:1px solid #E2E0D6;break-inside:avoid}
.finding-top{display:flex;gap:12px}
.index{width:18px;padding-top:12px;font-family:'JetBrains Mono',monospace;font-size:9px;color:#62646A}
.meta{font-size:9px;color:#62646A}.meta b{font-weight:600}
.desc{margin:5px 0 0 30px}
.diff{margin:9px 0 0 30px;border:1px solid #E2E0D6;border-radius:10px;overflow:hidden}
.seen{padding:6px 10px;border-bottom:1px solid #E2E0D6;font-size:9px;color:#62646A}
.row{display:grid;grid-template-columns:34px 1fr;gap:10px;padding:6px 10px;font-size:9.5px}
.row span{font-size:8.5px;font-weight:600}
.row code{white-space:pre-wrap;overflow-wrap:anywhere;font-size:9px}
.found{background:#FDEEF1}.found span{color:#C2183F}
.fix{background:#F3FAE0}.fix span{color:#4A6400}
.cat{margin:16px 0 6px}
table{width:100%;border-collapse:collapse;font-size:9.5px}
th{text-align:left;padding:6px 8px;border-bottom:1px solid #E2E0D6;color:#62646A;font-size:8.5px;font-weight:600}
td{vertical-align:top;padding:7px 8px;border-bottom:1px solid #EEEDE5}
tr{break-inside:avoid}
td p{font-size:9px}
.pages{margin-top:2px;font-size:8.5px;color:#62646A}
.status{width:90px;text-align:right}
.chip{display:inline-block;border-radius:99px;padding:1px 8px;font-size:8.5px;font-weight:600;background:#EEEDE5;color:#4D4F55}
.chip.fail{background:#FFF0D6;color:#9A5200}.chip.pass{background:#E0F5E6;color:#11744A}
.note{margin:10px 0;font-size:9px;color:#62646A}
.callout{margin-top:14px;padding:10px 12px;border-radius:10px;background:#FFF0D6;color:#9A5200;font-size:9.5px}
.empty-state{padding:12px;border-radius:10px;background:#FBFAF6;color:#62646A}
.new-page{break-before:page}
.unscored-label{font-family:'Instrument Sans',Arial,sans-serif;font-size:9px;color:#62646A}
.background{display:grid;grid-template-columns:1fr 1fr;gap:6px 18px;margin:0;padding:0;list-style:none}
.background li{break-inside:avoid;padding:5px 0;border-bottom:1px solid #EEEDE5;font-size:9px}
.background b{display:block;font-weight:600}
.background span{font-size:8.5px}
"""
    )
    return f"""<!doctype html><html><head><meta charset='utf-8'><title>AgentLane report · {text(domain)}</title><style>{style}</style></head><body>
<header><div class='brand'>{LOGO}AgentLane</div><div class='doc'>Website readiness report</div></header>
<h1>{text(domain)}</h1><p class='muted'>Public pages only · read-only checks · rubric {text(report.get("score_version"))}</p>
{dev_note}{failed_note}
<section class='summary'><div class='hero'><div class='dial'>{ring}<div><strong>{score_value if score_value is not None else "—"}</strong><small>out of 100</small></div></div>
<div><span class='label'>{label}</span><p class='verdict'>{text(verdict)}</p><p class='muted'>{text(lede)}</p></div></div>
{areas}<div class='counts'>{text(coverage.get("checks_passed"), "0")} checks passed · {text(coverage.get("checks_failed"), "0")} issues · {text(coverage.get("checks_inconclusive"), "0")} inconclusive</div></section>
<p class='explain'>{text(report.get("score_explanation"))}</p>
<h2>What to fix first</h2>{findings or "<p class='empty-state'>No priority findings were generated from the available evidence.</p>"}
<p class='note'>Ready prompts, asset drafts and re-scans are in your online Fix Center. This is a static, preliminary assessment: real AI agent tasks were not run, so it does not prove that an agent can or cannot complete a task.</p>
{policy_section}
<section class='new-page'><h2>What was checked</h2><p class='muted'>{text(crawled, "0")} pages checked in a bounded sample ({text(discovered, "0")} discovered, {text(report.get("pages_failed"), "0")} failed). Each check appears once with its result across those pages, issues first.</p>
{"".join(check_sections) or "<p class='empty-state'>No check details available.</p>"}{background_table}{truncation_note}</section>
<p class='note'>Generated by AgentLane. This report reflects only checks with evidence available at scan time.</p></body></html>"""


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
                    footer_template='<div style="font:8px Arial,sans-serif;color:#62646A;width:100%;text-align:center">AgentLane · <span class="pageNumber"></span> / <span class="totalPages"></span></div>',
                )
            finally:
                await browser.close()
