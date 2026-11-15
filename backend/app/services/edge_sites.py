"""Register customer hosts for the edge router. Origins are validated once, here."""

import re
from urllib.parse import urlsplit

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.engines.crawling.urls import URLValidator
from app.engines.variants.actions import DeliveryRules
from app.models.domain import EdgeSite
from app.repositories.edge import EdgeRecords
from app.repositories.site_jobs import JobRecords

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


class SiteBusy(Exception):
    pass


def _existing(session: Session, host: str) -> EdgeSite:
    site = EdgeRecords(session).site_by_host(normalize_host(host))
    if site is None:
        raise LookupError(f"{host} is not registered")
    return site


def site_settings(site: EdgeSite) -> dict:
    return {
        "host": site.host,
        "name": site.name,
        "origin": site.origin_url,
        "routing_enabled": site.routing_enabled,
        "delivery_rules": site.delivery_rules,
    }


def update_site(
    session: Session,
    settings: Settings,
    host: str,
    name: str | None = None,
    origin: str | None = None,
    routing_enabled: bool | None = None,
) -> EdgeSite:
    """The public host is the routing key and cannot change; register a new site instead."""
    site = _existing(session, host)
    if name is not None:
        site.name = name.strip()[:200]
    if origin is not None:
        site.origin_url = validate_origin(origin, settings)
    if routing_enabled is not None:
        site.routing_enabled = routing_enabled
    session.commit()
    return site


def set_delivery_rules(session: Session, host: str, rules: DeliveryRules | None) -> EdgeSite:
    site = _existing(session, host)
    site.delivery_rules = rules.model_dump() if rules else None
    session.commit()
    return site


def remove_site(session: Session, host: str) -> None:
    """Delete a site and, by cascade, its logs, sessions, versions, jobs and QA runs."""
    site = _existing(session, host)
    if JobRecords(session).has_active(site.id):
        raise SiteBusy("Wait for the running job to finish before removing this site")
    session.delete(site)
    session.commit()
