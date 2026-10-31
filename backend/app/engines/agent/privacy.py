"""Bounded best-effort redaction; browser state and input values are never observed."""

import re
from urllib.parse import urlsplit, urlunsplit

_PATTERNS = [
    r"hf_[A-Za-z0-9]+",
    r"(?i)bearer\s+\S+",
    r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}",
    r"(?i)(?:api[_-]?key|token|password|secret)\s*[:=]\s*[^\s,;]+",
    r"\b[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]+\b",
]


def redact(value: str, limit: int = 2000) -> str:
    value = value.replace("\x00", "")
    for pattern in _PATTERNS:
        value = re.sub(pattern, "[REDACTED]", value)
    return value[:limit]


def public_url(url: str) -> str:
    parts = urlsplit(url)
    return redact(urlunsplit((parts.scheme, parts.netloc, parts.path, "", "")), 2048)


def sanitize(value):
    if isinstance(value, str):
        return redact(value, 12000)
    if isinstance(value, dict):
        return {key: sanitize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    return value
