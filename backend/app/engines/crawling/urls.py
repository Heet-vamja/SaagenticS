"""URL scope and submission checks; socket enforcement lives in transport.py."""

import re
from urllib.parse import unquote, urljoin, urlsplit, urlunsplit

from app.core.urls import validate_website_url


class URLValidator:
    def __init__(self, start: str, allow_subdomains: bool = False):
        self.start = self.normalize(start)
        self.host = urlsplit(self.start).hostname
        self.allow_subdomains = allow_subdomains

    @staticmethod
    def normalize(value: str) -> str:
        value = validate_website_url(value)
        parts = urlsplit(value)
        if parts.port not in (None, 80 if parts.scheme == "http" else 443):
            raise ValueError("Only standard HTTP(S) ports are allowed")
        path = re.sub(r"%[0-9a-fA-F]{2}", lambda m: m[0].upper(), parts.path or "/")
        path = re.sub(
            r"%([0-9A-F]{2})",
            lambda m: (
                chr(int(m[1], 16))
                if chr(int(m[1], 16))
                in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._~"
                else m[0]
            ),
            path,
        )
        # Resolve dot segments after decoding unreserved characters.
        segments = []
        for segment in path.split("/"):
            if segment == "..":
                if segments:
                    segments.pop()
            elif segment != ".":
                segments.append(segment)
        path = "/".join(segments) or "/"
        host = parts.hostname.lower().rstrip(".")
        authority = f"[{host}]" if ":" in host else host
        return urlunsplit((parts.scheme, authority, path, parts.query, ""))

    def accept(self, value: str, base: str | None = None) -> str:
        url = self.normalize(urljoin(base or self.start, value))
        parts = urlsplit(url)
        if parts.hostname != self.host and not (
            self.allow_subdomains and parts.hostname.endswith("." + self.host)
        ):
            raise ValueError(
                f"Hostname '{parts.hostname}' is outside configured crawl host '{self.host}'. "
                "Use the destination hostname as the project website URL if that is the intended site."
            )
        if re.search(
            r"(?:^|[/_?&=.-])(logout|logoff|delete|remove|unsubscribe|signout)(?:$|[/_?&=.-])",
            unquote(parts.path + "?" + parts.query),
            re.IGNORECASE,
        ):
            raise ValueError("Potential state-changing URL")
        if len(url) > 2048:
            raise ValueError("URL is too long")
        return url
