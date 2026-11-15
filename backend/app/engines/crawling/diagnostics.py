"""Read-only diagnostics through the crawler's existing DNS-pinned, robots-aware fetcher."""

import asyncio
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import httpx

from app.engines.agent.privacy import public_url
from app.engines.static_audit.html import CHALLENGE
from app.engines.static_audit.resources import (
    CATALOG_PATH,
    catalog_resources,
    inspect_catalog,
    validate_resource,
)

ERRORS = (ValueError, httpx.HTTPError, OSError, TimeoutError, UnicodeError)
MAX_BYTES = 128_000


def observation(response):
    return {
        "status": response.status,
        "final_url": public_url(response.url),
        "redirects": len(response.redirects or []),
    }


def restricted(response):
    html = "html" in response.content_type.lower() or response.body.lstrip().startswith(b"<")
    return (
        response.status in (401, 403, 408, 429)
        or response.status >= 500
        or (response.headers or {}).get("cf-mitigated") == "challenge"
        or (html and bool(CHALLENGE.search(response.body.decode("utf-8", errors="replace"))))
    )


def pending(item):
    return {
        **item,
        "result": "UNKNOWN",
        "detail": "No completed result within the diagnostic budget",
    }


async def validate_linked(item, scope, fetcher, settings):
    url = scope.accept(item["url"])
    # The fetcher checks every redirect and reuses the validated socket transport.
    response = await fetcher.get(url, min(MAX_BYTES, settings.crawl_html_bytes))
    item.update(observation(response))
    if restricted(response):
        item["detail"] = "Restricted, challenged or transient response; validation is inconclusive"
    elif response.status in (404, 410):
        item.update(result="FAIL", detail="The linked resource returned not found/gone")
    elif response.status == 200:
        item["result"], item["detail"] = validate_resource(
            item["kind"], response.body, response.content_type
        )
    else:
        item["detail"] = "The linked resource did not return a supported success response"


async def check_catalog(data, scope, fetcher, settings):
    """One well-known AI Catalog request and at most one catalog-listed server card."""
    catalog, card = data["ai_catalog"], data["mcp_server_card"]
    parts = urlsplit(scope.start)
    url = urlunsplit((parts.scheme, parts.netloc, CATALOG_PATH, "", ""))
    catalog["probe_url"] = public_url(url)
    try:
        response = await fetcher.get(url, min(MAX_BYTES, settings.crawl_html_bytes))
        catalog.update(observation(response))
        if restricted(response):
            catalog["detail"] = "Restricted, challenged or transient response; catalog is unknown"
        else:
            catalog["result"], catalog["detail"], entries = inspect_catalog(
                response.status, response.body, response.content_type
            )
            listed = catalog_resources(entries, response.url)
            catalog["entries"] = [
                {"url": public_url(e["url"]), "kind": e["kind"], "type": e["type"]} for e in listed
            ]
    except ERRORS as exc:
        catalog["detail"] = type(exc).__name__
        listed = []
    if catalog["result"] in ("UNKNOWN", "FAIL"):
        card["detail"] = "The AI Catalog was unavailable, so a listed server card is unknown"
        return []
    cards = [e for e in listed if e["kind"] == "mcp_server_card"]
    if not cards:
        card.update(
            result="ABSENT",
            detail="No server card listed in an AI Catalog; reserved MCP endpoint paths were not probed",
        )
        return listed
    card.update(url=public_url(cards[0]["url"]), listed=len(cards))
    try:
        item = {"kind": "mcp_server_card", "url": cards[0]["url"]}
        await validate_linked(item, scope, fetcher, settings)
        card.update(
            {k: item[k] for k in ("status", "final_url", "redirects", "detail") if k in item},
            result=item.get("result", "UNKNOWN"),
        )
    except ERRORS as exc:
        card["detail"] = type(exc).__name__
    return listed


async def collect_diagnostics(crawler, progress):
    data = crawler.diagnostics
    scope, fetcher, settings = crawler.scope, crawler.fetcher, crawler.settings
    limit = settings.audit_resource_limit
    candidates = list(crawler.resource_candidates.values())
    catalog_links = [item for item in candidates if item["kind"] == "ai_catalog"]
    mirrors = [item for item in candidates if item["kind"] == "markdown_alternate"]
    candidates = [
        item for item in candidates if item["kind"] not in ("ai_catalog", "markdown_alternate")
    ]
    data["linked_candidates"] = len(candidates)
    data["markdown_alternates"] = len(mirrors)
    # Discovery files first; at most one Markdown mirror uses any remaining budget.
    candidates += mirrors[:1]
    data["resources_limited"] |= len(candidates) > limit
    data["resources"] = [pending(item) for item in candidates[:limit]]
    data["ai_catalog"] = {
        "result": "UNKNOWN",
        "detail": "No completed result within the diagnostic budget",
        "advertised": bool(catalog_links),
        "advertised_by": sorted({item["source"] for item in catalog_links}),
    }
    data["mcp_server_card"] = {
        "result": "UNKNOWN",
        "detail": "No completed result within the diagnostic budget",
    }
    if not settings.audit_missing_path_enabled:
        data["missing_path"] = {"result": "UNKNOWN", "detail": "Missing-path probe disabled"}
    try:
        async with asyncio.timeout(settings.audit_diagnostics_timeout):
            # A single probe, never load testing or auth/submission attempts.
            if settings.audit_missing_path_enabled:
                parts = urlsplit(scope.start)
                path = "/.agentreadiness-missing-" + uuid4().hex
                url = urlunsplit((parts.scheme, parts.netloc, path, "", ""))
                probe = data["missing_path"] = {"result": "UNKNOWN", "probe_url": public_url(url)}
                try:
                    response = await fetcher.get(url, min(MAX_BYTES, settings.crawl_html_bytes))
                    probe.update(observation(response))
                    if restricted(response):
                        probe["detail"] = (
                            "Restricted, challenged or transient response; missing-route behavior is unknown"
                        )
                    elif response.status == 404:
                        probe.update(result="PASS", detail="The one random path returned HTTP 404")
                    elif (
                        200 <= response.status < 300
                        and not response.redirects
                        and "html" in response.content_type.lower()
                    ):
                        probe.update(
                            result="FAIL",
                            detail="The random, unlinked path returned a successful HTML response; review for a soft 404",
                        )
                    else:
                        probe["detail"] = (
                            "Redirect intent or route semantics cannot be established from this response"
                        )
                except ERRORS as exc:
                    probe["detail"] = type(exc).__name__
                progress(crawler)
            listed = await check_catalog(data, scope, fetcher, settings)
            known = {item["url"] for item in data["resources"]}
            for entry in listed:
                if entry["kind"] != "openapi" or entry["url"] in known:
                    continue
                if len(data["resources"]) >= limit:
                    data["resources_limited"] = True
                    break
                known.add(entry["url"])
                data["resources"].append(pending(entry))
            progress(crawler)
            # Fetch catalog-listed contracts before an optional Markdown mirror.
            data["resources"].sort(key=lambda item: item["kind"] == "markdown_alternate")
            for item in data["resources"]:
                try:
                    await validate_linked(item, scope, fetcher, settings)
                except ERRORS as exc:
                    item["detail"] = type(exc).__name__
                progress(crawler)
    except TimeoutError:
        data["resources_limited"] = True
        if data["missing_path"].get("result") == "UNKNOWN":
            data["missing_path"].setdefault("detail", "Diagnostic time budget exhausted")
    progress(crawler)
