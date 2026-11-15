"""Agent actions over the published catalog, as plain functions and an MCP tool server.

Actions read the parity-checked catalog of the published variant. Delivery estimates use
rules the site owner configured explicitly; AgentLane never calls a login-gated endpoint
or performs checkout, payment or account actions on an agent's behalf.
"""

import json
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.engines.variants.contracts import Catalog

MCP_PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26")


class ActionError(ValueError):
    def __init__(self, code: str, message: str, status: int = 422):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


class DeliveryEstimate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prefixes: list[str] = Field(min_length=1, max_length=200)
    estimate: str = Field(min_length=1, max_length=80)


class DeliveryRules(BaseModel):
    """Owner-approved delivery data; configured per site, never scraped from a login wall."""

    model_config = ConfigDict(extra="forbid")
    pin_pattern: str = Field(default=r"^\d{6}$", max_length=60)
    estimates: list[DeliveryEstimate] = Field(default_factory=list, max_length=50)
    default_estimate: str = Field(min_length=1, max_length=80)
    free_delivery_over: float | None = Field(default=None, ge=0)


class SearchInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    q: str | None = Field(default=None, max_length=120)
    size: str | None = Field(default=None, max_length=20)
    max_price: float | None = Field(default=None, ge=0)
    limit: int = Field(default=10, ge=1, le=25)


class ProductInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slug: str = Field(min_length=1, max_length=120)


class DeliveryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pin: str = Field(min_length=1, max_length=20)


def _summary(product, currency: str) -> dict:
    return {
        "slug": product.slug,
        "name": product.name,
        "price": product.price,
        "currency": currency,
        "url": product.path,
        "sizes_in_stock": [s.size for s in product.sizes if s.in_stock],
        "sizes_unknown": [s.size for s in product.sizes if s.in_stock is None],
    }


def search_products(catalog: Catalog, params: SearchInput, as_of: str) -> dict:
    words = [w for w in re.split(r"\W+", (params.q or "").lower()) if w]
    results = []
    for product in catalog.products:
        haystack = " ".join(
            filter(None, [product.name, product.category, product.description])
        ).lower()
        if words and not all(word in haystack for word in words):
            continue
        if params.max_price is not None and product.price > params.max_price:
            continue
        if params.size is not None and not any(
            s.size == params.size and s.in_stock is not False for s in product.sizes
        ):
            continue
        results.append(_summary(product, catalog.currency))
    return {"results": results[: params.limit], "total": len(results), "as_of": as_of}


def get_product(catalog: Catalog, params: ProductInput, as_of: str) -> dict:
    for product in catalog.products:
        if product.slug == params.slug:
            return {
                **_summary(product, catalog.currency),
                "category": product.category,
                "description": product.description,
                "sizes": [s.model_dump() for s in product.sizes],
                "as_of": as_of,
            }
    raise ActionError("product_not_found", "No product with that slug", 404)


def check_delivery(rules: DeliveryRules | None, params: DeliveryInput) -> dict:
    if rules is None:
        raise ActionError("delivery_unavailable", "Delivery estimates are not configured", 404)
    pin = params.pin.strip()
    if not re.fullmatch(rules.pin_pattern, pin):
        raise ActionError("invalid_pin", "Enter a valid PIN code")
    estimate = next(
        (e.estimate for e in rules.estimates if any(pin.startswith(p) for p in e.prefixes)),
        rules.default_estimate,
    )
    return {"pin": pin, "estimate": estimate, "free_delivery_over": rules.free_delivery_over}


TOOLS = [
    {
        "name": "search_products",
        "description": "Search products by text, size and maximum price.",
        "inputSchema": SearchInput.model_json_schema(),
        "model": SearchInput,
    },
    {
        "name": "get_product",
        "description": "Get one product's price, sizes and availability by slug.",
        "inputSchema": ProductInput.model_json_schema(),
        "model": ProductInput,
    },
    {
        "name": "check_delivery",
        "description": "Get the delivery estimate for a PIN code. No login needed.",
        "inputSchema": DeliveryInput.model_json_schema(),
        "model": DeliveryInput,
    },
]
_TOOLS = {tool["name"]: tool for tool in TOOLS}


def run_tool(name: str, arguments: dict, catalog: Catalog, rules, as_of: str) -> dict:
    tool = _TOOLS.get(name)
    if tool is None:
        raise ActionError("unknown_tool", f"Unknown tool {name}", 404)
    try:
        params = tool["model"].model_validate(arguments or {})
    except ValidationError as exc:
        raise ActionError("invalid_arguments", exc.errors()[0]["msg"]) from exc
    if name == "search_products":
        return search_products(catalog, params, as_of)
    if name == "get_product":
        return get_product(catalog, params, as_of)
    return check_delivery(rules, params)


def handle_mcp(message: Any, store_name: str, catalog: Catalog, rules, as_of: str):
    """One JSON-RPC 2.0 message for the MCP Streamable HTTP transport.

    Returns (response or None for notifications, tool name or None for logging).
    """
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
        return _rpc_error(None, -32600, "Invalid request"), None
    method, request_id = message.get("method"), message.get("id")
    params = message.get("params") if isinstance(message.get("params"), dict) else {}
    if request_id is None:
        return None, None  # Notifications such as notifications/initialized.
    if method == "initialize":
        requested = params.get("protocolVersion")
        version = requested if requested in MCP_PROTOCOL_VERSIONS else MCP_PROTOCOL_VERSIONS[0]
        return _rpc_result(
            request_id,
            {
                "protocolVersion": version,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": f"AgentLane · {store_name}"[:100], "version": "0.1.0"},
                "instructions": "Read-only store tools. Prices and stock are as of the last "
                "published snapshot; the store's checkout is authoritative.",
            },
        ), None
    if method == "ping":
        return _rpc_result(request_id, {}), None
    if method == "tools/list":
        tools = [{k: v for k, v in t.items() if k != "model"} for t in TOOLS]
        return _rpc_result(request_id, {"tools": tools}), None
    if method == "tools/call":
        name = params.get("name")
        try:
            result = run_tool(str(name), params.get("arguments") or {}, catalog, rules, as_of)
        except ActionError as exc:
            return _rpc_result(
                request_id,
                {"content": [{"type": "text", "text": exc.message}], "isError": True},
            ), str(name)[:80]
        return _rpc_result(
            request_id,
            {
                "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}],
                "structuredContent": result,
            },
        ), str(name)
    return _rpc_error(request_id, -32601, "Method not found"), None


def _rpc_result(request_id, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _rpc_error(request_id, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}
