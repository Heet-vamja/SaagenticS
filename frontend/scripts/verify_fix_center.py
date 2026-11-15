"""Browser verification with mocked API, zero inference and no external crawl."""

import asyncio
import io
import json
import os
import zipfile

from playwright.async_api import async_playwright

from verify_free_flow import BASE, OUTPUT, REPORT_PATH, TOKEN, check_view, report


async def run():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    events, errors, submissions = [], [], []
    key_errors = []
    create_scan_gate = asyncio.Event()
    fail_next_submission = False
    polls = 0
    report_ready = False
    verified = False
    next_token = "ui-test-rescan-token"
    prompt = "Fix the observed button label. Preserve its behavior. Re-scan to confirm."

    def center(retested=False):
        return {
            "version": "customer-fixes-v1", "truncated": False,
            "fixes": [] if retested else [{
                "key": "button-fixture", "title": "Controls lack accessible names",
                "category": "Actionability", "severity": "HIGH",
                "url": "https://example.com/pricing", "evidence": "Example: <button></button>",
                "recommendation": "Give the control a descriptive accessible name.",
                "template_version": "fix-prompts-v1",
                "prompts": {variant: prompt for variant in ("coding_assistant", "general_llm", "developer_ticket")},
                "status": "FIX_APPLIED" if "FIX_APPLIED" in events else "PROMPT_COPIED" if "PROMPT_COPIED" in events else "OPEN",
            }],
            "assets": [{
                "key": "llms.txt", "filename": "llms.txt", "content": "# Example\n\n## Overview\n\n- [Example](https://example.com/): Sample description\n",
                "media_type": "text/plain", "placement": "Review and upload to /llms.txt.",
                "provenance": "Observed fixture homepage title and description.",
                "validated": True, "version": "crawl-assets-v1",
            }],
            "missing_information": ["Organization name was not observed; no organization facts were invented."],
            "comparison": {
                "available": retested, "reason": None, "confirmed": int(retested),
                "total": int(retested), "score_before": 81.3 if retested else None,
                "score_after": 85 if retested else None, "score_delta": 3.7 if retested else None,
                "results": [{"key": "button-fixture", "title": "Controls lack accessible names", "url": "https://example.com/pricing", "status": "VERIFIED_FIXED"}] if retested else [],
            },
            "events": [event for event in events if event in ("USEFUL", "NOT_USEFUL", "PRICE_INTERESTED")],
            "agent_status": "NOT_RUN", "agent_message": "No real agent task was run.",
        }

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            # Reduced motion keeps axe from sampling animations mid-fade (as in verify_landing).
            context = await browser.new_context(
                viewport={"width": 1440, "height": 1000}, reduced_motion="reduce"
            )
            theme = os.environ.get("QA_THEME")  # Optional: "light" or "dark".
            if theme:
                await context.add_init_script(f"localStorage.setItem('ar-theme', '{theme}')")
            page = await context.new_page()
            await page.context.grant_permissions(["clipboard-read", "clipboard-write"])
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("console", lambda message: key_errors.append(message.text) if "same key" in message.text else None)

            async def api_route(route):
                nonlocal polls, fail_next_submission, verified
                url = route.request.url
                if "/verification/status" in url:
                    body, status = {"verified": verified, "domain": "example.com", "email_hint": "o***@example.com"}, 200
                elif url.endswith("/verification/request"):
                    body, status = {"challenge_id": "fixture-challenge", "email_hint": "o***@example.com", "expires_in": 600}, 200
                elif url.endswith("/verification/verify"):
                    assert route.request.post_data_json == {"challenge_id": "fixture-challenge", "code": "123456"}
                    verified = True
                    body, status = {"verified": True}, 200
                elif url.endswith("/free-scans"):
                    submissions.append(route.request.post_data_json)
                    if fail_next_submission:
                        fail_next_submission = False
                        await route.fulfill(status=503, content_type="application/json", body=json.dumps({"error": {"message": "Queue is busy. Please retry."}}))
                        return
                    await create_scan_gate.wait()
                    body = {"report_path": REPORT_PATH, "status": "PENDING", "expires_at": "2026-12-01T00:00:00Z"}
                    status = 201
                elif "/fix-center" in url:
                    body, status = center(next_token in url), 200
                elif url.endswith("/fix-events"):
                    events.append(route.request.post_data_json["event_type"])
                    body, status = {"recorded": True}, 200
                elif url.endswith("/rescan"):
                    body, status = {"report_path": f"/free-reports/{next_token}", "status": "PENDING", "expires_at": "2026-12-01T00:00:00Z"}, 201
                elif "/assets/" in url or "/fix-pack.zip" in url:
                    if "/fix-pack.zip" in url:
                        stream = io.BytesIO()
                        with zipfile.ZipFile(stream, "w") as archive:
                            archive.writestr("fix-everything-01.md", prompt)
                        content, media = stream.getvalue(), "application/zip"
                    else:
                        content, media = center()["assets"][0]["content"].encode(), "text/plain"
                    await route.fulfill(status=200, content_type=media, body=content, headers={"Content-Disposition": 'attachment; filename="fixture-download"'})
                    return
                else:
                    polls += 1
                    state = "COMPLETED" if next_token in url or report_ready else "PENDING"
                    body, status = report(state), 200
                await route.fulfill(status=status, content_type="application/json", body=json.dumps(body))

            await page.route("**/api/v1/**", api_route)
            await page.goto(BASE, wait_until="networkidle")
            await page.get_by_role("heading", level=1).wait_for()
            await check_view(page, "homepage-desktop")
            for width, label in [(768, "tablet"), (390, "mobile"), (320, "small-mobile")]:
                await page.set_viewport_size({"width": width, "height": 900})
                await check_view(page, f"homepage-{label}")
                assert await page.locator(".hero-title-row").count() == 3
            await page.set_viewport_size({"width": 1440, "height": 1000})
            hero_form = page.locator("form.website-entry").first
            await hero_form.get_by_label("Website URL").fill("example.com")
            await hero_form.get_by_role("button", name="Scan Website").click()
            # Customer release: a mailbox code is required before the first scan.
            dialog = page.get_by_role("dialog")
            await dialog.get_by_role("heading", name="Confirm your email to start.").wait_for()
            await check_view(page, "verify-email")
            await dialog.get_by_label("Your email").fill("owner@example.com")
            await dialog.get_by_role("button", name="Send verification code").click()
            await dialog.get_by_label("Verification code").fill("123456")
            await check_view(page, "verify-code")
            await dialog.get_by_role("button", name="Verify and scan").click()
            await page.get_by_role("heading", name="Preparing your report").wait_for(timeout=3000)
            await page.get_by_text("Creating your report link…", exact=True).wait_for()
            assert not page.url.endswith(REPORT_PATH)
            await hero_form.evaluate("form => form.requestSubmit()")
            assert len(submissions) == 1
            await check_view(page, "scan-handoff")
            create_scan_gate.set()
            await page.wait_for_url(f"**{REPORT_PATH}")
            await page.get_by_text("We’re checking your website").wait_for()
            report_ready = True
            await page.get_by_text("Preliminary static readiness", exact=True).wait_for(timeout=8000)
            await page.get_by_role("heading", name="Your Fix Center").wait_for()
            assert submissions == [{"website_url": "https://example.com/"}]
            # Agent task testing is not part of the customer release; the report says so.
            await page.get_by_label("Real AI agent testing, coming Christmas 2026").wait_for()
            ring = page.get_by_role("img", name="Readiness score 81 out of 100")
            ring_top = await ring.evaluate("element => element.getBoundingClientRect().top + window.scrollY")
            await page.get_by_text("How this score works", exact=True).click()
            expanded_top = await ring.evaluate("element => element.getBoundingClientRect().top + window.scrollY")
            assert abs(ring_top - expanded_top) < 1, (ring_top, expanded_top)
            await page.get_by_text("How this score works", exact=True).click()
            await page.get_by_text("What was checked", exact=True).click()
            duplicate_rows = page.locator("details.group\\/check").filter(has_text="No known bot challenge signal was observed")
            assert await duplicate_rows.count() == 2
            await duplicate_rows.first.locator("summary").click()
            assert await duplicate_rows.first.get_attribute("open") is not None
            assert await duplicate_rows.last.get_attribute("open") is None
            await page.get_by_text("What was checked", exact=True).click()
            fix = page.locator("details").filter(has_text="Preview prompt").first
            await fix.locator("summary").first.click()
            await fix.get_by_role("button", name="Copy fix prompt").click()
            await page.get_by_role("button", name="Prompt copied", exact=True).wait_for()
            assert await page.evaluate("navigator.clipboard.readText()") == prompt
            await fix.get_by_role("button", name="I’ve applied this fix").click()
            await page.get_by_text("Applied · awaiting rescan", exact=True).wait_for()
            await page.get_by_role("button", name="Yes", exact=True).click()
            await page.get_by_text("Thanks — your feedback was saved.").wait_for()
            async with page.expect_download() as download_info:
                await page.get_by_role("button", name="Download fix pack").click()
            assert (await download_info.value).suggested_filename == "agentlane-fix-pack.zip"
            await check_view(page, "fix-center-desktop")
            for width, name in [(390, "mobile"), (768, "tablet"), (320, "small-mobile")]:
                await page.set_viewport_size({"width": width, "height": 900})
                await check_view(page, f"fix-center-{name}")
            await page.get_by_role("button", name="Re-scan to verify").click()
            await page.wait_for_url(f"**/free-reports/{next_token}")
            await page.get_by_role("heading", name="1 of 1 previous issues confirmed fixed").wait_for()
            await check_view(page, "fix-center-rescan")
            await page.goto(BASE, wait_until="networkidle")
            fail_next_submission = True
            retry_form = page.locator("form.website-entry").last
            await retry_form.get_by_label("Website URL").fill("example.com")
            await retry_form.get_by_role("button", name="Scan Website").click()
            await page.get_by_role("button", name="Continue to scan").click()
            await page.get_by_text("Queue is busy. Please retry.").wait_for()
            assert await retry_form.get_by_label("Website URL").is_enabled()
            assert not await page.get_by_role("heading", name="Preparing your report").count()
            await retry_form.get_by_role("button", name="Scan Website").click()
            await page.get_by_role("button", name="Continue to scan").click()
            await page.wait_for_url(f"**{REPORT_PATH}")
            await page.get_by_role("heading", name="Your Fix Center").wait_for()
            assert len(submissions) == 3
            assert not errors, errors
            assert not key_errors, key_errors
            assert {"PROMPT_COPIED", "FIX_APPLIED", "USEFUL"} <= set(events)
            print("PASS URL submission → static report → copy/apply → fix pack → feedback → linked rescan; all API/model responses mocked.", flush=True)
        except Exception:
            await page.screenshot(path=str(OUTPUT / "flow-error.png"), full_page=True)
            print({"url": page.url, "page_errors": errors, "key_errors": key_errors, "submissions": len(submissions)}, flush=True)
            raise
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(run())
