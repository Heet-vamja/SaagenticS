"""Edge router ASGI app: `uvicorn app.edge.main:app`.

Every request is matched to a registered site by its Host header and proxied to that
site's single configured origin. Agent and crawler requests are logged after the
response finishes; human traffic is passed through untouched and not logged. When the
site has a published agent variant, `app/edge/variants.py` answers agent-facing URLs and
serves the agent-friendly page to user-initiated agents. The router fails open: variant
or logging problems never block proxying to the origin.
"""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

import httpx
from sqlalchemy.exc import SQLAlchemyError
from starlette.applications import Starlette
from starlette.background import BackgroundTask
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import Route

from app.core.config import Settings, get_settings
from app.db.session import SessionLocal
from app.edge.agents import Visitor, classify
from app.edge.variants import VariantSnapshot, agent_surface, load_variant, variant_page
from app.engines.crawling.transport import SafeTransport
from app.repositories.edge import EdgeRecords
from app.services.agent_policy import client_identity
from app.services.edge_sites import normalize_host
from app.services.request_log import (
    PostgresRequestLogSink,
    RequestEvent,
    RequestLogSink,
    client_hash,
    write_safely,
)

logger = logging.getLogger(__name__)
HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "proxy-connection",
    "te",
    "trailer",
    "trailers",
    "transfer-encoding",
    "upgrade",
}
MAX_REQUEST_BYTES = 10 * 1024 * 1024
HEALTH_PATH = "/_agentlane/health"
METHODS = ["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]


@dataclass(frozen=True)
class SiteSnapshot:
    id: UUID
    origin_url: str
    routing_enabled: bool
    delivery_rules: dict | None = None


def error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message, "details": []}}, status)


def end_to_end(items: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Drop hop-by-hop headers, including any named by the Connection header."""
    named = {
        token.strip().lower()
        for key, value in items
        if key.lower() == "connection"
        for token in value.split(",")
    }
    drop = HOP_BY_HOP | named
    return [(key, value) for key, value in items if key.lower() not in drop]


def create_app(
    session_factory=SessionLocal,
    sink: RequestLogSink | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
    settings: Settings | None = None,
    cache_seconds: float = 15.0,
) -> Starlette:
    settings = settings or get_settings()
    sink = sink or PostgresRequestLogSink(session_factory)
    cache: dict[str, tuple[float, SiteSnapshot | None]] = {}
    variants: dict[UUID, tuple[float, VariantSnapshot | None]] = {}
    if transport is None and not settings.edge_allow_private_origins:
        # Public origins only: DNS answers are checked at connect time (ports 80/443).
        transport = SafeTransport(concurrency=100)
    client = httpx.AsyncClient(
        transport=transport,
        timeout=settings.edge_upstream_timeout,
        follow_redirects=False,
        trust_env=False,  # Never route customer traffic through ambient proxies.
    )

    def load_site(host: str) -> SiteSnapshot | None:
        with session_factory() as session:
            site = EdgeRecords(session).site_by_host(host)
            if site is None:
                return None
            return SiteSnapshot(site.id, site.origin_url, site.routing_enabled, site.delivery_rules)

    def read_variant(site: SiteSnapshot) -> VariantSnapshot | None:
        with session_factory() as session:
            return load_variant(session, site.id, site.delivery_rules)

    async def variant_for(site: SiteSnapshot) -> VariantSnapshot | None:
        now = time.monotonic()
        cached = variants.get(site.id)
        if cached and cached[0] > now:
            return cached[1]
        try:
            variant = await asyncio.to_thread(read_variant, site)
        except (SQLAlchemyError, ValueError):
            # Fail open: a broken or unreadable variant never blocks the origin.
            logger.warning("Variant unavailable for site %s", site.id, exc_info=True)
            variant = None
        variants[site.id] = (now + cache_seconds, variant)
        return variant

    async def site_for(host: str) -> SiteSnapshot | None:
        now = time.monotonic()
        cached = cache.get(host)
        if cached and cached[0] > now:
            return cached[1]
        site = await asyncio.to_thread(load_site, host)
        cache[host] = (now + cache_seconds, site)
        return site

    async def proxy(request: Request) -> Response:
        if request.url.path == HEALTH_PATH:
            return JSONResponse({"status": "ok"})
        started = time.monotonic()
        received_at = datetime.now(UTC)
        raw_host = request.headers.get("host", "")
        try:
            host = normalize_host(raw_host)
        except ValueError:
            return error(400, "invalid_host", "The request host is not valid")
        site = await site_for(host)
        if site is None:
            return error(404, "unknown_site", "This host is not served by AgentLane")

        user_agent = request.headers.get("user-agent") or ""
        visitor = classify(user_agent)
        hashed_client = client_hash(client_identity(request, settings), settings)

        async def log(
            status: int,
            served_by: str,
            size: int,
            action: str | None = None,
            actor: Visitor | None = None,
        ) -> None:
            actor = actor or visitor
            if actor.kind == "human":
                return
            event = RequestEvent(
                site_id=site.id,
                received_at=received_at,
                agent=actor.name,
                agent_kind=actor.kind,
                action=action,
                method=request.method,
                path=request.url.path[:2048],  # Query strings are never stored.
                status=status,
                duration_ms=int((time.monotonic() - started) * 1000),
                served_by=served_by,
                response_bytes=size,
                client_hash=hashed_client,
                user_agent=user_agent[:300],
            )
            await asyncio.to_thread(write_safely, sink, [event])

        body = await request.body()
        if len(body) > MAX_REQUEST_BYTES:
            await log(413, "router", 0)
            return error(413, "request_too_large", "Request body is too large")

        variant = await variant_for(site)
        if variant is not None:
            surface = agent_surface(request, variant, body)
            if surface is not None:
                answer, action = surface
                # Agent-facing URLs are machine traffic even from unrecognized clients.
                actor = visitor if visitor.kind != "human" else Visitor("unidentified", "agent")
                answer.background = BackgroundTask(
                    log, answer.status_code, "variant", len(answer.body), action, actor
                )
                return answer
            if visitor.routable and site.routing_enabled:
                page = variant_page(request, variant)
                if page is not None:
                    page.background = BackgroundTask(
                        log, page.status_code, "variant", len(page.body)
                    )
                    return page

        peer = request.client.host if request.client else "unknown"
        prior = request.headers.get("x-forwarded-for")
        headers = [
            (key, value)
            for key, value in end_to_end(request.headers.items())
            if key.lower() not in ("host", "content-length")
            and not key.lower().startswith("x-forwarded-")
        ] + [
            ("x-forwarded-for", f"{prior}, {peer}" if prior else peer),
            ("x-forwarded-proto", request.url.scheme),
            ("x-forwarded-host", raw_host),
        ]
        # Forward the raw path so percent-encoding reaches the origin unchanged.
        raw_path = request.scope.get("raw_path", request.url.path.encode()).decode("latin-1")
        query = request.scope.get("query_string", b"").decode("latin-1")
        target = site.origin_url + raw_path + (f"?{query}" if query else "")
        try:
            upstream = await client.send(
                client.build_request(request.method, target, headers=headers, content=body),
                stream=True,
            )
        except (httpx.HTTPError, ValueError):  # ValueError: refused non-public destination.
            await log(502, "router", 0)
            return error(502, "upstream_unavailable", "The website could not be reached")

        sent = 0

        async def relay():
            nonlocal sent
            try:
                async for chunk in upstream.aiter_raw():
                    sent += len(chunk)
                    yield chunk
            finally:
                await upstream.aclose()

        async def finish():
            await log(upstream.status_code, "origin", sent)

        public_origin = f"{request.url.scheme}://{raw_host}"
        response_headers = []
        for key, value in end_to_end(upstream.headers.multi_items()):
            if key.lower() == "location" and value.startswith(site.origin_url):
                # Keep visitors on the public host; never reveal the private origin.
                value = public_origin + value[len(site.origin_url) :]
            response_headers.append((key.lower().encode("latin-1"), value.encode("latin-1")))
        response = StreamingResponse(
            relay(), status_code=upstream.status_code, background=BackgroundTask(finish)
        )
        response.raw_headers = response_headers
        return response

    @asynccontextmanager
    async def lifespan(_app):
        try:
            yield
        finally:
            await client.aclose()

    return Starlette(routes=[Route("/{path:path}", proxy, methods=METHODS)], lifespan=lifespan)


app = create_app()
