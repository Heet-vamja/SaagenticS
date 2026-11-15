"""Bounded breadth-first discovery; callbacks persist progress after every page."""

import asyncio
from collections import deque
from copy import deepcopy
from urllib.parse import urlsplit, urlunsplit
from xml.etree.ElementTree import ParseError

import httpx
from defusedxml.common import DefusedXmlException

from app.core.config import Settings
from app.engines.agent.privacy import public_url
from app.engines.crawling.parsers import PageParser, RobotsHandler, SitemapParser
from app.engines.crawling.transport import Fetcher
from app.engines.crawling.urls import URLValidator


class WebsiteCrawler:
    def __init__(self, url: str, settings: Settings, fetcher=None):
        self.settings = settings
        self.scope = URLValidator(url, settings.crawl_allow_subdomains)
        self.fetcher = fetcher or Fetcher(self.scope, settings)
        self.robots = {}
        self.robots_locks = {}
        self.warnings = []
        self.sitemap_diagnostics = []
        self.llms = {}
        self.resource_candidates = {}
        self.diagnostics = {
            "resources": [],
            "resources_limited": False,
            "html_inspected": False,
            "missing_path": {"result": "UNKNOWN", "detail": "Not attempted"},
            "ai_catalog": {"result": "UNKNOWN", "detail": "Not attempted"},
            "mcp_server_card": {"result": "UNKNOWN", "detail": "Not attempted"},
        }
        self.discovered = set()
        self.crawled = 0
        self.failed = 0

    def warn(self, message):
        if len(self.warnings) < 50:
            self.warnings.append(message)

    async def robots_for(self, url):
        parts = urlsplit(url)
        origin = urlunsplit((parts.scheme, parts.netloc, "", "", ""))
        async with self.robots_locks.setdefault(origin, asyncio.Lock()):
            if origin in self.robots:
                return self.robots[origin]
            handler = RobotsHandler(self.settings.crawl_user_agent)
            try:
                response = await self.fetcher.get(
                    origin + "/robots.txt", self.settings.crawl_sitemap_bytes, robots=False
                )
                # A same-scheme redirect between the bare hostname and its
                # canonical www alias is within the configured site scope.
                final = urlsplit(response.url)
                self.scope.accept(response.url)
                if (final.scheme, final.port) != (parts.scheme, parts.port):
                    raise ValueError("robots.txt redirected to another origin")
                handler.parse(response.status, response.body)
                self.fetcher.delay = max(self.fetcher.delay, handler.delay)
            except (
                ValueError,
                httpx.HTTPError,
                OSError,
                TimeoutError,
                UnicodeError,
                ParseError,
                DefusedXmlException,
            ) as exc:
                handler.allowed = False
                detail = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
                handler.reason = f"robots.txt could not be inspected: {detail}; crawl denied"
            self.robots[origin] = handler
            if not handler.permits(url):
                self.warn(handler.reason)
        return self.robots[origin]

    async def permitted(self, url):
        return (await self.robots_for(url)).permits(url)

    async def sitemaps(self, handler, progress=None):
        parts = urlsplit(self.scope.start)
        conventional = urlunsplit((parts.scheme, parts.netloc, "/sitemap.xml", "", ""))
        queue = deque((url, 0) for url in [*handler.sitemaps, conventional])
        visited = set()
        processed = 0
        while queue and processed < self.settings.crawl_sitemap_entries:
            raw, depth = queue.popleft()
            processed += 1
            diagnostic = None
            try:
                url = self.scope.accept(raw)
                if url in visited:
                    continue
                visited.add(url)
                diagnostic = {"url": url}
                if len(self.sitemap_diagnostics) < 30:
                    self.sitemap_diagnostics.append(diagnostic)
                result = await self.fetcher.get(url, self.settings.crawl_sitemap_bytes)
                diagnostic["status"] = result.status
                if result.status != 200:
                    self.warn(f"Sitemap returned HTTP {result.status}")
                    continue
                index, entries = SitemapParser.parse(result.body)
                from defusedxml import ElementTree

                root = ElementTree.fromstring(result.body, forbid_dtd=True)
                diagnostic.update(
                    parsed=True,
                    entries=len(entries),
                    lastmod_samples=[
                        node.text[:100]
                        for node in root.iter()
                        if node.tag.rsplit("}", 1)[-1] == "lastmod" and node.text
                    ][:100],
                )
                for entry in entries:
                    if processed >= self.settings.crawl_sitemap_entries:
                        break
                    processed += 1
                    try:
                        entry = self.scope.accept(entry, url)
                    except ValueError:
                        continue
                    if index:
                        if depth < self.settings.crawl_sitemap_depth:
                            queue.append((entry, depth + 1))
                    else:
                        self.discovered.add(entry)
            except (
                ValueError,
                httpx.HTTPError,
                OSError,
                TimeoutError,
                UnicodeError,
                ParseError,
                DefusedXmlException,
            ) as exc:
                self.warn(f"Sitemap skipped ({type(exc).__name__})")
                if diagnostic is not None:
                    diagnostic["error"] = type(exc).__name__
            finally:
                if progress:
                    progress(self)

    async def page(self, url, depth):
        record = {"url": url, "crawl_depth": depth, "page_metadata": {}}
        links = []
        try:
            response = await self.fetcher.get(url, self.settings.crawl_html_bytes)
            record.update(
                url=response.url, status_code=response.status, content_type=response.content_type
            )
            if response.status >= 400:
                record["crawl_error"] = f"HTTP {response.status}"
            if (
                "text/html" in response.content_type.lower()
                or "application/xhtml+xml" in response.content_type.lower()
            ):
                metadata, links = PageParser.parse(response.body, response.url, self.scope)
                record.update(metadata)
                if response.status >= 400:
                    links = []
            else:
                record["page_metadata"] = {"skipped": "Non-HTML response"}
        except (
            ValueError,
            httpx.HTTPError,
            OSError,
            TimeoutError,
            UnicodeError,
            ParseError,
            DefusedXmlException,
        ) as exc:
            # Avoid leaking remote text, credential-bearing redirects or network internals.
            record["crawl_error"] = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
        if "response" in locals():
            record["page_metadata"]["http"] = {
                "redirects": response.redirects or [],
                "headers": {
                    k: str(v)[:200]
                    for k, v in (response.headers or {}).items()
                    if k.lower()
                    in (
                        "retry-after",
                        "ratelimit-limit",
                        "ratelimit-remaining",
                        "ratelimit-reset",
                        "x-ratelimit-limit",
                        "x-ratelimit-remaining",
                        "x-ratelimit-reset",
                        "server",
                        "cf-mitigated",
                    )
                },
            }
        if "response" in locals() and response.status == 200:
            from app.engines.static_audit.resources import header_resource_links

            html_links = record["page_metadata"].get("audit", {}).get("discovery_resources")
            if isinstance(html_links, dict):
                self.diagnostics["html_inspected"] = True
            for source in (
                html_links or {},
                header_resource_links((response.headers or {}).get("link", ""), response.url),
            ):
                self.diagnostics["resources_limited"] |= bool(source.get("limited"))
                for item in source.get("candidates", []):
                    item = {**item, "linked_from": public_url(response.url)}
                    if (
                        len(self.resource_candidates) >= 30
                        and item["url"] not in self.resource_candidates
                    ):
                        self.diagnostics["resources_limited"] = True
                        break
                    self.resource_candidates.setdefault(item["url"], item)
        if record["url"] != url:
            record["page_metadata"]["requested_url"] = url
        return record, links

    async def crawl(self, persist, progress):
        try:
            async with asyncio.timeout(self.settings.crawl_duration):
                await self._crawl(persist, progress)
        finally:
            await self.fetcher.close()

    async def _crawl(self, persist, progress):
        self.discovered.add(self.scope.start)
        handler = await self.robots_for(self.scope.start)
        self.fetcher.permit = self.permitted
        progress(self)
        if not handler.permits(self.scope.start):
            reason = "robots.txt disallows the starting URL" if handler.allowed else handler.reason
            raise ValueError("Crawling denied: " + reason)
        await self.sitemaps(handler, progress)
        from app.engines.static_audit.site import llms_measurements

        parts = urlsplit(self.scope.start)
        llms_url = urlunsplit((parts.scheme, parts.netloc, "/llms.txt", "", ""))
        self.llms = {"url": llms_url}
        try:
            llms = await self.fetcher.get(llms_url, min(256_000, self.settings.crawl_html_bytes))
            self.llms["status"] = llms.status
            if llms.status == 200:
                self.llms.update(llms_measurements(llms.body))
        except (ValueError, httpx.HTTPError, OSError, TimeoutError, UnicodeError) as exc:
            self.llms["error"] = type(exc).__name__
        progress(self)
        # Sitemap URLs have discovery depth 1, ordered by path depth.
        queue = deque(
            [(self.scope.start, 0)]
            + [
                (url, 1)
                for url in sorted(
                    self.discovered - {self.scope.start},
                    key=lambda u: (urlsplit(u).path.count("/"), u),
                )
            ]
            if self.settings.crawl_max_depth >= 1
            else [(self.scope.start, 0)]
        )
        scheduled = set()
        final_urls = set()
        while queue and len(scheduled) < self.settings.crawl_max_pages:
            batch = []
            current_depth = queue[0][1]
            while (
                queue
                and queue[0][1] == current_depth
                and len(batch) < self.settings.crawl_concurrency
            ):
                url, depth = queue.popleft()
                if url in scheduled or url in final_urls:
                    continue
                if len(scheduled) >= self.settings.crawl_max_pages:
                    break
                scheduled.add(url)
                batch.append((url, depth))
            results = await asyncio.gather(*(self.page(url, depth) for url, depth in batch))
            for (record, links), (_, depth) in zip(results, batch, strict=True):
                self.crawled += 1
                self.failed += bool(record.get("crawl_error"))
                if record["url"] not in final_urls:
                    final_urls.add(record["url"])
                    persist(record)
                if depth < self.settings.crawl_max_depth:
                    for link in links:
                        # Bound the frontier as well as actual requests.
                        if (
                            len(self.discovered)
                            >= self.settings.crawl_sitemap_entries + self.settings.crawl_max_pages
                        ):
                            break
                        if link not in self.discovered:
                            self.discovered.add(link)
                            queue.append((link, depth + 1))
                progress(self)
        if self.failed == self.crawled:
            raise ValueError("No pages could be crawled successfully")
        from app.engines.crawling.diagnostics import collect_diagnostics

        await collect_diagnostics(self, progress)

    def metadata(self):
        return {
            "robots": {
                origin: handler.metadata(
                    self.scope.start if self.scope.start.startswith(origin + "/") else origin + "/"
                )
                for origin, handler in self.robots.items()
            },
            "warnings": self.warnings,
            "sitemaps": self.sitemap_diagnostics,
            "llms": self.llms,
            "diagnostics": deepcopy(self.diagnostics),
        }
