import asyncio
from xml.etree.ElementTree import ParseError

import httpx
import pytest
from defusedxml.common import DefusedXmlException

from app.core.config import Settings
from app.engines.crawling.crawler import WebsiteCrawler
from app.engines.crawling.parsers import PageParser, RobotsHandler, SitemapParser
from app.engines.crawling.transport import Fetcher
from app.engines.crawling.urls import URLValidator


def run(coroutine):
    return asyncio.run(coroutine)


def fetcher(handler, **overrides):
    settings = Settings(**overrides)
    scope = URLValidator("https://example.com")
    return Fetcher(scope, settings, httpx.MockTransport(handler))


def response(status=200, body=b"", **headers):
    return httpx.Response(status, stream=httpx.ByteStream(body), headers=headers)


def test_robots_policy():
    robots = RobotsHandler("AgentReadinessBot/0.1")
    robots.parse(
        200,
        b"User-agent: *\nDisallow: /private\nCrawl-delay: 2\nSitemap: https://example.com/map.xml",
    )
    assert robots.permits("https://example.com/")
    assert not robots.permits("https://example.com/private")
    assert robots.delay == 2
    assert robots.sitemaps == ["https://example.com/map.xml"]
    robots = RobotsHandler("AgentReadinessBot/0.1")
    robots.parse(503, b"")
    assert not robots.permits("https://example.com/")
    robots.parse(404, b"")
    assert robots.permits("https://example.com/")
    with pytest.raises(ValueError):
        robots.parse(200, b"<html>error</html>")


def test_sitemap_safe_xml_and_indexes():
    assert SitemapParser.parse(
        b'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://example.com/</loc></url></urlset>'
    ) == (False, ["https://example.com/"])
    assert SitemapParser.parse(
        b"<sitemapindex><sitemap><loc>https://example.com/map.xml</loc></sitemap></sitemapindex>"
    )[0]
    for body in [
        b"<broken",
        b'<!DOCTYPE a [<!ENTITY x SYSTEM "file:///etc/passwd">]><urlset>&x;</urlset>',
    ]:
        with pytest.raises((ParseError, DefusedXmlException)):
            SitemapParser.parse(body)


def test_metadata_and_invalid_html():
    data, links = PageParser.parse(
        b'<html lang="en"><title>Example</title><meta name="description" content="Description"><link rel="canonical" href="/canonical"><h1>Heading</h1><a href="/about#x">About</a><a href="https://evil.com">External</a><a href="/about">Duplicate</a>',
        "https://example.com/",
        URLValidator("https://example.com"),
    )
    assert data["title"] == "Example"
    assert data["meta_description"] == "Description"
    assert data["canonical_url"] == "https://example.com/canonical"
    assert data["page_metadata"]["headings"] == [{"level": 1, "text": "Heading"}]
    assert links == ["https://example.com/about"]
    assert (
        PageParser.parse(
            b"<html><title>unclosed", "https://example.com/", URLValidator("https://example.com")
        )[0]["title"]
        == "unclosed"
    )


def crawl_site(handler, **settings):
    f = fetcher(handler, **settings)
    crawler = WebsiteCrawler("https://example.com", f.settings, f)
    records, snapshots = [], []
    run(crawler.crawl(records.append, lambda c: snapshots.append((c.crawled, c.failed))))
    return crawler, records, snapshots


def test_discovery_limits_duplicates_and_failures():
    calls = []

    def site(request):
        path = request.url.path
        calls.append(path)
        if path == "/robots.txt":
            return response(
                200, b"User-agent: *\nDisallow: /private\nSitemap: https://example.com/index.xml"
            )
        if path == "/index.xml":
            return response(
                200, b"<sitemapindex><sitemap><loc>/map.xml</loc></sitemap></sitemapindex>"
            )
        if path == "/map.xml":
            return response(
                200,
                b"<urlset><url><loc>/broken</loc></url><url><loc>https://evil.com/</loc></url></urlset>",
            )
        if path == "/sitemap.xml":
            return response(404)
        if path == "/broken":
            return response(404)
        return response(
            200,
            b'<title>Page</title><a href="/next">Next</a><a href="/next#f">Duplicate</a><a href="/private">Private</a>',
            **{"content-type": "text/html"},
        )

    crawler, records, snapshots = crawl_site(site, crawl_max_pages=4, crawl_max_depth=1)
    assert len(records) == 4
    assert max(record["crawl_depth"] for record in records) == 1
    assert calls.count("/next") == 1
    assert "/private" not in calls
    assert crawler.failed == 2  # broken link + robots-denied page
    assert snapshots[-1] == (4, 2)
    assert len({record["url"] for record in records}) == len(records)
    crawler, records, _ = crawl_site(site, crawl_max_depth=0)
    assert len(records) == 1
    assert records[0]["crawl_depth"] == 0


def test_conservative_robots_failure_and_total_duration():
    with pytest.raises(ValueError, match="denied"):
        crawl_site(lambda r: response(503))

    async def slow(request):
        if request.url.path == "/robots.txt":
            return response(404)
        await asyncio.sleep(0.1)
        return response(200)

    with pytest.raises(TimeoutError):
        crawl_site(slow, crawl_duration=0.02)


def test_sitemap_budget_nesting_and_redirect_aliases():
    calls = []

    def site(request):
        path = request.url.path
        calls.append(path)
        if path == "/robots.txt":
            return response(404)
        if path == "/sitemap.xml":
            return response(
                200, b"<sitemapindex><sitemap><loc>/nested.xml</loc></sitemap></sitemapindex>"
            )
        if path == "/nested.xml":
            return response(
                200, b"<sitemapindex><sitemap><loc>/too-deep.xml</loc></sitemap></sitemapindex>"
            )
        if path == "/alias":
            return response(302, location="/")
        return response(200, b'<a href="/alias">Alias</a>', **{"content-type": "text/html"})

    crawler, records, _ = crawl_site(site, crawl_sitemap_depth=1)
    assert "/too-deep.xml" not in calls
    assert len(records) == 1
    assert crawler.crawled == 2
    calls.clear()
    crawl_site(site, crawl_sitemap_entries=1)
    assert "/nested.xml" not in calls


def test_robots_wildcards_specific_agents_and_longest_match():
    robots = RobotsHandler("AgentReadinessBot/0.1")
    robots.parse(
        200,
        b"User-agent: *\nDisallow: /\n\nUser-agent: AgentReadinessBot\nDisallow: /*?secret=\nDisallow: /private\nAllow: /private/public\nDisallow: /private/public/delete$\nCrawl-delay: 0.5",
    )
    assert robots.permits("https://example.com/")
    assert not robots.permits("https://example.com/path?secret=value")
    assert not robots.permits("https://example.com/private/x")
    assert robots.permits("https://example.com/private/public")
    assert not robots.permits("https://example.com/private/public/delete")
    assert robots.delay == 0.5


def test_robots_www_redirect_reports_scope_without_claiming_file_absent():
    calls = []

    def site(request):
        calls.append(str(request.url))
        return response(301, location="https://www.example.com/robots.txt")

    f = fetcher(site)
    crawler = WebsiteCrawler("https://example.com", f.settings, f)
    with pytest.raises(ValueError, match="www.example.com.*example.com"):
        run(crawler.crawl(lambda record: None, lambda state: None))
    assert calls == ["https://example.com/robots.txt"]
    robots = crawler.metadata()["robots"]["https://example.com"]
    assert robots["exists"] is None
    assert robots["permitted"] is False
    assert "project website URL" in robots["reason"]


def test_absent_robots_allows_page_and_sitemap_discovery():
    def site(request):
        if request.url.path == "/robots.txt":
            return response(404)
        if request.url.path == "/sitemap.xml":
            return response(200, b"<urlset><url><loc>/about</loc></url></urlset>")
        return response(
            200, b"<title>Allowed without robots</title>", **{"content-type": "text/html"}
        )

    crawler, records, _ = crawl_site(site)
    assert {record["url"] for record in records} == {
        "https://example.com/",
        "https://example.com/about",
    }
    assert crawler.failed == 0
    assert crawler.metadata()["robots"]["https://example.com"]["exists"] is False
