"""HTTPX/HTTPcore adapter: DNS validation is enforced at socket creation.

Only the checked numeric IP is passed to the TCP backend. HTTPcore retains the
original origin for Host, SNI and certificate verification. No second hostname
lookup can select a different destination. All answers must be public.
"""

import asyncio
import ipaddress
import socket
import ssl
import time
from dataclasses import dataclass

import httpcore
import httpx
from httpcore._backends.anyio import AnyIOBackend

from app.core.config import Settings
from app.engines.crawling.urls import URLValidator


def public_address(value: str) -> bool:
    address = ipaddress.ip_address(value.split("%")[0])
    if isinstance(address, ipaddress.IPv6Address) and (
        address.ipv4_mapped or address.sixtofour or address.teredo
    ):
        return False
    # Azure's virtual platform endpoint is publicly numbered but instance-local.
    return (
        address.is_global
        and not address.is_multicast
        and not address.is_reserved
        and address != ipaddress.ip_address("168.63.129.16")
    )


class ValidatedBackend(AnyIOBackend):
    async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        if port not in (80, 443):
            raise ValueError("Unsafe destination port")
        answers = await asyncio.wait_for(
            asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM), timeout
        )
        addresses = list(dict.fromkeys(answer[4][0] for answer in answers))
        if not addresses or not all(public_address(ip) for ip in addresses):
            raise ValueError("DNS returned a non-public destination")
        return await super().connect_tcp(addresses[0], port, timeout, local_address, socket_options)


class SafeTransport(httpx.AsyncHTTPTransport):
    def __init__(self, concurrency: int):
        super().__init__(trust_env=False)
        # HTTPX has no public network_backend argument; versions are bounded and
        # transport tests cover this adapter. The unused initial pool has no sockets.
        self._pool = httpcore.AsyncConnectionPool(
            ssl_context=ssl.create_default_context(),
            network_backend=ValidatedBackend(),
            max_connections=concurrency,
            max_keepalive_connections=0,
            retries=0,
        )


@dataclass
class FetchResult:
    url: str
    status: int
    content_type: str
    body: bytes
    headers: dict[str, str] | None = None
    redirects: list[str] | None = None


class Fetcher:
    def __init__(self, scope: URLValidator, settings: Settings, transport=None):
        self.scope, self.settings = scope, settings
        self.client = httpx.AsyncClient(
            transport=transport or SafeTransport(settings.crawl_concurrency),
            trust_env=False,
            follow_redirects=False,
            timeout=settings.crawl_request_timeout,
            headers={"User-Agent": settings.crawl_user_agent, "Accept-Encoding": "identity"},
        )
        self.permit = None
        self.delay = settings.crawl_min_delay
        self.last_request = 0.0
        self.lock = asyncio.Lock()
        self.semaphore = asyncio.Semaphore(settings.crawl_concurrency)

    async def close(self):
        await self.client.aclose()

    async def get(
        self, url: str, limit: int, robots: bool = True, follow_redirects: bool = True
    ) -> FetchResult:
        redirects = []
        async with asyncio.timeout(self.settings.crawl_request_timeout):
            for hop in range(self.settings.crawl_max_redirects + 1):
                url = self.scope.accept(url)
                if robots and self.permit and not await self.permit(url):
                    raise ValueError("Blocked by robots.txt")
                async with self.semaphore:
                    async with self.lock:
                        await asyncio.sleep(
                            max(0, self.delay - (time.monotonic() - self.last_request))
                        )
                        self.last_request = time.monotonic()
                    # Do not retain cookies or accept user headers/credentials.
                    self.client.cookies.clear()
                    async with self.client.stream("GET", url) as response:
                        if response.status_code in (301, 302, 303, 307, 308):
                            if (
                                hop == self.settings.crawl_max_redirects
                                or "location" not in response.headers
                            ):
                                raise ValueError("Redirect limit or missing Location")
                            destination = self.scope.accept(response.headers["location"], url)
                            if not follow_redirects:
                                return FetchResult(
                                    url, response.status_code, "", b"", {"location": destination}
                                )
                            from app.engines.agent.privacy import public_url

                            redirects.append(public_url(destination))
                            url = destination
                            continue
                        if (
                            response.headers.get("content-encoding", "identity").lower()
                            != "identity"
                        ):
                            raise ValueError("Compressed responses are not supported")
                        body = bytearray()
                        async for chunk in response.aiter_raw(chunk_size=16384):
                            body.extend(chunk)
                            if len(body) > limit:
                                raise ValueError("Response exceeds byte limit")
                        return FetchResult(
                            url,
                            response.status_code,
                            response.headers.get("content-type", ""),
                            bytes(body),
                            dict(response.headers),
                            redirects,
                        )
        raise ValueError("Redirect limit exceeded")
