"""Submission validation only. A future transport must enforce network safety per hop."""

import ipaddress

from pydantic import HttpUrl, TypeAdapter, ValidationError

_http_url = TypeAdapter(HttpUrl)
_blocked_hosts = {"localhost", "metadata.google.internal", "instance-data.ec2.internal"}


def validate_website_url(value: str) -> str:
    try:
        url = _http_url.validate_python(value)
    except ValidationError as exc:
        raise ValueError("Enter a valid HTTP or HTTPS website URL") from exc
    if url.username is not None or url.password is not None:
        raise ValueError("URLs containing credentials are not supported")
    host = (url.host or "").strip("[]").lower().rstrip(".")
    if host in _blocked_hosts or host.endswith((".localhost", ".local", ".internal")):
        raise ValueError("Local and metadata service hostnames are not supported")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        pass  # DNS resolution belongs to the future request layer, not URL submission.
    else:
        if not address.is_global:
            raise ValueError("Only public website addresses are supported")
    return str(url)
