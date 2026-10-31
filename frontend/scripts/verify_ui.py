"""Real UI/API smoke checks. Uses the workspace's existing Python Playwright install.

Run from frontend: ../backend/.venv/bin/python scripts/verify_ui.py
A disposable project is created; its ID is written to QA_OUTPUT/records.json for cleanup.
No model result is fabricated: the real configured endpoint is used.
"""

import asyncio
import json
import os
import time
from pathlib import Path

import httpx
from playwright.async_api import async_playwright, expect

BASE = os.environ.get("UI_BASE_URL", "http://localhost:13000")
OUTPUT = Path(os.environ.get("QA_OUTPUT", "/private/tmp/agentreadiness-redesign"))
AXE = Path(__file__).resolve().parents[1] / "node_modules/axe-core/axe.min.js"


async def check_page(page, label, screenshot=True):
    await page.evaluate("""async () => { await document.fonts.ready;
      await Promise.allSettled(document.getAnimations().filter(a => a.effect?.getTiming().iterations !== Infinity).map(a=>a.finished));
    }""")
    assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (
        f"Page overflow: {label}"
    )
    await page.add_script_tag(path=str(AXE))
    violations = await page.evaluate("""async () => (await axe.run(document, {
      runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}
    })).violations.map(v=>({id:v.id,impact:v.impact,description:v.description,nodes:v.nodes.map(n=>n.target)}))""")
    assert not violations, (
        f"Accessibility failures on {label}: {json.dumps(violations)}"
    )
    if screenshot:
        await page.screenshot(path=str(OUTPUT / f"{label}.png"), full_page=True)
    print(f"PASS {label}: overflow and WCAG checks", flush=True)


async def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    previous = (
        json.loads((OUTPUT / "records.json").read_text())
        if (OUTPUT / "records.json").exists()
        else {}
    )
    owned = list(
        dict.fromkeys(
            [
                *previous.get("project_ids", []),
                *([previous["project_id"]] if previous.get("project_id") else []),
            ]
        )
    )
    records = {"project_ids": owned}
    with httpx.Client(base_url=BASE, timeout=20, trust_env=False) as api:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page(viewport={"width": 1440, "height": 1100})
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                await page.goto(BASE, wait_until="networkidle")
                await check_page(page, "landing-desktop")
                # Reuse a prior isolated QA project when retrying after a failed assertion.
                if previous.get("project_id"):
                    project = api.get(
                        f"/api/v1/projects/{previous['project_id']}"
                    ).json()
                    records["project_id"] = project["id"]
                else:
                    await page.goto(BASE + "/projects", wait_until="networkidle")
                    await page.get_by_role(
                        "button", name="New project", exact=True
                    ).first.click()
                    project_name = f"Design QA {int(time.time())}"
                    await page.get_by_label("Project name", exact=True).fill(project_name)
                    await page.get_by_label("Website URL", exact=True).first.fill(
                        "https://example.com/"
                    )
                    await page.get_by_role(
                        "button", name="Create project", exact=True
                    ).click()
                    await page.get_by_role(
                        "link", name=project_name, exact=False
                    ).first.wait_for()
                    project = next(
                        x
                        for x in api.get("/api/v1/projects").json()
                        if x["name"] == project_name
                    )
                    records["project_id"] = project["id"]
                    records["project_ids"].append(project["id"])
                (OUTPUT / "records.json").write_text(json.dumps(records))
                # Hero URL CTA must reuse the existing project, start a scan and navigate.
                if previous.get("scan_id"):
                    records["scan_id"] = previous["scan_id"]
                    await page.goto(
                        BASE + f"/scans/{records['scan_id']}", wait_until="networkidle"
                    )
                else:
                    await page.goto(BASE, wait_until="networkidle")
                    await page.get_by_label("Website URL", exact=True).first.fill(
                        "https://example.com/"
                    )
                    await page.get_by_role(
                        "button", name="Scan your website", exact=True
                    ).first.click()
                    await page.wait_for_url("**/scans/*", timeout=20000)
                    records["scan_id"] = page.url.split("/")[-1]
                    (OUTPUT / "records.json").write_text(json.dumps(records))
                await page.get_by_role(
                    "heading", name="Discovered pages, with evidence"
                ).wait_for()
                for _ in range(30):
                    scan = api.get(f"/api/v1/scans/{records['scan_id']}").json()
                    if scan["status"] in ("COMPLETED", "FAILED"):
                        break
                    await asyncio.sleep(1)
                assert scan["status"] == "COMPLETED", scan.get("error_summary")
                await page.get_by_role(
                    "button", name="https://example.com/", exact=False
                ).wait_for()
                await check_page(page, "scan-desktop")
                await page.get_by_role(
                    "button", name="https://example.com/", exact=False
                ).click()
                await page.get_by_role("dialog").wait_for()
                assert (
                    await page.get_by_role("dialog")
                    .get_by_role("heading", name="Example Domain", exact=True)
                    .is_visible()
                )
                await page.keyboard.press("Escape")
                findings = api.get(
                    f"/api/v1/scans/{records['scan_id']}/findings"
                ).json()
                await page.get_by_role(
                    "tab", name="Technical findings", exact=False
                ).click()
                if findings:
                    await page.get_by_text(findings[0]["title"], exact=True).wait_for()
                else:
                    await page.get_by_text(
                        "No issues recorded in this view", exact=True
                    ).wait_for()
                await page.get_by_role("tab", name="Agent tests", exact=False).click()
                await page.get_by_text("Find Pricing", exact=True).click()
                assert await page.get_by_role(
                    "radio", name="Find Pricing", exact=False
                ).is_checked()
                await page.get_by_role(
                    "button", name="Run Agent Task", exact=True
                ).click()
                await page.wait_for_url("**/agent-tests/*", timeout=20000)
                records["agent_test_id"] = page.url.split("/")[-1]
                (OUTPUT / "records.json").write_text(json.dumps(records))
                await page.get_by_role(
                    "heading", name="Execution timeline", exact=True
                ).wait_for()
                for _ in range(130):
                    test = api.get(
                        f"/api/v1/agent-tests/{records['agent_test_id']}"
                    ).json()
                    if test["status"] in ("COMPLETED", "FAILED"):
                        break
                    await asyncio.sleep(1)
                assert test["status"] in ("COMPLETED", "FAILED")
                assurance_copy = {
                    "rules": "Rule verified",
                    "judged": "LLM judged · lower assurance",
                    "unverified": "The agent claim was not independently verified.",
                }[test.get("verification_method", "unverified")]
                await page.get_by_text(assurance_copy, exact=True).wait_for()
                if test.get("failure_reason") and "402" in test["failure_reason"]:
                    await page.get_by_text(
                        "Model request failed", exact=True
                    ).wait_for()
                await check_page(page, "agent-desktop")
                steps = api.get(
                    f"/api/v1/agent-tests/{records['agent_test_id']}/steps"
                ).json()
                expected_verification = {
                    "rules": "RULE_VERIFIED",
                    "judged": "LLM_JUDGED",
                    "unverified": "NOT_INDEPENDENTLY_VERIFIED",
                }[test.get("verification_method", "unverified")]
                assert steps and test["verification"] == expected_verification
                screenshot = next((s for s in steps if s["has_screenshot"]), None)
                if screenshot:
                    await page.get_by_role(
                        "button",
                        name=f"Step {screenshot['step_number']:02}",
                        exact=False,
                    ).click()
                    await page.get_by_alt_text(
                        "Captured browser screenshot", exact=False
                    ).wait_for()
                # Project, history, global metrics, and another scan from project details.
                await page.goto(
                    BASE + f"/projects/{project['id']}", wait_until="networkidle"
                )
                await page.get_by_role(
                    "heading", name="Agent executions", exact=True
                ).wait_for()
                await check_page(page, "project-desktop")
                await page.get_by_role(
                    "button", name="Start Scan", exact=True
                ).first.click()
                await page.wait_for_url("**/scans/*", timeout=20000)
                await page.goto(BASE + "/agent-tests", wait_until="networkidle")
                await page.get_by_role(
                    "link", name="Find Pricing", exact=True
                ).first.wait_for()
                await check_page(page, "agents-desktop")
                await page.goto(BASE + "/dashboard", wait_until="networkidle")
                await page.get_by_role(
                    "heading", name="Recent projects", exact=True
                ).wait_for()
                await check_page(page, "overview-desktop")
                await page.get_by_role("button", name="Collapse sidebar").click()
                await page.get_by_role("button", name="Expand sidebar").click()
                await page.get_by_role("button", name="Switch to dark theme").click()
                await check_page(page, "overview-dark")
                await page.get_by_role("button", name="Switch to light theme").click()
                # Mobile/tablet pages and focus-trapped navigation drawer.
                for width, label in [
                    (390, "mobile"),
                    (768, "tablet"),
                    (320, "small-mobile"),
                ]:
                    await page.set_viewport_size({"width": width, "height": 900})
                    for route, name in [
                        ("/", "landing"),
                        ("/dashboard", "overview"),
                        ("/projects", "projects"),
                        (f"/scans/{records['scan_id']}", "scan"),
                        (f"/agent-tests/{records['agent_test_id']}", "agent"),
                    ]:
                        await page.goto(BASE + route, wait_until="networkidle")
                        if name != "landing":
                            await page.locator(
                                '[role="status"][aria-label="Loading content"]'
                            ).wait_for(state="detached")
                        await check_page(page, f"{name}-{label}")
                    await page.get_by_role("button", name="Open navigation").click()
                    await page.get_by_role(
                        "dialog", name="Workspace navigation"
                    ).wait_for()
                    await page.keyboard.press("Escape")
                    await page.get_by_role("dialog").wait_for(state="hidden")
                    await expect(
                        page.get_by_role("button", name="Open navigation")
                    ).to_be_focused()
                assert not errors, errors
                print(
                    "PASS real project creation, URL submission, scan creation/progress, page details, task creation, history, evidence, keyboard navigation and theme.",
                    flush=True,
                )
                print(
                    "Real inference outcome:",
                    test["status"],
                    test.get("failure_reason"),
                    flush=True,
                )
            finally:
                await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
