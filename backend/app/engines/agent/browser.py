"""Read-only Playwright tools with a fail-closed, validated fetch gateway.

Chromium is configured with a rejecting proxy (including loopback), no direct DNS,
QUIC or non-proxied WebRTC UDP. All permitted HTTP is fulfilled by Python's pinned
transport. Browser cookies/authorization headers never enter the gateway or model.
"""

import asyncio
import json
import re
import secrets
from pathlib import Path
from urllib.parse import parse_qsl, urljoin, urlsplit

import httpx
from playwright.async_api import Error as BrowserError
from playwright.async_api import async_playwright

from app.core.config import Settings
from app.engines.agent.actions import AgentAction
from app.engines.agent.privacy import public_url, redact, sanitize
from app.engines.crawling.crawler import WebsiteCrawler
from app.engines.crawling.transport import Fetcher
from app.engines.crawling.urls import URLValidator

DANGEROUS = re.compile(
    r"\b(submit|purchase|pay|checkout|buy|delete|remove|logout|sign.?out|create account|register|confirm|send|book now|log.?in|sign.?in)\b",
    re.IGNORECASE,
)
SENSITIVE = re.compile(
    r"password|secret|token|api.?key|credit|card|email|phone|address|name|captcha|one.?time|otp",
    re.IGNORECASE,
)
CSP = (
    "default-src 'self' data:; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; font-src 'self' data:; connect-src 'none'; worker-src 'none'; "
    "frame-src 'none'; object-src 'none'; form-action 'none'; base-uri 'self'"
)


class AgentScope:
    def __init__(self, starting_url: str, domains: list[str]):
        self.start = URLValidator.normalize(starting_url)
        self.hosts = {urlsplit(self.start).hostname}
        for domain in domains:
            normalized = URLValidator.normalize("https://" + domain)
            parts = urlsplit(normalized)
            if parts.path != "/" or parts.query or parts.hostname != domain.lower().rstrip("."):
                raise ValueError("Authorized domains must be plain hostnames")
            self.hosts.add(parts.hostname)

    def accept(self, url: str, base: str | None = None):
        target = URLValidator.normalize(urljoin(base or self.start, url))
        if urlsplit(target).hostname not in self.hosts:
            raise ValueError("Destination domain is not authorized")
        target = URLValidator(target).accept(target)
        if DANGEROUS.search(urlsplit(target).path.replace("-", " ").replace("_", " ")):
            raise ValueError("State-changing destination blocked")
        for key, value in parse_qsl(urlsplit(target).query):
            if (
                SENSITIVE.search(key)
                or DANGEROUS.search(value)
                or key.lower() in ("action", "cmd", "method")
            ):
                raise ValueError("Unsafe navigation query blocked")
        return target


class BrowserSession:
    def __init__(
        self,
        starting_url: str,
        domains: list[str],
        settings: Settings,
        test_id: str,
        transport=None,
    ):
        self.settings, self.test_id = settings, test_id
        self.scope = AgentScope(starting_url, domains)
        self.fetcher = Fetcher(self.scope, settings, transport)
        self.robots = WebsiteCrawler(starting_url, settings, self.fetcher)
        self.fetcher.permit = self.robots.permitted
        self.elements = {}
        self.element_info = {}
        self.requests = 0
        self.blocked_requests = 0
        self.navigation_attempts = 0
        self.playwright = self.browser = self.context = self.page = self.proxy = None
        self.closed = False

    async def start(self):
        async def deny(reader, writer):
            try:
                await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 1)
                writer.write(
                    b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
                )
                await writer.drain()
            except (TimeoutError, OSError, asyncio.IncompleteReadError, asyncio.LimitOverrunError):
                pass
            finally:
                writer.close()
                try:
                    await writer.wait_closed()
                except OSError:
                    pass

        self.proxy = await asyncio.start_server(deny, "127.0.0.1", 0, limit=8192)
        port = self.proxy.sockets[0].getsockname()[1]
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            executable_path=self.settings.agent_browser_executable,
            proxy={"server": f"http://127.0.0.1:{port}", "bypass": "<-loopback>"},
            args=[
                "--proxy-bypass-list=<-loopback>",
                "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE localhost",
                "--disable-quic",
                "--dns-prefetch-disable",
                "--disable-background-networking",
                "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
            ],
        )
        self.context = await self.browser.new_context(
            accept_downloads=False,
            service_workers="block",
            viewport={"width": 1280, "height": 800},
            permissions=[],
            user_agent=self.settings.crawl_user_agent,
        )
        await self.context.route("**/*", self._route)
        await self.context.route_web_socket("**/*", lambda ws: ws.close())
        await self.context.add_init_script("""(() => {
          for (const name of ['RTCPeerConnection','webkitRTCPeerConnection','WebTransport','Worker','SharedWorker']) {
            Object.defineProperty(globalThis, name, {value: undefined, configurable:false});
          }
          document.addEventListener('submit', event => {event.preventDefault(); event.stopImmediatePropagation();}, true);
          HTMLFormElement.prototype.submit = function(){throw new Error('Read-only agent');};
          HTMLFormElement.prototype.requestSubmit = function(){throw new Error('Read-only agent');};
          navigator.sendBeacon = () => false;
        })();""")
        self.page = await self.context.new_page()
        self.page.set_default_timeout(5000)
        self.page.on("dialog", lambda dialog: dialog.dismiss())
        self.page.on("download", lambda download: download.cancel())
        self.page.on("filechooser", lambda chooser: chooser.set_files([]))
        self.context.on("page", lambda page: page.close() if page != self.page else None)

    async def _route(self, route):
        request = route.request
        self.requests += 1
        try:
            if self.requests > self.settings.agent_request_limit or request.method != "GET":
                raise ValueError("Request method or budget denied")
            target = self.scope.accept(request.url)
            if request.resource_type == "document" and request.frame != self.page.main_frame:
                raise ValueError("Popups and child frames are not permitted")
            redirects = 0
            previous = request.redirected_from
            while previous:
                redirects += 1
                previous = previous.redirected_from
            if redirects > self.settings.agent_max_redirects:
                raise ValueError("Navigation redirect limit exceeded")
            response = await self.fetcher.get(
                target, self.settings.crawl_html_bytes, follow_redirects=False
            )
            if response.status in (401, 403, 429):
                raise ValueError("Authentication or anti-bot restriction; do not bypass")
            headers = response.headers or {}
            if "attachment" in headers.get("content-disposition", "").lower():
                raise ValueError("Download denied")
            # Do not forward Set-Cookie, authentication, transport encoding or browser hints.
            safe_headers = {
                key: headers[key] for key in ("content-type", "location") if key in headers
            }
            safe_headers["content-security-policy"] = CSP
            await route.fulfill(status=response.status, headers=safe_headers, body=response.body)
        except (ValueError, OSError, TimeoutError, BrowserError, httpx.HTTPError):
            self.blocked_requests += 1
            await route.abort("blockedbyclient")

    async def navigate(self, url):
        self.navigation_attempts += 1
        target = self.scope.accept(
            url, self.page.url if self.page.url != "about:blank" else self.scope.start
        )
        await self.page.goto(target, wait_until="domcontentloaded", timeout=15000)
        self.scope.accept(self.page.url)

    async def observe(self):
        self.scope.accept(self.page.url)
        for handle in self.elements.values():
            await handle.dispose()
        self.elements, self.element_info = {}, {}
        prefix = secrets.token_hex(4)
        items = []
        handles = await self.page.locator(
            "a[href],button,input,select,textarea,[role=button],[role=tab],summary"
        ).element_handles()
        for handle in handles[:400]:
            if not await handle.is_visible():
                await handle.dispose()
                continue
            info = await handle.evaluate(r"""e => ({tag:e.tagName.toLowerCase(), role:e.getAttribute('role') || ({A:'link',BUTTON:'button',INPUT:e.type==='search'?'searchbox':'textbox',SELECT:'combobox',TEXTAREA:'textbox',SUMMARY:'button'}[e.tagName] || null),
              name:(e.getAttribute('aria-label') || (e.getAttribute('aria-labelledby') || '').split(/\s+/).map(id=>document.getElementById(id)?.textContent || '').join(' ').trim() || (e.labels ? [...e.labels].map(l=>l.innerText).join(' ') : '') || e.innerText || e.getAttribute('placeholder') || '').slice(0,200),
              type:e.getAttribute('type') || (e.tagName==='BUTTON'?'submit':''),
              href:e.tagName==='A'?e.href:null, field:e.getAttribute('name') || '',
              required:!!e.required || e.getAttribute('aria-required')==='true', form:!!e.form, disabled:!!e.disabled || e.getAttribute('aria-disabled')==='true',
              expanded:e.getAttribute('aria-expanded'),
              options:e.tagName==='SELECT'?[...e.options].slice(0,30).map(o=>({value:o.value,label:o.label})):null})""")
            key = f"{prefix}:{len(items) + 1}"
            self.elements[key] = handle
            self.element_info[key] = info
            visible = {
                k: redact(v, 200) if isinstance(v, str) else v
                for k, v in info.items()
                if k not in ("field", "href")
            }
            if info["href"]:
                visible["href"] = public_url(info["href"])
            visible["element_id"] = key
            items.append(sanitize(visible))
            if len(items) >= self.settings.agent_max_elements:
                break
        for handle in handles:
            if handle not in self.elements.values():
                await handle.dispose()
        # No values, cookies, storage, hidden text, DOM HTML or request headers.
        headings = []
        for heading in await self.page.locator("h1,h2,h3").element_handles():
            if len(headings) < 15 and await heading.is_visible():
                headings.append(await heading.inner_text())
            await heading.dispose()
        text = await self.page.locator("body").inner_text(timeout=5000)
        observation = {
            "url": public_url(self.page.url),
            "title": redact(await self.page.title(), 200),
            "headings": [redact(h, 200) for h in headings[:15]],
            "elements": items,
            "visible_text": redact(text, 3500),
        }
        while (
            len(json.dumps(observation)) > self.settings.agent_observation_chars
            and observation["elements"]
        ):
            removed = observation["elements"].pop()
            key = removed["element_id"]
            await self.elements.pop(key).dispose()
            self.element_info.pop(key)
        if len(json.dumps(observation)) > self.settings.agent_observation_chars:
            observation["visible_text"] = observation["visible_text"][:300]
            observation["headings"] = observation["headings"][:3]
        if re.search(
            r"verify you are human|captcha|access denied|checking your browser",
            text[:4000],
            re.IGNORECASE,
        ):
            raise ValueError(
                "Authentication, CAPTCHA or anti-bot page encountered; execution stopped"
            )
        return observation

    async def execute(self, action: AgentAction):
        if action.action in ("click", "fill", "select_option"):
            if action.element_id not in self.elements:
                raise ValueError("Element ID is not from the latest observation")
            element = self.elements[action.element_id]
            info = self.element_info[action.element_id]
            if info["disabled"] or not await element.is_visible():
                raise ValueError("Element is no longer available")
            if action.action == "click":
                if info["tag"] == "a":
                    if not info["href"]:
                        raise ValueError("Link has no destination")
                    self.scope.accept(info["href"])
                    self.navigation_attempts += 1
                elif info["tag"] not in ("button", "summary") and info["role"] not in (
                    "button",
                    "tab",
                ):
                    raise ValueError("Only navigation or non-submitting controls may be clicked")
                if (
                    info["tag"] == "button"
                    and info["form"]
                    and info["type"].lower() in ("submit", "reset")
                ) or DANGEROUS.search(info["name"]):
                    raise ValueError("Submitting or state-changing controls are blocked")
                await element.click(timeout=5000)
            elif action.action == "fill":
                if (
                    info["tag"] != "input"
                    or info["type"] not in ("text", "search", "")
                    or SENSITIVE.search(info["name"] + info["field"])
                ):
                    raise ValueError("Only non-sensitive text/search inputs may be filled")
                if not re.search(r"search|filter", info["name"] + info["field"], re.IGNORECASE):
                    raise ValueError("Form entry is disabled except search/filter inspection")
                await element.fill(action.value)
            else:
                if info["tag"] != "select" or SENSITIVE.search(info["name"] + info["field"]):
                    raise ValueError("Dropdown is not permitted")
                await element.select_option(value=action.value)
        elif action.action == "navigate":
            await self.navigate(action.url)
        elif action.action == "scroll":
            await self.page.mouse.wheel(0, 600 if action.direction == "down" else -600)
        elif action.action == "go_back":
            self.navigation_attempts += 1
            await self.page.go_back(wait_until="domcontentloaded", timeout=10000)
        elif action.action == "get_page_snapshot":
            return {"snapshot": await self.observe()}
        elif action.action == "finish":
            return {"agent_declared_result": redact(action.result), "independently_verified": False}
        self.scope.accept(self.page.url)
        return {"message": "Action executed", "url": public_url(self.page.url)}

    async def screenshot(self, step: int):
        if not self.settings.agent_screenshots:
            return None
        directory = Path(self.settings.agent_screenshot_dir) / self.test_id
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{step}.png"
        # Inputs are masked; screenshots are local evidence and never sent to the LLM.
        await self.page.screenshot(
            path=str(path),
            full_page=False,
            mask=[self.page.locator("input,textarea,[contenteditable=true]")],
        )
        return str(path)

    async def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            if self.context:
                await self.context.close()
        finally:
            try:
                if self.browser:
                    await self.browser.close()
            finally:
                try:
                    if self.playwright:
                        await self.playwright.stop()
                finally:
                    await self.fetcher.close()
                    if self.proxy:
                        self.proxy.close()
                        await self.proxy.wait_closed()
