"""Serve a site's published agent variant from the edge router.

- The HTML replacement at the original URL is served only to user-initiated agents
  (`Visitor.routable`), never to search or training crawlers.
- Explicitly agent-facing URLs are open to every caller: Markdown mirrors (`.md`),
  `/llms.txt`, the REST actions under `/agent-api/` and the MCP endpoint `/mcp`.
- Anything else, or any site without a published variant, falls through to the origin.
"""

import json
from dataclasses import dataclass, field

from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response

from app.engines.variants.actions import (
    ActionError,
    DeliveryRules,
    handle_mcp,
    run_tool,
)
from app.engines.variants.contracts import Catalog
from app.engines.variants.render import markdown_path
from app.repositories.edge import EdgeRecords

MAX_MCP_BYTES = 64 * 1024


@dataclass(frozen=True)
class VariantSnapshot:
    version: int
    as_of: str
    catalog: Catalog
    llms_txt: str
    rules: DeliveryRules | None
    pages: dict[str, tuple[str, str]] = field(default_factory=dict)  # path -> (markdown, html)


def load_variant(session, site_id, delivery_rules) -> VariantSnapshot | None:
    records = EdgeRecords(session)
    variant = records.published_variant(site_id)
    if variant is None:
        return None
    try:
        rules = DeliveryRules.model_validate(delivery_rules) if delivery_rules else None
    except ValueError:
        rules = None  # Invalid owner data disables check_delivery instead of failing.
    return VariantSnapshot(
        version=variant.version,
        as_of=(variant.published_at or variant.created_at).isoformat(),
        catalog=Catalog.model_validate(variant.catalog),
        llms_txt=variant.llms_txt,
        rules=rules,
        pages={p.path: (p.markdown, p.html) for p in records.variant_pages(variant.id)},
    )


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message, "details": []}}, status)


def _headers(variant: VariantSnapshot, page_path: str) -> dict[str, str]:
    return {
        "x-agentlane-variant": f"v{variant.version}",
        "link": f'<{markdown_path(page_path)}>; rel="alternate"; type="text/markdown"',
        "vary": "User-Agent, Accept",
        "cache-control": "public, max-age=60",
    }


def agent_surface(request: Request, variant: VariantSnapshot, body: bytes):
    """URLs that exist only for agents. Returns (response, action) or None."""
    path, method = request.url.path, request.method
    if path == "/llms.txt" and method in ("GET", "HEAD"):
        return PlainTextResponse(
            variant.llms_txt, headers={"x-agentlane-variant": f"v{variant.version}"}
        ), "llms_txt"
    if path.endswith(".md") and method in ("GET", "HEAD"):
        base = "/" if path == "/index.md" else path[:-3]
        if base in variant.pages:
            return Response(
                variant.pages[base][0],
                media_type="text/markdown; charset=utf-8",
                headers=_headers(variant, base),
            ), None
        return None
    if path.startswith("/agent-api/") and method == "GET":
        query = request.query_params
        try:
            if path == "/agent-api/search":
                name, args = (
                    "search_products",
                    {
                        key: query[key]
                        for key in ("q", "size", "max_price", "limit")
                        if key in query
                    },
                )
            elif path.startswith("/agent-api/products/"):
                name, args = "get_product", {"slug": path.rsplit("/", 1)[-1]}
            elif path == "/agent-api/delivery":
                name, args = "check_delivery", {"pin": query.get("pin", "")}
            else:
                return _error(404, "unknown_action", "Unknown agent action"), "unknown"
            result = run_tool(name, args, variant.catalog, variant.rules, variant.as_of)
            return JSONResponse(
                result, headers={"x-agentlane-variant": f"v{variant.version}"}
            ), name
        except ActionError as exc:
            return _error(exc.status, exc.code, exc.message), name
    if path == "/mcp":
        if method != "POST":
            return Response(status_code=405, headers={"allow": "POST"}), "mcp"
        if len(body) > MAX_MCP_BYTES:
            return _error(413, "request_too_large", "MCP message is too large"), "mcp"
        try:
            message = json.loads(body or b"null")
        except ValueError:
            message = None
        response, action = handle_mcp(
            message, variant.catalog.store_name, variant.catalog, variant.rules, variant.as_of
        )
        if response is None:
            return Response(status_code=202), "mcp"
        return JSONResponse(response), action or "mcp"
    return None


def variant_page(request: Request, variant: VariantSnapshot) -> Response | None:
    """The agent-friendly HTML (or Markdown on request) at the original URL."""
    if request.method not in ("GET", "HEAD"):
        return None
    page = variant.pages.get(request.url.path)
    if page is None:
        return None
    if "text/markdown" in request.headers.get("accept", ""):
        return Response(
            page[0],
            media_type="text/markdown; charset=utf-8",
            headers=_headers(variant, request.url.path),
        )
    return Response(
        page[1], media_type="text/html; charset=utf-8", headers=_headers(variant, request.url.path)
    )
