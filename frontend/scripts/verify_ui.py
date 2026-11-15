"""Check the public customer flow against an existing scan.

Run from frontend with CUSTOMER_REPORT_SCAN_ID set. This script does not create
projects, scans, or agent tests and never calls a model.
"""

import asyncio
import json
import os
from pathlib import Path

import httpx
from playwright.async_api import async_playwright

BASE = os.environ.get("UI_BASE_URL", "http://localhost:13000")
SCAN_ID = os.environ.get("CUSTOMER_REPORT_SCAN_ID")
OUTPUT = Path(os.environ.get("QA_OUTPUT", "/private/tmp/agentreadiness-customer-flow"))
AXE = Path(__file__).resolve().parents[1] / "node_modules/axe-core/axe.min.js"


async def check_page(page, label, screenshot=True):
    await page.evaluate("document.fonts.ready")
    assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (
        f"Page overflow: {label}"
    )
    await page.add_script_tag(path=str(AXE))
    violations = await page.evaluate("""async () => (await axe.run(document, {
      runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}
    })).violations.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.map(n=>n.target)}))""")
    assert not violations, f"Accessibility failures on {label}: {json.dumps(violations)}"
    if screenshot:
        await page.screenshot(path=str(OUTPUT / f"{label}.png"), full_page=True)
    print(f"PASS {label}: no horizontal overflow or WCAG 2.1 AA violations", flush=True)


async def main():
    if not SCAN_ID:
        raise SystemExit("Set CUSTOMER_REPORT_SCAN_ID to an existing scan before running.")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with httpx.Client(base_url=BASE, timeout=20, trust_env=False) as client:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            try:
                page = await browser.new_page(viewport={"width": 1440, "height": 1100})
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                await page.goto(BASE, wait_until="networkidle")
                await page.get_by_role("heading", name="Be the website AI agents can actually use.").wait_for()
                await check_page(page, "landing-desktop")

                report_url = f"/results/{SCAN_ID}"
                await page.goto(BASE + report_url, wait_until="networkidle")
                await page.get_by_role("heading").first.wait_for()
                scan = client.get(f"/api/v1/scans/{SCAN_ID}").json()
                if scan["status"] == "COMPLETED":
                    await page.get_by_text("Preliminary readiness score").wait_for()
                    await page.get_by_role("link", name="Review all findings").wait_for()
                elif scan["status"] == "FAILED":
                    await page.get_by_text("We couldn’t finish this scan").wait_for()
                else:
                    await page.get_by_text("We’re checking your website").wait_for()
                await check_page(page, "customer-report-desktop")

                for width, label in [(390, "mobile"), (768, "tablet"), (320, "small-mobile")]:
                    await page.set_viewport_size({"width": width, "height": 900})
                    await page.goto(BASE + report_url, wait_until="networkidle")
                    await check_page(page, f"customer-report-{label}")
                assert not errors, errors
                print("PASS customer flow: homepage → existing scan report; no scan or agent test created.", flush=True)
            finally:
                await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
