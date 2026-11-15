"""Edge router: classification, pass-through, logging and failure behavior with a mock origin."""

from contextlib import nullcontext

import httpx
import pytest
from sqlalchemy import select
from starlette.testclient import TestClient

from app.core.config import get_settings
from app.edge.agents import classify
from app.edge.main import create_app
from app.models.domain import AgentRequest
from app.services.edge_sites import normalize_host, register_site, validate_origin

CHROME = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/130 Safari/537.36"
)
CHATGPT = "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; ChatGPT-User/1.0; +https://openai.com/bot"
GOOGLEBOT = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"


class OriginStream(httpx.AsyncByteStream):
    """A real streaming body; httpx pre-reads `content=` responses, unlike real origins."""

    def __init__(self, data: bytes):
        self.data = data

    async def __aiter__(self):
        yield self.data


@pytest.mark.parametrize(
    "user_agent,name,kind",
    [
        (CHATGPT, "ChatGPT-User", "agent"),
        ("Claude-User/1.0 (+Claude-User@anthropic.com)", "Claude-User", "agent"),
        ("Mozilla/5.0 (compatible; Perplexity-User/1.0)", "Perplexity-User", "agent"),
        (GOOGLEBOT, "Googlebot", "crawler"),
        ("Googlebot-Image/1.0", "Googlebot", "crawler"),
        ("Mozilla/5.0 (compatible; GPTBot/1.2; +https://openai.com/gptbot)", "GPTBot", "crawler"),
        ("Mozilla/5.0 (compatible; ClaudeBot/1.0)", "ClaudeBot", "crawler"),
        (CHROME, "human", "human"),
        ("", "human", "human"),
        (None, "human", "human"),
    ],
)
def test_only_user_initiated_agents_are_routable(user_agent, name, kind):
    visitor = classify(user_agent)
    assert (visitor.name, visitor.kind) == (name, kind)
    assert visitor.routable is (kind == "agent")


@pytest.fixture
def edge(session, monkeypatch):
    monkeypatch.setattr(get_settings(), "edge_allow_private_origins", True)
    site = register_site(
        session, get_settings(), "Store.Localhost", "http://demo-store:4000", "Northstar"
    )
    seen = []

    def origin(request: httpx.Request):
        seen.append(request)
        if request.url.path == "/old":
            return httpx.Response(
                302,
                headers={"location": "http://demo-store:4000/new"},
                stream=OriginStream(b""),
            )
        if request.url.path == "/boom":
            raise httpx.ConnectError("origin down", request=request)
        return httpx.Response(
            200,
            headers=[
                ("content-type", "text/html"),
                ("set-cookie", "a=1; Path=/"),
                ("set-cookie", "b=2; Path=/"),
                ("connection", "keep-alive"),
            ],
            stream=OriginStream(b"<html>Northstar</html>"),
        )

    def build(sink=None):
        app = create_app(
            session_factory=lambda: nullcontext(session),
            sink=sink,
            transport=httpx.MockTransport(origin),
            settings=get_settings(),
            cache_seconds=0,
        )
        return TestClient(app, base_url="http://store.localhost:8080", follow_redirects=False)

    return site, seen, build


def logged(session):
    return list(session.scalars(select(AgentRequest).order_by(AgentRequest.received_at)))


def test_humans_pass_through_unlogged_with_clean_forwarding(session, edge):
    _site, seen, build = edge
    response = build().get(
        "/product/trail-runner?ref=email&token=secret",
        headers={
            "user-agent": CHROME,
            "connection": "keep-alive, x-hop",
            "x-hop": "drop-me",
            "x-forwarded-host": "spoofed.example",
        },
    )
    assert response.status_code == 200 and response.text == "<html>Northstar</html>"
    assert response.headers.get_list("set-cookie") == ["a=1; Path=/", "b=2; Path=/"]
    assert "connection" not in response.headers
    upstream = seen[-1]
    assert str(upstream.url) == "http://demo-store:4000/product/trail-runner?ref=email&token=secret"
    assert upstream.headers["x-forwarded-host"] == "store.localhost:8080"
    # The client's hop-by-hop values never reach the origin (httpx manages its own).
    assert "x-hop" not in upstream.headers
    assert upstream.headers.get("connection") != "keep-alive, x-hop"
    assert logged(session) == []


def test_agent_requests_are_logged_without_query_or_raw_ip(session, edge):
    site, _seen, build = edge
    response = build().get("/product/trail-runner?token=secret", headers={"user-agent": CHATGPT})
    assert response.status_code == 200
    [row] = logged(session)
    assert (row.site_id, row.agent, row.agent_kind, row.served_by) == (
        site.id,
        "ChatGPT-User",
        "agent",
        "origin",
    )
    assert row.path == "/product/trail-runner" and row.method == "GET" and row.status == 200
    assert row.response_bytes == len(b"<html>Northstar</html>") and row.duration_ms >= 0
    assert "secret" not in row.path and "testclient" not in row.client_hash
    assert len(row.client_hash) == 64 and row.action is None


def test_crawlers_get_the_same_origin_content_and_are_logged_as_crawlers(session, edge):
    _site, _seen, build = edge
    client = build()
    human = client.get("/", headers={"user-agent": CHROME})
    crawler = client.get("/", headers={"user-agent": GOOGLEBOT})
    assert crawler.text == human.text  # Never cloak search crawlers.
    [row] = logged(session)
    assert (row.agent, row.agent_kind, row.served_by) == ("Googlebot", "crawler", "origin")


def test_origin_redirects_stay_on_the_public_host(edge):
    _site, _seen, build = edge
    response = build().get("/old", headers={"user-agent": CHROME})
    assert response.status_code == 302
    assert response.headers["location"] == "http://store.localhost:8080/new"


def test_unreachable_origin_returns_error_envelope_and_logs_agents(session, edge):
    _site, _seen, build = edge
    response = build().get("/boom", headers={"user-agent": CHATGPT})
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "upstream_unavailable"
    [row] = logged(session)
    assert (row.status, row.served_by) == (502, "router")


def test_unknown_or_invalid_hosts_are_rejected(edge):
    _site, _seen, build = edge
    client = build()
    unknown = client.get("/", headers={"host": "other.localhost"})
    assert unknown.status_code == 404 and unknown.json()["error"]["code"] == "unknown_site"
    invalid = client.get("/", headers={"host": "bad host"})
    assert invalid.status_code == 400
    assert client.get("/_agentlane/health", headers={"host": "anything"}).json() == {"status": "ok"}


def test_logging_failures_never_block_proxying(session, edge):
    _site, _seen, build = edge

    class BrokenSink:
        def write(self, events):
            raise RuntimeError("log store down")

    response = build(sink=BrokenSink()).get("/", headers={"user-agent": CHATGPT})
    assert response.status_code == 200 and response.text == "<html>Northstar</html>"


@pytest.mark.parametrize(
    "origin",
    [
        "http://localhost:4000",
        "http://10.0.0.5",
        "https://shop.example.com/store",
        "https://user:pass@shop.example.com",
        "https://shop.example.com?x=1",
        "ftp://shop.example.com",
    ],
)
def test_origins_must_be_public_bare_http_origins(origin, monkeypatch):
    monkeypatch.setattr(get_settings(), "edge_allow_private_origins", False)
    with pytest.raises(ValueError):
        validate_origin(origin, get_settings())


def test_site_registration_normalizes_hosts_and_rejects_duplicates(session, monkeypatch):
    monkeypatch.setattr(get_settings(), "edge_allow_private_origins", False)
    assert (
        validate_origin("https://Shop.Example.com/", get_settings()) == "https://shop.example.com"
    )
    assert normalize_host("Store.Example.com:443") == "store.example.com"
    with pytest.raises(ValueError):
        normalize_host("[::1]")
    register_site(session, get_settings(), "shop.example.com", "https://origin.example.com", "S")
    with pytest.raises(ValueError, match="already registered"):
        register_site(
            session, get_settings(), "SHOP.example.com", "https://origin.example.com", "S"
        )
