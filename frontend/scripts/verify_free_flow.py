"""Browser smoke test for homepage URL submission → anonymous free report."""

import asyncio
import json
import os
from pathlib import Path

BASE = os.environ.get("FREE_SCAN_BASE_URL", "http://localhost:3010")
OUTPUT = Path(
    os.environ.get("FREE_SCAN_QA_OUTPUT", "/private/tmp/agentreadiness-free-flow")
)
TOKEN = "ui-test-token"
REPORT_PATH = f"/free-reports/{TOKEN}"


def report(status):
    pending = status == "PENDING"
    return {
        "status": status,
        "website": "https://example.com/",
        "phase": "CRAWLING" if pending else "COMPLETED",
        "progress_message": "Finding important pages on your website.",
        "score_version": "free-static-v3",
        "score": None if pending else 81.3,
        "score_status": "UNAVAILABLE" if pending else "PRELIMINARY",
        "score_explanation": "Preliminary score from deterministic checks. AI agent task testing is not included.",
        "category_scores": [
            {
                "name": "Discoverability",
                "score": 80,
                "weight": 30,
                "tested": True,
                "evaluated": 4,
                "total": 4,
            },
            {
                "name": "Content understanding",
                "score": 82,
                "weight": 25,
                "tested": True,
                "evaluated": 3,
                "total": 3,
            },
            {
                "name": "Structured data",
                "score": 82,
                "weight": 20,
                "tested": True,
                "evaluated": 2,
                "total": 3,
            },
            {
                "name": "Agent usability",
                "score": None,
                "weight": 25,
                "tested": False,
                "evaluated": 0,
                "total": 0,
            },
        ],
        "coverage": {
            "evaluated": 9,
            "total": 10,
            "passed": 7,
            "problems": 2,
            "untested": 1,
            "checks_total": 4,
            "checks_passed": 2,
            "checks_failed": 1,
            "checks_inconclusive": 1,
            "checks_informational": 0,
            "checks_not_applicable": 0,
        },
        "checks": []
        if pending
        else [
            {
                "category": "Navigation and interaction",
                "status": "FAIL",
                "title": "Controls lack accessible names",
                "description": "A control has no accessible name in the inspected page.",
                "url": "https://example.com/pricing",
                "evidence_summary": "Example inspected element: <button type=button>",
                "recommendation": "Give the control a clear accessible name while keeping its behavior.",
            },
            *[{
                "category": "Discoverability",
                "status": "PASS",
                "title": "No known bot challenge signal was observed",
                "description": f"Distinct {source} measurement of the same public page.",
                "url": "https://www.apple.com/",
                "evidence_summary": f"{source} markup was inspected.",
                "recommendation": None,
            } for source in ("raw", "rendered")],
            {
                "category": "Content understanding", "status": "UNKNOWN",
                "title": "Rendered comparison was inconclusive",
                "description": "The bounded sample did not establish this result.",
                "url": "https://example.com/", "evidence_summary": None, "recommendation": None,
            },
        ],
        "checks_truncated": False,
        "insights": []
        if pending
        else [
            {
                "category": "Agent usability",
                "severity": "HIGH",
                "title": "Controls lack accessible names",
                "description": "A control has no accessible name in the inspected page.",
                "evidence_url": "https://example.com/pricing",
                "evidence_summary": 'Example inspected element: <button type="button">',
                "recommendation": "Give the control a clear accessible name while keeping its behavior.",
            }
        ],
        "pages_crawled": 3 if not pending else 1,
        "pages_discovered": 5 if not pending else 3,
        "pages_failed": 0,
        "failure_message": None,
    }


async def check_view(page, label):
    await page.evaluate("document.fonts.ready")
    assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (
        f"Page overflow at {label}"
    )
    await page.add_script_tag(
        path=str(
            Path(__file__).resolve().parents[1] / "node_modules/axe-core/axe.min.js"
        )
    )
    violations = await page.evaluate("""async () => (await axe.run(document, {
      runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}
    })).violations.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.map(n=>({target:n.target,html:n.html,summary:n.failureSummary}))}))""")
    await page.screenshot(path=str(OUTPUT / f"{label}.png"), full_page=True)
    assert not violations, (
        f"Accessibility failures at {label}: {json.dumps(violations)}"
    )
    print(f"PASS {label}: no overflow or WCAG 2.1 AA violations", flush=True)


async def main():
    from verify_fix_center import run

    await run()


if __name__ == "__main__":
    asyncio.run(main())
