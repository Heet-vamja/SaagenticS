"""Local-only landing QA. No scans, emails, payments or model requests are made."""

import asyncio
import json
import os
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from playwright.async_api import async_playwright

BASE = os.environ.get("UI_BASE_URL", "http://localhost:13000")
OUTPUT = Path(os.environ.get("QA_OUTPUT", "/private/tmp/agentreadiness-landing"))
AXE = Path(__file__).resolve().parents[1] / "node_modules/axe-core/axe.min.js"


async def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            for theme in ("light", "dark"):
                for width in (375, 768, 1280):
                    context = await browser.new_context(
                        viewport={"width": width, "height": 1000},
                        reduced_motion="reduce",
                    )
                    await context.add_init_script(
                        f"if (!localStorage.getItem('ar-theme')) localStorage.setItem('ar-theme', '{theme}')"
                    )
                    await context.add_init_script(
                        "window.__landingCLS=0;new PerformanceObserver(list=>{for(const entry of list.getEntries())if(!entry.hadRecentInput)window.__landingCLS+=entry.value}).observe({type:'layout-shift',buffered:true})"
                    )
                    page = await context.new_page()
                    errors = []
                    page.on(
                        "pageerror",
                        lambda error, errors=errors: errors.append(str(error)),
                    )
                    await page.goto(BASE, wait_until="networkidle")
                    await page.evaluate("document.fonts.ready")
                    await page.wait_for_function(
                        "document.querySelector('[aria-label^=\"Illustrative readiness score\"] strong')?.textContent === '42'"
                    )
                    assert await page.evaluate(
                        "document.documentElement.scrollWidth <= innerWidth"
                    ), f"Overflow {width}/{theme}"
                    # Catch clipped individual controls too; overflow:clip on a root can hide problems.
                    offenders = await page.evaluate(
                        """() => [...document.querySelectorAll('main input, main button, main h1, main h2')].filter(e=>{const r=e.getBoundingClientRect();return r.width && (r.left < -1 || r.right > innerWidth+1)}).map(e=>e.textContent?.slice(0,70)||e.tagName)"""
                    )
                    assert not offenders, (width, theme, offenders)
                    cls = await page.evaluate("window.__landingCLS")
                    assert cls < 0.1, (width, theme, "layout shift", cls)
                    await page.screenshot(
                        path=str(OUTPUT / f"{width}-{theme}-hero.png"), full_page=False
                    )
                    await page.screenshot(
                        path=str(OUTPUT / f"{width}-{theme}-full.png"), full_page=True
                    )
                    preview = page.get_by_role(
                        "complementary", name="Illustrative readiness report, demo data"
                    )
                    await preview.get_by_role(
                        "button", name="What a human sees"
                    ).click()
                    assert await preview.get_by_text(
                        "Implementation guidance"
                    ).is_visible()
                    await preview.get_by_role(
                        "button", name="What an agent sees"
                    ).click()
                    assert await preview.get_by_text("<main></main>").is_visible()
                    assert (
                        await page.locator("[class*='cursor']").first.evaluate(
                            "e => getComputedStyle(e).animationName"
                        )
                        == "none"
                    )
                    await page.add_script_tag(path=str(AXE))
                    violations = await page.evaluate(
                        """async()=> (await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}})).violations.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.map(n=>n.target)}))"""
                    )
                    assert not violations, json.dumps(
                        {"width": width, "theme": theme, "violations": violations}
                    )
                    faq = page.locator('section[aria-labelledby="homepage-questions"]')
                    first_question = faq.locator("details").first
                    await first_question.locator("summary").click()
                    assert await first_question.locator("p").is_visible()
                    await first_question.locator("summary").press("Enter")
                    assert await first_question.get_attribute("open") is None
                    await page.get_by_role(
                        "button",
                        name=f"Switch to {'dark' if theme == 'light' else 'light'} theme",
                    ).click()
                    await page.reload(wait_until="networkidle")
                    expected = "dark" if theme == "light" else "light"
                    assert (
                        await page.locator("html").get_attribute("data-theme")
                        == expected
                    )
                    requested = []

                    async def verification_status(
                        route, _request, *, requested=requested
                    ):
                        requested.append(
                            parse_qs(urlsplit(route.request.url).query)["website_url"][
                                0
                            ]
                        )
                        await route.fulfill(
                            json={
                                "verified": False,
                                "domain": "example.com",
                                "development_skip_available": False,
                            }
                        )

                    await page.route("**/api/**", lambda route: route.abort())
                    await page.route(
                        "**/api/v1/verification/status**", verification_status
                    )
                    form = page.locator("#scan form")
                    await form.get_by_role("textbox", name="Website URL").fill(
                        "example.com"
                    )
                    async with page.expect_response("**/api/v1/verification/status**"):
                        await form.get_by_role("button", name="Scan Website").click()
                    assert await page.get_by_role("dialog").is_visible()
                    assert requested and set(requested) == {"https://example.com/"}, (
                        requested
                    )
                    assert not errors, errors
                    await context.close()
                    print(
                        f"PASS {width}px/{theme}: layout, contrast, CLS={cls:.3f}, view toggle, reduced motion, saved theme, domain verification entry",
                        flush=True,
                    )
            context = await browser.new_context(
                viewport={"width": 1280, "height": 1000}
            )
            page = await context.new_page()
            await page.goto(BASE, wait_until="networkidle")
            await page.wait_for_function(
                "document.querySelector('[aria-label^=\"Illustrative readiness score\"] strong')?.textContent === '42'"
            )
            await page.get_by_role("button", name="Pause demo animation").click()
            assert (
                await page.locator("[class*='cursor']").first.evaluate(
                    "e => getComputedStyle(e).animationPlayState"
                )
                == "paused"
            )
            await page.get_by_role("button", name="Resume demo animation").click()
            await context.close()
            print("PASS animated demo count-up and pause control. No external actions triggered.")
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
