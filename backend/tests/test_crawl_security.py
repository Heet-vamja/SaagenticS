import asyncio
import socket
from unittest.mock import AsyncMock

import httpx
import pytest
from httpcore._backends.anyio import AnyIOBackend

from app.core.config import Settings
from app.engines.crawling.transport import Fetcher, SafeTransport, ValidatedBackend, public_address
from app.engines.crawling.urls import URLValidator


def run(coroutine):
    return asyncio.run(coroutine)


def test_normalization_and_scope():
    scope = URLValidator("https://EXAMPLE.com:443/a/../")
    assert scope.start == "https://example.com/"
    assert scope.accept("/a/%7e#fragment") == "https://example.com/a/~"
    assert scope.accept("/a/%2e%2e/b") == "https://example.com/b"
    assert scope.accept("https://example.com./a") == "https://example.com/a"
    for value in [
        "https://sub.example.com",
        "https://evil.com",
        "//evil.com",
        "javascript:x",
        "data:text/html,x",
        "file:///etc/passwd",
        "/logout",
        "/item/delete?id=1",
        "https://example.com:8080",
        "https://user:pass@example.com",
    ]:
        with pytest.raises(ValueError):
            scope.accept(value)
    assert URLValidator("https://example.com", True).accept("https://sub.example.com/")


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost",
        "http://127.0.0.1",
        "http://10.1.2.3",
        "http://169.254.169.254",
        "http://[::1]",
        "http://[fe80::1]",
    ],
)
def test_reject_local_urls(url):
    with pytest.raises(ValueError):
        URLValidator(url)


@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1",
        "10.0.0.1",
        "169.254.169.254",
        "168.63.129.16",
        "0.0.0.0",
        "224.0.0.1",
        "192.0.2.1",
        "::1",
        "fc00::1",
        "fe80::1",
        "::ffff:8.8.8.8",
        "2002:0808:0808::1",
        "ff02::1",
    ],
)
def test_block_nonpublic_and_transition_addresses(ip):
    assert not public_address(ip)


def test_dns_is_pinned_and_mixed_answers_denied(monkeypatch):
    async def scenario():
        loop = asyncio.get_running_loop()
        dns = AsyncMock(
            return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))]
        )
        monkeypatch.setattr(loop, "getaddrinfo", dns)
        connect = AsyncMock(return_value="stream")
        monkeypatch.setattr(AnyIOBackend, "connect_tcp", connect)
        assert await ValidatedBackend().connect_tcp("example.com", 443, 1) == "stream"
        assert connect.call_args.args[:2] == ("8.8.8.8", 443)
        # A rebinding answer on the next connection is revalidated, never passed through.
        dns.return_value.append((socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443)))
        with pytest.raises(ValueError):
            await ValidatedBackend().connect_tcp("example.com", 443, 1)
        assert connect.await_count == 1

    run(scenario())


def test_transport_uses_validated_backend_and_keeps_tls_origin(monkeypatch):
    class Stream:
        def __init__(self):
            self.sni = None
            self.writes = []
            self.sent = False

        async def start_tls(self, ssl_context, server_hostname, timeout):
            self.sni = server_hostname
            assert ssl_context.check_hostname
            return self

        async def write(self, buffer, timeout):
            self.writes.append(buffer)

        async def read(self, max_bytes, timeout):
            if self.sent:
                return b""
            self.sent = True
            return b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok"

        async def aclose(self):
            pass

        def get_extra_info(self, info):
            return None

    async def scenario():
        stream = Stream()
        connect = AsyncMock(return_value=stream)
        monkeypatch.setattr(AnyIOBackend, "connect_tcp", connect)
        monkeypatch.setattr(
            asyncio.get_running_loop(),
            "getaddrinfo",
            AsyncMock(return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))]),
        )
        transport = SafeTransport(3)
        async with httpx.AsyncClient(transport=transport, trust_env=False) as client:
            assert (await client.get("https://example.com/")).text == "ok"
        assert connect.call_args.args[0] == "8.8.8.8"
        assert stream.sni == "example.com"
        assert b"Host: example.com" in b"".join(stream.writes)

    run(scenario())


def fetcher(handler, **overrides):
    settings = Settings(**overrides)
    scope = URLValidator("https://example.com")
    return Fetcher(scope, settings, httpx.MockTransport(handler))


def response(status=200, body=b"", **headers):
    return httpx.Response(status, stream=httpx.ByteStream(body), headers=headers)


def test_redirects_size_timeout_and_proxy(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9999")

    async def scenario():
        calls = []

        def redirect(request):
            calls.append(str(request.url))
            return response(302, location="http://169.254.169.254/")

        f = fetcher(redirect)
        with pytest.raises(ValueError):
            await f.get(f.scope.start, 100)
        assert calls == ["https://example.com/"]
        assert f.client._trust_env is False
        await f.close()
        for handler, error in [
            (lambda r: response(200, b"x" * 101), ValueError),
            (lambda r: response(302, location="/loop"), ValueError),
            (lambda r: response(200, b"x", **{"content-encoding": "gzip"}), ValueError),
        ]:
            f = fetcher(handler)
            with pytest.raises(error):
                await f.get(f.scope.start, 100)
            await f.close()

        async def slow(request):
            await asyncio.sleep(0.05)
            return response()

        f = fetcher(slow, crawl_request_timeout=0.01)
        with pytest.raises(TimeoutError):
            await f.get(f.scope.start, 100)
        await f.close()

    run(scenario())


def test_every_redirect_checks_robots_and_concurrency_is_bounded():
    async def scenario():
        calls = []

        def redirected(request):
            calls.append(request.url.path)
            return response(302, location="/forbidden")

        f = fetcher(redirected, crawl_concurrency=1)
        permit = AsyncMock(side_effect=lambda url: not url.endswith("/forbidden"))
        f.permit = permit
        with pytest.raises(ValueError, match="robots"):
            await f.get(f.scope.start, 100)
        assert calls == ["/"]
        assert permit.await_count == 2
        await f.close()
        running = 0
        peak = 0

        async def slow(request):
            nonlocal running, peak
            running += 1
            peak = max(peak, running)
            await asyncio.sleep(0.01)
            running -= 1
            return response(200, b"ok")

        f = fetcher(slow, crawl_concurrency=3, crawl_min_delay=0)
        await asyncio.gather(*(f.get(f"https://example.com/{i}", 100) for i in range(8)))
        assert peak == 3
        await f.close()

    run(scenario())


def test_dns_timeout_does_not_connect(monkeypatch):
    async def scenario():
        async def slow(*args, **kwargs):
            await asyncio.sleep(0.1)
            return []

        monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", slow)
        connect = AsyncMock()
        monkeypatch.setattr(AnyIOBackend, "connect_tcp", connect)
        with pytest.raises(TimeoutError):
            await ValidatedBackend().connect_tcp("example.com", 443, 0.01)
        connect.assert_not_awaited()

    run(scenario())
