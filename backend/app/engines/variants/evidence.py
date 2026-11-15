"""Collect rendered evidence from a site for catalog extraction. No model is called here.

Public origins render through the existing fail-closed `BrowserSession` (validated,
DNS-pinned fetch gateway, robots-aware, rejecting proxy). Private origins are accepted
only when `edge_allow_private_origins` is enabled for local development (the demo store
on the Docker network); they use a contained browser that permits GET requests to that
single configured origin and blocks everything else.
"""

import asyncio
import json
import re
from contextlib import asynccontextmanager, suppress
from urllib.parse import urljoin, urlsplit
from uuid import uuid4

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import async_playwright

from app.core.config import Settings
from app.engines.agent.browser import BrowserSession
from app.engines.crawling.urls import URLValidator
from app.engines.variants.contracts import Evidence, EvidenceData, EvidencePage

MAX_JSON_BYTES = 200_000
MAX_JSON_RESPONSES = 40
MAX_LINKS_PER_PAGE = 300
SKIP_PATH = re.compile(
    r"(log-?out|sign-?out|delete|remove|checkout|payment|admin|account|wp-admin)", re.IGNORECASE
)
SKIP_EXTENSION = re.compile(
    r"\.(png|jpe?g|gif|svg|webp|ico|css|js|mjs|map|pdf|zip|woff2?)$", re.IGNORECASE
)
# Many JavaScript storefronts navigate with click handlers instead of anchors, so read
# the common data attributes as well as href.
LINKS_SCRIPT = """() => {
  const values = [];
  for (const el of document.querySelectorAll('[href],[data-href],[data-go],[data-url],[data-link]')) {
    for (const name of ['href', 'data-href', 'data-go', 'data-url', 'data-link']) {
      const value = el.getAttribute(name);
      if (value) values.push(value);
    }
    if (values.length > LIMIT) break;
  }
  return values;
}""".replace("LIMIT", str(MAX_LINKS_PER_PAGE))


def origin_of(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}".lower()


def uses_dev_browser(origin: str, settings: Settings) -> bool:
    try:
        URLValidator(origin + "/").accept(origin + "/")
        return False
    except ValueError:
        if settings.edge_allow_private_origins:
            return True
        raise ValueError("This origin cannot be rendered through the validated browser gateway")


@asynccontextmanager
async def _dev_page(
    origin: str, settings: Settings, request_limit: int, user_agent: str, get_only: bool = True
):
    """Local development only: one origin, bounded request count; GET only unless a
    QA run needs the site's own same-origin forms."""
    async with async_playwright() as playwright:
        rules = settings.dev_browser_host_rules
        browser = await playwright.chromium.launch(
            headless=True,
            executable_path=settings.agent_browser_executable,
            args=[f"--host-resolver-rules={rules}"] if rules else [],
        )
        context = await browser.new_context(
            accept_downloads=False,
            service_workers="block",
            viewport={"width": 1280, "height": 800},
            user_agent=user_agent,
        )
        count = 0

        async def route(route):
            nonlocal count
            count += 1
            request = route.request
            if (
                count > request_limit
                or (get_only and request.method != "GET")
                or origin_of(request.url) != origin
            ):
                await route.abort("blockedbyclient")
            else:
                await route.continue_()

        await context.route("**/*", route)
        await context.route_web_socket("**/*", lambda ws: ws.close())
        page = await context.new_page()
        page.set_default_timeout(15000)
        page.on("dialog", lambda dialog: dialog.dismiss())

        async def navigate(url: str):
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)

        try:
            yield page, navigate
        finally:
            await context.close()
            await browser.close()


@asynccontextmanager
async def _gateway_page(
    origin: str, settings: Settings, request_limit: int, user_agent: str, get_only: bool = True
):
    # BrowserSession is always read-only (GET only, form submission blocked).
    scoped = settings.model_copy(
        update={"agent_request_limit": request_limit, "crawl_user_agent": user_agent}
    )
    session = BrowserSession(origin + "/", [], scoped, "variant-" + str(uuid4()))
    await session.start()
    try:
        yield session.page, session.navigate
    finally:
        await session.close()


def open_page(
    origin: str,
    settings: Settings,
    request_limit: int,
    user_agent: str | None = None,
    get_only: bool = True,
):
    """Context manager yielding (page, navigate) on the right browser for this origin."""
    opener = _dev_page if uses_dev_browser(origin, settings) else _gateway_page
    return opener(
        origin, settings, request_limit, user_agent or settings.crawl_user_agent, get_only
    )


def _candidate_paths(values: list[str], base: str, origin: str) -> list[str]:
    paths = []
    for value in values:
        try:
            target = urljoin(base, value.strip())
        except ValueError:
            continue
        parts = urlsplit(target)
        path = parts.path or "/"
        if (
            origin_of(target) == origin
            and not SKIP_PATH.search(path)
            and not SKIP_EXTENSION.search(path)
        ):
            paths.append(path)  # Query strings and fragments are never followed.
    return paths


async def collect_evidence(origin_url: str, settings: Settings) -> Evidence:
    origin = origin_of(origin_url)
    evidence = Evidence(origin=origin)
    request_limit = settings.variant_max_pages * 20
    queue, seen, json_seen = ["/"], {"/"}, set()
    try:
        async with asyncio.timeout(settings.variant_crawl_duration):
            async with open_page(origin, settings, request_limit) as (page, navigate):
                responses = []
                # Playwright needs a real function; it cannot wrap a builtin method.
                page.on("response", lambda response: responses.append(response))
                while queue and len(evidence.pages) < settings.variant_max_pages:
                    path = queue.pop(0)
                    responses.clear()
                    try:
                        await navigate(origin + path)
                        with suppress(PlaywrightError):
                            await page.wait_for_load_state("networkidle", timeout=8000)
                        text = await page.evaluate("document.body ? document.body.innerText : ''")
                        title = await page.title()
                        links = await page.evaluate(LINKS_SCRIPT)
                    except (PlaywrightError, ValueError, TimeoutError):
                        evidence.pages.append(EvidencePage(path, "", "", 0))
                        continue
                    evidence.pages.append(
                        EvidencePage(path, title[:300], text[: settings.variant_page_chars], 200)
                    )
                    # Copy: new responses can arrive while bodies are awaited below.
                    arrived = responses.copy()
                    for response in arrived:
                        if len(evidence.data) >= MAX_JSON_RESPONSES:
                            evidence.limited = True
                            break
                        data_path = urlsplit(response.url).path
                        if (
                            origin_of(response.url) != origin
                            or response.status != 200
                            or "json" not in (response.headers.get("content-type") or "")
                            or data_path in json_seen
                        ):
                            continue
                        try:
                            body = await response.body()
                        except PlaywrightError:
                            continue
                        if len(body) > MAX_JSON_BYTES:
                            evidence.limited = True
                            continue
                        try:
                            evidence.data.append(EvidenceData(data_path, json.loads(body)))
                            json_seen.add(data_path)
                        except (ValueError, UnicodeDecodeError):
                            continue
                    for candidate in _candidate_paths(links, page.url, origin):
                        if candidate not in seen:
                            seen.add(candidate)
                            queue.append(candidate)
                evidence.limited |= bool(queue)
    except TimeoutError:
        evidence.limited = True
    return evidence
