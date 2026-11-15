"""Isolated frontend state fixtures; no fixture data is written to the backend."""

import asyncio
from urllib.parse import urlsplit

from playwright.async_api import async_playwright
from verify_ui import BASE, check_page


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            page = await browser.new_page(viewport={"width": 1440, "height": 1000})
            state = {"phase": "PENDING", "requests": 0}

            async def agent_route(route):
                state["requests"] += 1
                phase = state["phase"]
                step = {
                    "id": "fixture-step",
                    "step_number": 1,
                    "page_url": "https://fixture.example/",
                    "action_type": "navigate",
                    "reasoning_summary": "Open the fixture homepage",
                    "action_arguments": {},
                    "action_result": {"message": "Opened fixture"},
                    "observation_summary": {
                        "title": "UI fixture page",
                        "visible_text": "Fixture content only",
                        "elements": [],
                    },
                    "error_message": None,
                    "duration_ms": 200,
                    "has_screenshot": False,
                }
                if urlsplit(route.request.url).path.endswith("/steps"):
                    await route.fulfill(json=[] if phase == "PENDING" else [step])
                else:
                    await route.fulfill(
                        json={
                            "id": "ui-fixture",
                            "scan_id": "fixture-scan",
                            "task_type": "FIND_PRICING",
                            "task_description": "Find the pricing page (isolated UI fixture)",
                            "model_identifier": "Fixture model · UI tests only",
                            "starting_url": "https://fixture.example/",
                            "allowed_domains": ["fixture.example"],
                            "status": phase,
                            "steps_completed": 0 if phase == "PENDING" else 1,
                            "execution_duration": None
                            if phase in ("RUNNING", "PENDING")
                            else 2.4,
                            "final_url": "https://fixture.example/",
                            "agent_declared_outcome": "Fixture agent reported pricing."
                            if phase == "COMPLETED"
                            else None,
                            "failure_reason": "Agent execution time limit reached"
                            if phase == "FAILED"
                            else None,
                            "metrics": {"timeouts": 1} if phase == "FAILED" else {},
                            "verification": "NOT_INDEPENDENTLY_VERIFIED",
                            "started_at": None,
                            "completed_at": None,
                        }
                    )

            await page.route("**/api/v1/agent-tests/ui-fixture**", agent_route)
            await page.goto(BASE + "/agent-tests/ui-fixture", wait_until="networkidle")
            # Both the badge and the metadata row say Pending in this view.
            await page.get_by_text("Pending", exact=True).first.wait_for()
            await check_page(page, "fixture-pending", screenshot=False)
            state["phase"] = "RUNNING"
            await page.get_by_text("Running", exact=True).wait_for(timeout=10000)
            await page.get_by_text("Navigate to page", exact=True).wait_for()
            await page.get_by_text("No screenshot for this step", exact=True).wait_for()
            state["phase"] = "COMPLETED"
            await page.get_by_text(
                "Fixture agent reported pricing.", exact=True
            ).wait_for(timeout=10000)
            await page.get_by_text(
                "The agent claim was not independently verified.", exact=True
            ).wait_for()
            await check_page(page, "fixture-completed", screenshot=False)
            before = state["requests"]
            await asyncio.sleep(3)
            assert state["requests"] == before, (
                "Polling continued after terminal status"
            )
            state["phase"] = "FAILED"
            await page.reload(wait_until="networkidle")
            await page.get_by_text("Timed out", exact=True).wait_for()
            await check_page(page, "fixture-timeout", screenshot=False)

            async def missing(route):
                await route.fulfill(
                    status=404,
                    json={
                        "error": {
                            "code": "not_found",
                            "message": "Agent test not found",
                            "details": [],
                        }
                    },
                )

            await page.route("**/api/v1/agent-tests/ui-missing**", missing)
            await page.goto(BASE + "/agent-tests/ui-missing", wait_until="networkidle")
            await page.get_by_text("Agent test not found", exact=True).wait_for()
            await check_page(page, "fixture-missing", screenshot=False)
            available = {"yes": False}

            async def projects(route):
                if available["yes"]:
                    await route.fulfill(json=[])
                else:
                    await route.fulfill(
                        status=503,
                        json={
                            "error": {
                                "message": "Service temporarily unavailable",
                                "details": [],
                            }
                        },
                    )

            await page.route("**/api/v1/projects?*", projects)
            await page.route("**/api/v1/scans?*", lambda route: route.fulfill(json=[]))
            await page.goto(BASE + "/projects", wait_until="networkidle")
            await page.get_by_text(
                "Service temporarily unavailable", exact=True
            ).wait_for()
            available["yes"] = True
            await page.get_by_role("button", name="Try again").click()
            await page.get_by_text(
                "Start with your first website", exact=True
            ).wait_for()
            await check_page(page, "fixture-empty", screenshot=False)
            await page.unroute("**/api/v1/projects?*")
            await page.goto(BASE, wait_until="networkidle")
            await page.get_by_label("Website URL", exact=True).first.fill(
                "http://localhost"
            )
            await page.get_by_role(
                "button", name="Scan Website", exact=True
            ).first.click()
            await page.get_by_text(
                "Local and metadata service hostnames are not supported", exact=False
            ).wait_for()
            print(
                "PASS isolated pending/running/completed/timeout/missing/empty states, API retry, invalid URL, missing screenshots and terminal polling.",
                flush=True,
            )
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
