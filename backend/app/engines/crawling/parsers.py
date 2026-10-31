from urllib.parse import urljoin

from bs4 import BeautifulSoup
from defusedxml import ElementTree
from protego import Protego

from app.engines.crawling.urls import URLValidator
from app.engines.static_audit.html import inspect_html
from app.engines.static_audit.site import AI_AGENTS


class RobotsHandler:
    def __init__(self, agent: str):
        self.agent = agent
        self.parser = Protego.parse("")
        self.exists: bool | None = None
        self.reason = "Not inspected"
        self.allowed = False

    def parse(self, status: int, body: bytes):
        self.allowed = False
        self.exists = status not in (404, 410)
        if status in (404, 410):
            self.parser = Protego.parse("")
            self.allowed, self.reason = True, "robots.txt absent"
        elif status == 200:
            text = body.decode("utf-8-sig", errors="strict")
            lines = [line.split("#", 1)[0].strip() for line in text.splitlines()]
            if (
                "<html" in text.lower()
                or "\x00" in text
                or any(line and ":" not in line for line in lines)
            ):
                raise ValueError("Invalid robots.txt")
            self.parser = Protego.parse(text)
            self.allowed, self.reason = True, "robots.txt parsed"
        else:
            self.reason = f"robots.txt returned HTTP {status}; crawl denied"

    def permits(self, url: str) -> bool:
        return self.allowed and self.parser.can_fetch(url, self.agent)

    @property
    def sitemaps(self):
        return list(self.parser.sitemaps)

    @property
    def delay(self):
        delay = self.parser.crawl_delay(self.agent) or 0
        rate = self.parser.request_rate(self.agent)
        return max(delay, rate.seconds / rate.requests if rate and rate.requests else 0)

    def metadata(self, url: str):
        return {
            "exists": self.exists,
            "permitted": self.permits(url),
            "reason": self.reason,
            "url": url,
            "ai_agents": {
                agent: {
                    "allowed": self.allowed and self.parser.can_fetch(url, agent),
                    "sampled_paths": [url],
                    "known": self.exists is not None and self.allowed,
                }
                for agent in AI_AGENTS
            },
        }


class SitemapParser:
    @staticmethod
    def parse(body: bytes) -> tuple[bool, list[str]]:
        root = ElementTree.fromstring(body, forbid_dtd=True)
        kind = root.tag.rsplit("}", 1)[-1]
        if kind not in ("sitemapindex", "urlset"):
            raise ValueError("Unsupported sitemap root")
        tag = "sitemap" if kind == "sitemapindex" else "url"
        locations = []
        for child in root:
            if child.tag.rsplit("}", 1)[-1] == tag:
                for element in child:
                    if element.tag.rsplit("}", 1)[-1] == "loc" and element.text:
                        locations.append(element.text.strip())
                        break
        return kind == "sitemapindex", locations


class PageParser:
    @staticmethod
    def parse(body: bytes, url: str, scope: URLValidator):
        soup = BeautifulSoup(body, "html.parser")
        description = soup.find("meta", attrs={"name": lambda x: x and x.lower() == "description"})
        canonical = soup.find("link", rel=lambda x: x and "canonical" in x)
        canonical_url = None
        if canonical and canonical.get("href"):
            try:
                canonical_url = scope.normalize(urljoin(url, canonical["href"]))
                if len(canonical_url) > 2048:
                    canonical_url = None
            except ValueError:
                pass
        links = set()
        for anchor in soup.find_all("a", href=True):
            try:
                links.add(scope.accept(anchor["href"], url))
            except ValueError:
                continue
        headings = [
            {"level": int(h.name[1]), "text": h.get_text(" ", strip=True)[:2000]}
            for h in soup.find_all([f"h{i}" for i in range(1, 7)], limit=200)
        ]
        return {
            "title": soup.title.get_text(" ", strip=True)[:4000] if soup.title else None,
            "meta_description": str(description.get("content", ""))[:4000] if description else None,
            "canonical_url": canonical_url,
            "page_metadata": {
                "headings": headings,
                "internal_links": sorted(links)[:500],
                "language": soup.html.get("lang") if soup.html else None,
                "audit": inspect_html(body, url, soup),
            },
        }, sorted(links)
