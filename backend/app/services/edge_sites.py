"""Register customer hosts for the edge router. Origins are validated once, here."""

import re
from urllib.parse import urlsplit

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.engines.crawling.urls import URLValidator
from app.models.domain import EdgeSite
from app.repositories.edge import EdgeRecords

HOST = re.compile(r"^(?=.{1,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)*[a-z0-9-]{1,63}$")


def normalize_host(value: str) -> str:
    """Lowercase host without port or trailing dot, as matched against the Host header."""
    host = (value or "").strip().lower().rstrip(".")
    if host.startswith("["):  # IPv6 literals are not customer hosts.
        raise ValueError("Use a host name, not an IP address")
    host = host.split(":", 1)[0]
    if not HOST.match(host):
        raise ValueError("Enter a valid host name")
    return host


def validate_origin(value: str, settings: Settings) -> str:
    """Public HTTP(S) origin without path, query or credentials.

    Private origins (such as the demo store on the Docker network) are accepted only
    when `edge_allow_private_origins` is enabled for local development.
    """
    parts = urlsplit((value or "").strip())
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError("Use an http(s) origin such as https://shop.example.com")
    if parts.username or parts.password or parts.query or parts.fragment:
        raise ValueError("Origins cannot contain credentials, queries or fragments")
    if parts.path not in ("", "/"):
        raise ValueError("Origins cannot contain a path")
    origin = f"{parts.scheme}://{parts.netloc.lower()}"
    if not settings.edge_allow_private_origins:
        # Public host names on standard ports only. The router also connects through the
        # DNS-validated transport, so a name that later resolves privately is refused.
        URLValidator.normalize(origin + "/")
    return origin


def register_site(session: Session, settings: Settings, host: str, origin: str, name: str):
    records = EdgeRecords(session)
    host = normalize_host(host)
    if records.site_by_host(host):
        raise ValueError(f"{host} is already registered")
    site = records.add_site(
        EdgeSite(host=host, origin_url=validate_origin(origin, settings), name=name.strip()[:200])
    )
    session.commit()
    return site
