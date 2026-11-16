"""Isolated frontend state fixtures; every API response is mocked in the browser and no
fixture data is written to the backend.

Covers: an address the API refuses, missing and failing reports with retry, a locked
report (free fixes in the findings, prompt tabs, the counted offer), the
customer-release redirects, and the owner dashboard (sign-in, rejected token, first
site, job lifecycle with polling that stops, and a fully populated overview).
"""

import asyncio

from playwright.async_api import async_playwright
from verify_free_flow import report
from verify_ui import BASE, check_page

TOKEN = "fixture-token"


def error(status, message, code="http_error"):
    return {
        "status": status,
        "json": {"error": {"code": code, "message": message, "details": []}},
    }


def overview(with_data):
    qa = {
        "batch_id": "fixture",
        "created_at": "2026-11-15T09:12:00Z",
        "original": {"runs": 2, "passed": 1, "failed": 1, "errors": 0, "eligible": 2,
                     "tokens": 90000, "steps": 30, "duration_ms": 120000},
        "variant": {"runs": 2, "passed": 2, "failed": 0, "errors": 0, "eligible": 2,
                    "tokens": 20000, "steps": 8, "duration_ms": 30000},
        "tasks": [
            {"task": "price", "prompt": "What does the Trail Runner cost?", "original": "PASSED",
             "variant": "PASSED", "original_steps": 12, "variant_steps": 3},
            {"task": "sizes", "prompt": "Which sizes are in stock?", "original": "FAILED",
             "variant": "PASSED", "original_steps": 18, "variant_steps": 5},
        ],
    }
    return {
        "site": {"host": "store.fixture", "name": "Fixture Store", "routing_enabled": True},
        "window_days": 7,
        "variant": {"version": 2, "published_at": "2026-11-14T10:00:00Z", "products": 9}
        if with_data else None,
        "totals": {"requests": 9, "agent_requests": 8, "crawler_requests": 1,
                   "variant_requests": 4 if with_data else 0, "sessions": 3,
                   "unlabeled_sessions": 0 if with_data else 3},
        "agents": [
            {"agent": "ChatGPT-User", "kind": "agent", "requests": 8, "variant_requests": 4,
             "errors": 0, "sessions": 3, "last_seen": "2026-11-15T09:00:00Z"},
            {"agent": "Googlebot", "kind": "crawler", "requests": 1, "variant_requests": 0,
             "errors": 0, "sessions": 0, "last_seen": "2026-11-15T09:00:00Z"},
        ],
        "tasks": [{"task": "Find sizes in stock", "sessions": 3, "succeeded": 1, "failed": 2,
                   "unknown": 0}] if with_data else [],
        "failures": [{"task": "Find sizes in stock", "failed_step": "size picker has no labels",
                      "sessions": 2, "agents": ["ChatGPT-User"],
                      "explanation": "Size buttons had no accessible names.",
                      "suggested_fix": "Label each size option."}] if with_data else [],
        "qa": qa if with_data else None,
    }


def job(status, detail=None):
    return {"id": "job-1", "kind": "build_variant", "status": status, "detail": detail,
            "result": None, "created_at": "2026-11-15T09:00:00Z",
            "started_at": None if status == "PENDING" else "2026-11-15T09:00:02Z",
            "finished_at": "2026-11-15T09:00:09Z" if status in ("FAILED", "SUCCEEDED") else None}


async def fulfill(route, spec):
    if "status" in spec:
        await route.fulfill(status=spec["status"], json=spec["json"])
    else:
        await route.fulfill(json=spec)


async def landing_and_reports(page):
    await page.goto(BASE, wait_until="networkidle")
    await page.route(
        "**/api/v1/verification/status**",
        lambda route: fulfill(
            route, error(422, "Local and metadata service hostnames are not supported",
                         "invalid_crawl_scope")),
    )
    form = page.locator("form.website-entry").first
    await form.get_by_label("Website URL").fill("http://localhost")
    await form.get_by_role("button", name="Scan Website").click()
    dialog = page.get_by_role("dialog")
    await dialog.get_by_role("heading", name="We can’t scan this address.").wait_for()
    await dialog.get_by_text("Local and metadata service hostnames are not supported",
                             exact=False).wait_for()
    assert not await dialog.get_by_label("Your email").count(), "No email form for refused URLs"
    await check_page(page, "refused-address", screenshot=False)
    await dialog.get_by_role("button", name="Change the address").click()
    await dialog.wait_for(state="hidden")

    await page.route("**/api/v1/free-reports/missing**",
                     lambda route: fulfill(route, error(404, "Report not found", "not_found")))
    await page.goto(BASE + "/free-reports/missing", wait_until="networkidle")
    await page.get_by_role("heading", name="This report link has expired").wait_for()
    await check_page(page, "report-expired", screenshot=False)

    state = {"down": True}

    async def flaky(route):
        if state["down"]:
            await fulfill(route, error(503, "Database operation unavailable"))
        else:
            await route.fulfill(json=report("COMPLETED"))

    await page.route("**/api/v1/free-reports/flaky**", flaky)
    await page.goto(BASE + "/free-reports/flaky", wait_until="networkidle")
    await page.get_by_text("Database operation unavailable", exact=True).wait_for()
    await check_page(page, "report-unavailable", screenshot=False)
    state["down"] = False
    await page.get_by_role("button", name="Try again").click()
    await page.get_by_text("Preliminary static readiness", exact=True).wait_for()

    # Before purchase: free fixes fold into the findings; the offer counts what it adds.
    locked = {**report("COMPLETED"), "full_report_unlocked": False}
    locked["insights"] = locked["insights"] + [{
        "category": "Content understanding", "severity": "MEDIUM",
        "title": "JSON-LD could not be validated",
        "description": "JSON syntax or schema.org context checks failed.",
        "evidence_url": None, "evidence_summary": None,
        "recommendation": "Use valid JSON with an @context and @type.",
    }]
    prompts = {key: f"{key} prompt for the size picker" for key in
               ("coding_assistant", "general_llm", "developer_ticket")}
    preview = {
        "fixes": [{
            "key": "fix-1", "title": "Controls lack accessible names", "category": "Actionability",
            "severity": "HIGH", "url": "https://example.com/trail-runner",
            "evidence": "Example inspected element: <button type=button role=>",
            "recommendation": "Give the control a clear accessible name.",
            "template_version": "fix-prompts-v1.1", "prompts": prompts, "status": "OPEN",
        }],
        "assets": [], "remaining_fixes": 2, "remaining_assets": 1, "truncated": False,
    }

    async def locked_report(route):
        await route.fulfill(json=preview if "fix-preview" in route.request.url else locked)

    await page.route("**/api/v1/free-reports/locked**", locked_report)
    await page.goto(BASE + "/free-reports/locked", wait_until="networkidle")
    await page.get_by_role("heading", name="What to fix first").wait_for()
    await page.get_by_text("One of them comes with a complete fix, free.", exact=False).wait_for()
    await page.get_by_text("Free fix", exact=True).wait_for()
    await page.get_by_role("tab", name="Dev ticket").click()
    assert await page.get_by_role("tab", name="Dev ticket").get_attribute("aria-selected") == "true"
    await page.get_by_role("heading", name="Fix the other 1 finding, then prove it.").wait_for()
    await page.get_by_text("2 more ready prompts and 1 asset draft", exact=True).wait_for()
    await page.get_by_role("button", name="Unlock the Fix Kit").wait_for()
    await page.locator("summary").filter(has_text="JSON-LD could not be validated").click()
    await page.get_by_role("link", name="See what’s included").wait_for()
    await check_page(page, "report-locked", screenshot=False)

    await page.goto(BASE + "/agent-tests/any", wait_until="networkidle")
    await page.get_by_label("Real AI agent testing, coming Christmas 2026").first.wait_for()
    await check_page(page, "agent-tests-coming-soon", screenshot=False)
    await page.goto(BASE + "/projects")
    await page.wait_for_url(BASE.rstrip("/") + "/")  # The workspace is not public.


async def dashboard(browser):
    context = await browser.new_context(viewport={"width": 1440, "height": 1000},
                                        reduced_motion="reduce")
    page = await context.new_page()
    api = {"sites": [], "jobs": [], "overview": overview(False), "job_polls": 0, "calls": []}
    settings = {"host": "store.fixture", "name": "Fixture Store", "origin": "https://origin.fixture",
                "routing_enabled": True, "delivery_rules": None}

    async def route(route):
        request = route.request
        url = request.url.split("?")[0]
        if request.headers.get("authorization") != f"Bearer {TOKEN}":
            return await fulfill(route, error(401, "A valid dashboard token is required"))
        if url.endswith("/dashboard/sites") and request.method == "POST":
            body = request.post_data_json
            if not body["origin"].startswith("https://"):
                return await fulfill(route, error(422, "Origins must be public"))
            site = {"host": body["host"], "name": body["name"], "routing_enabled": True}
            api["sites"].append(site)
            return await route.fulfill(status=201, json=site)
        if url.endswith("/dashboard/sites"):
            return await route.fulfill(json={"sites": api["sites"]})
        if url.endswith("/settings"):
            return await route.fulfill(json=settings)
        if url.endswith("/delivery"):
            api["calls"].append((request.method, "delivery"))
            rules = request.post_data_json if request.method == "PUT" else None
            if rules and rules["pin_pattern"] == "([0-9":
                return await fulfill(route, error(422, "PIN pattern is not a valid regular expression",
                                                  "validation_error"))
            settings["delivery_rules"] = rules
            return await route.fulfill(json=settings)
        if url.endswith("/dashboard/sites/store.fixture") and request.method == "PATCH":
            api["calls"].append(("PATCH", request.post_data_json))
            settings.update(request.post_data_json)
            return await route.fulfill(json=settings)
        if url.endswith("/dashboard/sites/store.fixture") and request.method == "DELETE":
            api["calls"].append(("DELETE", "site"))
            api["sites"].clear()
            return await route.fulfill(status=204, body="")
        if url.endswith("/overview"):
            return await route.fulfill(json=api["overview"])
        if url.endswith("/variants"):
            return await route.fulfill(json={"variants": []})
        if url.endswith("/jobs") and request.method == "POST":
            api["jobs"] = [job("PENDING")]
            return await route.fulfill(status=202, json=api["jobs"][0])
        if url.endswith("/jobs"):
            api["job_polls"] += 1
            return await route.fulfill(json={"jobs": api["jobs"]})
        return await fulfill(route, error(404, "Not found"))

    await page.route("**/api/v1/dashboard/**", route)
    await page.goto(BASE + "/dashboard", wait_until="networkidle")
    await page.get_by_role("heading", name="Sign in to your dashboard").wait_for()
    await check_page(page, "dashboard-sign-in", screenshot=False)
    await page.get_by_label("Dashboard token").fill("wrong")
    await page.get_by_role("button", name="Open dashboard").click()
    await page.get_by_text("A valid dashboard token is required", exact=True).wait_for()
    await page.get_by_label("Dashboard token").fill(TOKEN)
    await page.get_by_role("button", name="Open dashboard").click()

    await page.get_by_role("heading", name="Add your first site").wait_for()
    await check_page(page, "dashboard-first-site", screenshot=False)
    await page.get_by_label("Site name").fill("Fixture Store")
    await page.get_by_label("Public host").fill("store.fixture")
    await page.get_by_label("Origin").fill("http://10.0.0.5")
    await page.get_by_role("button", name="Add site").last.click()
    await page.get_by_text("Origins must be public", exact=True).wait_for()
    await page.get_by_label("Origin").fill("https://origin.fixture")
    await page.get_by_role("button", name="Add site").last.click()
    await page.get_by_role("heading", name="Fixture Store").wait_for()
    await page.get_by_text("No published agent lane yet", exact=True).wait_for()
    await page.get_by_text("No labeled sessions yet", exact=True).wait_for()
    await page.get_by_text("No QA batch yet", exact=True).wait_for()
    assert await page.get_by_role("button", name="Run agent QA").is_disabled(), (
        "QA needs a published agent lane"
    )
    await check_page(page, "dashboard-empty", screenshot=False)

    await page.get_by_role("button", name="Build agent lane").click()
    await page.get_by_text("Queued · waiting for the jobs worker", exact=True).wait_for()
    api["jobs"] = [job("RUNNING")]
    await page.get_by_text("Running since", exact=False).wait_for(timeout=10000)
    api["jobs"] = [job("FAILED", "InferenceError: Configure GEMINI_API_KEY")]
    await page.get_by_text("Configure GEMINI_API_KEY", exact=False).wait_for(timeout=10000)
    await page.get_by_role("button", name="Build agent lane").wait_for()
    before = api["job_polls"]
    await asyncio.sleep(5)
    assert api["job_polls"] == before, "Job polling continued after a terminal status"
    await check_page(page, "dashboard-job-failed", screenshot=False)

    api["overview"] = overview(True)
    for theme, width in (("light", 1440), ("dark", 1440), ("light", 390)):
        await page.set_viewport_size({"width": width, "height": 1000})
        await page.evaluate(f"localStorage.setItem('ar-theme', '{theme}')")
        await page.reload(wait_until="networkidle")
        applied = await page.evaluate("document.documentElement.dataset.theme")
        assert applied == theme, (theme, applied)
        await page.get_by_text("Agent lane v2 live · 9 products", exact=True).wait_for()
        await page.get_by_text("4.5× fewer tokens", exact=True).wait_for()
        await page.get_by_text("Suggestions, not applied automatically", exact=True).wait_for()
        await check_page(page, f"dashboard-full-{theme}-{width}", screenshot=False)

    await page.set_viewport_size({"width": 1440, "height": 1000})
    await page.get_by_role("button", name="Settings").click()
    panel = page.get_by_role("region", name="Site settings")
    await panel.get_by_label("Origin").wait_for()
    assert await panel.get_by_label("Origin").input_value() == "https://origin.fixture"
    await check_page(page, "dashboard-settings", screenshot=False)
    toggle = panel.get_by_label("Serve the agent lane to AI agents")
    # The checkbox reflects the saved state, so it flips only after the server confirms.
    await toggle.click()
    await panel.get_by_text("Routing paused. Everyone gets your original site.").wait_for()
    assert not await toggle.is_checked()
    assert ("PATCH", {"routing_enabled": False}) in api["calls"]
    await panel.get_by_label("Default estimate").fill("3–5 working days")
    await panel.get_by_label("PIN code pattern").fill("([0-9")
    await panel.get_by_role("button", name="Save delivery estimates").click()
    await panel.get_by_text("PIN pattern is not a valid regular expression").wait_for()
    await panel.get_by_label("PIN code pattern").fill("^\\d{6}$")
    await panel.get_by_role("button", name="Add an area").click()
    await panel.get_by_label("PIN prefixes, row 1").fill("11, 56")
    await panel.get_by_label("Estimate, row 1").fill("2–3 working days")
    await panel.get_by_role("button", name="Save delivery estimates").click()
    await panel.get_by_text("Delivery estimates saved.").wait_for()
    assert settings["delivery_rules"]["estimates"] == [
        {"prefixes": ["11", "56"], "estimate": "2–3 working days"}
    ], settings["delivery_rules"]
    remove = panel.get_by_role("button", name="Remove site")
    assert await remove.is_disabled(), "Removal needs the typed host"
    await panel.get_by_label("Type store.fixture to confirm").fill("store.fixture")
    await remove.click()
    await page.get_by_role("heading", name="Add your first site").wait_for()
    assert ("DELETE", "site") in api["calls"]
    await context.close()


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            context = await browser.new_context(
                viewport={"width": 1440, "height": 1000}, reduced_motion="reduce"
            )
            await landing_and_reports(await context.new_page())
            await context.close()
            await dashboard(browser)
            print(
                "PASS refused address, expired/unavailable report with retry, locked report "
                "with free fixes and offer, customer-release "
                "redirects, dashboard sign-in/rejected token/first site/job lifecycle/full overview/"
                "site settings (routing, delivery rules, removal).",
                flush=True,
            )
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
