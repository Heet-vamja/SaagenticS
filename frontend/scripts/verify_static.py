"""Report UI checks against clearly labeled, locally persisted HTTP fixtures.

No LLM or public website requests. Seed records using the documented test helper,
then set STATIC_QA_RECORDS to the local manifest. API persistence is tested by pytest.
"""

import asyncio
import json
import os
from pathlib import Path

from playwright.async_api import async_playwright
from verify_ui import BASE, check_page


async def main():
    manifest = Path(
        os.environ.get("STATIC_QA_RECORDS", "/private/tmp/static-qa-records.json")
    )
    records = json.loads(manifest.read_text())
    output = Path(os.environ.get("QA_OUTPUT", "/private/tmp/agentreadiness-static-ui"))
    output.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            page = await browser.new_page(viewport={"width": 1440, "height": 1050})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            await page.goto(
                BASE + f"/scans/{records['before']}", wait_until="networkidle"
            )
            await page.get_by_role("region", name="Static readiness score").wait_for()
            await page.get_by_role(
                "link", name="Open report, priority fixes and exports"
            ).click()
            await page.get_by_role(
                "heading", name="Top priority fixes", exact=True
            ).wait_for()
            await page.get_by_text(
                "Controls lack accessible names", exact=True
            ).first.wait_for()
            await check_page(page, "static-report-before", screenshot=False)
            await page.screenshot(
                path=str(output / "report-desktop.png"), full_page=True
            )
            # Real export endpoints and bytes, with no browser-agent or model execution.
            for format in ("JSON", "CSV", "PDF"):
                async with page.expect_download() as item:
                    await page.get_by_role(
                        "button", name=f"Export {format}", exact=True
                    ).click()
                download = await item.value
                destination = output / f"static-report.{format.lower()}"
                await download.save_as(destination)
                assert destination.stat().st_size > 50
                if format == "PDF":
                    assert destination.read_bytes().startswith(b"%PDF-")
            await page.get_by_role(
                "button", name="Create share link", exact=True
            ).click()
            link = page.get_by_label("Share report link", exact=True)
            await link.wait_for()
            shared_url = await link.input_value()
            # Do not print the capability token.
            await page.goto(shared_url, wait_until="networkidle")
            await page.get_by_text(
                "Shared static report · anyone with this link", exact=True
            ).wait_for()
            assert (
                await page.get_by_role("button", name="Create share link").count() == 0
            )
            await check_page(page, "shared-report", screenshot=False)
            await page.screenshot(
                path=str(output / "shared-report.png"), full_page=True
            )
            await page.goto(
                BASE + f"/scans/{records['after']}/report", wait_until="networkidle"
            )
            await page.get_by_role(
                "heading", name="Before / after", exact=True
            ).wait_for()
            await page.get_by_text("Resolved", exact=True).wait_for()
            await check_page(page, "static-report-after", screenshot=False)
            comparison = await (
                await page.request.get(
                    BASE + f"/api/v1/scans/{records['after']}/comparison"
                )
            ).json()
            assert comparison["available"] and comparison["resolved"]
            assert comparison["score_delta"] > 0
            await page.screenshot(
                path=str(output / "comparison-desktop.png"), full_page=True
            )
            # A share is scoped to its own scan; revoke the previously created link.
            await page.request.post(
                BASE + f"/api/v1/scans/{records['before']}/shares/revoke"
            )
            await page.goto(shared_url, wait_until="networkidle")
            await page.get_by_text(
                "Report link not found or expired", exact=True
            ).wait_for()
            await page.goto(
                BASE + f"/projects/{records['project_id']}", wait_until="networkidle"
            )
            await page.get_by_role(
                "heading", name="Static score history", exact=True
            ).wait_for()
            await check_page(page, "static-history", screenshot=False)
            # Re-test report layouts at actual mobile widths; no horizontal overflow.
            for width in (390, 320, 768):
                await page.set_viewport_size({"width": width, "height": 900})
                for scan_id, label in (
                    (records["before"], "report"),
                    (records["after"], "comparison"),
                ):
                    await page.goto(
                        BASE + f"/scans/{scan_id}/report", wait_until="networkidle"
                    )
                    await page.get_by_role(
                        "heading", name="Top priority fixes", exact=True
                    ).wait_for()
                    await check_page(page, f"static-{label}-{width}", screenshot=False)
                    await page.screenshot(
                        path=str(output / f"{label}-{width}.png"), full_page=True
                    )
            assert not errors, errors
            print(
                "PASS static reports, real JSON/CSV/PDF exports, sharing/revocation, comparison, score history and responsive accessibility; NO LLM USED.",
                flush=True,
            )
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
