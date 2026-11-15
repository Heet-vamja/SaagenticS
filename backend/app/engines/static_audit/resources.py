"""Bounded discovery-link and code-example measurements; no network or execution."""

import json
import re
from collections import deque
from urllib.parse import urljoin, urlsplit

from app.engines.crawling.urls import URLValidator
from app.engines.static_audit.checks import Check
from app.engines.static_audit.site import llms_measurements

MAX_LINKS = 500
MAX_CANDIDATES = 30
MAX_CODE_BLOCKS = 100
MAX_CATALOG_ENTRIES = 20
CATALOG_PATH = "/.well-known/ai-catalog.json"
PRICING_SEGMENTS = {"pricing", "plans", "prices", "plans-and-pricing", "pricing-plans"}
PRICING_HEADING = re.compile(r"^(?:pricing|plans|plans (?:and|&) pricing)\b", re.IGNORECASE)
PRICE_AMOUNT = re.compile(
    r"[$€£¥₹]\s?\d[\d,.]*|\b\d[\d,.]*\s?(?:USD|EUR|GBP|INR|CAD|AUD)\b", re.IGNORECASE
)
FREE_TIER = re.compile(r"\bfree (?:plan|tier|forever)\b|\bforever free\b", re.IGNORECASE)


def resource_kind(url, rel="", media_type=""):
    path = urlsplit(url).path.lower()
    name = path.rsplit("/", 1)[-1]
    rels = rel.split()
    if "ai-catalog" in rels or path == CATALOG_PATH:
        return "ai_catalog"
    if name == "llms.txt":
        return "llms"
    if name == "llms-full.txt":
        return "markdown"
    if "alternate" in rels and media_type.split(";")[0].strip() == "text/markdown":
        return "markdown_alternate"
    if name in {
        "openapi.json",
        "openapi.yaml",
        "openapi.yml",
        "swagger.json",
        "swagger.yaml",
        "swagger.yml",
    } or ("service-desc" in rel.split() and "openapi" in media_type):
        return "openapi"
    if name == "agents.md":
        return "agents"
    if path.startswith("/.well-known/"):
        return "well_known"
    return None


def candidate(href, base, source, rel="", media_type=""):
    try:
        url = URLValidator.normalize(urljoin(base, str(href)))
        if urlsplit(url).query:  # Never persist or fetch token-bearing query links.
            return None
        kind = resource_kind(url, rel.lower(), media_type.lower())
        if kind:
            return {"url": url, "kind": kind, "source": source}
    except (ValueError, TypeError):
        pass
    return None


def html_resource_links(soup, url):
    base = soup.find("base", href=True)
    try:
        base_url = urljoin(url, str(base["href"])) if base else url
    except ValueError:
        return {"candidates": [], "limited": True}
    nodes = soup.find_all(["a", "link"], href=True, limit=MAX_LINKS + 1)
    result = {}
    filtered = False
    for node in nodes[:MAX_LINKS]:
        rel = node.get("rel") or []
        rel = " ".join(rel) if isinstance(rel, list) else str(rel)
        item = candidate(
            node["href"],
            base_url,
            "html-link" if node.name == "link" else "html-anchor",
            rel,
            str(node.get("type") or ""),
        )
        if item:
            result.setdefault(item["url"], item)
        else:
            try:
                filtered |= bool(
                    resource_kind(
                        urljoin(base_url, str(node["href"])), rel, str(node.get("type") or "")
                    )
                )
            except ValueError:
                filtered = True
    return {
        "candidates": list(result.values())[:MAX_CANDIDATES],
        "limited": filtered or len(nodes) > MAX_LINKS or len(result) > MAX_CANDIDATES,
    }


def header_resource_links(value, url):
    limited = len(value) > 8192
    parts = re.split(r",(?=\s*<)", value[:8192])
    result = {}
    for part in parts[:MAX_LINKS]:
        match = re.match(r"^\s*<([^>]{1,2048})>\s*(.*)$", part)
        if not match:
            continue
        params = {
            key.lower(): val.strip('"')
            for key, val in re.findall(r'(?:^|;)\s*([\w-]+)\s*=\s*("[^"]*"|[^;\s]+)', match[2])
        }
        item = candidate(match[1], url, "http-link", params.get("rel", ""), params.get("type", ""))
        if item:
            result.setdefault(item["url"], item)
        else:
            try:
                limited |= bool(
                    resource_kind(
                        urljoin(url, match[1]), params.get("rel", ""), params.get("type", "")
                    )
                )
            except ValueError:
                limited = True
    return {
        "candidates": list(result.values())[:MAX_CANDIDATES],
        "limited": limited or len(result) > MAX_CANDIDATES or len(parts) > MAX_LINKS,
    }


def code_examples(soup):
    nodes = soup.find_all("pre", limit=MAX_CODE_BLOCKS + 1)
    count, missing = 0, []
    for index, node in enumerate(nodes[:MAX_CODE_BLOCKS], 1):
        code = node.find("code")
        classes = [
            str(c) for element in (node, code) if element for c in (element.get("class") or [])
        ]
        language = next(
            (
                element.get("data-language") or element.get("data-lang")
                for element in (code, node)
                if element and (element.get("data-language") or element.get("data-lang"))
            ),
            "",
        )
        annotated = bool(re.fullmatch(r"[a-zA-Z0-9_+#.-]{1,40}", str(language).strip())) or any(
            re.fullmatch(r"(?:language|lang)-[a-zA-Z0-9_+#.-]{1,40}", token) for token in classes
        )
        if code is None and not annotated:
            continue  # Plain preformatted output is not automatically a code example.
        if not (code or node).get_text(strip=True):
            continue
        count += 1
        if not annotated and len(missing) < 10:
            missing.append({"block": index, "reason": "No language annotation on pre/code"})
    return {
        "count": count,
        "missing_language": missing,
        "limited": len(nodes) > MAX_CODE_BLOCKS,
        "scope": "HTML block-code annotations only; authoring fences and language correctness are not verified",
    }


def code_example_check(url, data):
    missing = data.get("missing_language", [])
    status = (
        "FAIL"
        if missing
        else "UNKNOWN"
        if data.get("limited")
        else "PASS"
        if data.get("count")
        else "NOT_APPLICABLE"
    )
    return Check(
        "content.code_examples",
        "Readability",
        status,
        "Code examples need language annotations"
        if missing
        else "Code-example annotations sampled",
        "Inspects nonempty HTML pre/code blocks. Inline code and plain preformatted output are excluded. This does not validate code correctness or prove Markdown fencing.",
        "Add an accurate language-... class or data-language to each block-code example. In Markdown, use fenced blocks with the appropriate language. Preserve code, output and layout.",
        "LOW",
        url,
        data,
        0,
    )


def validate_resource(kind, body, content_type):
    """Return PASS/FAIL/UNKNOWN for the supported, explicitly limited syntax subset."""
    try:
        text = body.decode("utf-8-sig", errors="strict").strip()
        if not text or "\x00" in text:
            return "FAIL", "Empty or invalid text content"
        if (
            text.lower().startswith(("<!doctype html", "<html"))
            or "text/html" in content_type.lower()
        ):
            return "FAIL", "Linked resource returned HTML rather than its declared document"
        if kind == "llms":
            result = llms_measurements(body)
            return (
                ("PASS", "Supported llms.txt structural subset parsed")
                if result["valid"]
                else ("FAIL", "; ".join(result["errors"])[:300])
            )
        if kind in {"agents", "markdown", "markdown_alternate"}:
            return (
                "PASS",
                "Nonempty UTF-8 document retrieved; instructions were not executed or verified",
            )
        if "json" not in content_type.lower() and not text.startswith(("{", "[")):
            return (
                "UNKNOWN",
                "Document format is outside supported JSON validation (including YAML)",
            )
        data = json.loads(text)
        if kind == "mcp_server_card" and not isinstance(data, dict):
            return "FAIL", "Server card is not a JSON object"
        if kind == "openapi":
            if not isinstance(data, dict) or not isinstance(
                data.get("openapi", data.get("swagger")), str
            ):
                return "FAIL", "JSON document is missing an OpenAPI/Swagger version string"
            if not any(
                isinstance(data.get(key), dict) for key in ("paths", "webhooks", "components")
            ):
                return "FAIL", "JSON contract has no supported paths/webhooks/components object"
            return (
                "PASS",
                "Basic JSON contract fields parsed; operations and authentication were not tested",
            )
        return (
            "PASS",
            "JSON syntax parsed; resource-specific claims and capabilities were not verified",
        )
    except (UnicodeError, ValueError, RecursionError):
        return "FAIL", "Document could not be parsed safely as the expected text/JSON subset"


def pricing_measurements(soup, url, text):
    """Identify a pricing page by URL or main heading and count price text in initial HTML."""
    segments = {segment.lower() for segment in urlsplit(url).path.split("/") if segment}
    heading = soup.find("h1")
    heading = heading.get_text(" ", strip=True)[:80] if heading else ""
    if not (segments & PRICING_SEGMENTS or PRICING_HEADING.match(heading)):
        return {"pricing_page": False}
    return {
        "pricing_page": True,
        "amounts": min(len(PRICE_AMOUNT.findall(text)), 100),
        "free_tier": bool(FREE_TIER.search(text)),
        "scope": "Initial HTML text only; images, calculators, forms and scripts are not read",
    }


def pricing_check(url, data):
    if not data.get("pricing_page"):
        return None
    observed = bool(data.get("amounts") or data.get("free_tier"))
    return Check(
        "content.pricing_text",
        "Readability",
        "PASS" if observed else "FAIL",
        "Pricing page shows prices as text"
        if observed
        else "Pricing page has no prices in its initial HTML",
        "Inspects the initial HTML text of a page identified as pricing by its URL or main heading. Currency amounts or an explicit free plan count as observed pricing text. Prices in images, calculators, sales forms or JavaScript-only content are not found, and the completeness or accuracy of plans, limits and prices is not verified.",
        "Publish plans, the free tier and limits as text in the server-rendered HTML of a first-party pricing page. Keep images and calculators as supplements, not the only source. Never invent or change prices.",
        "MEDIUM",
        url,
        data,
        0,
    )


def pricing_presence_check(start, measurements):
    measured = [
        m["pricing"]
        for m in measurements
        if isinstance(m, dict) and isinstance(m.get("pricing"), dict)
    ]
    if not measured or any(m.get("pricing_page") for m in measured):
        return []  # Old scans were not measured; identified pricing pages report per page.
    return [
        Check(
            "content.pricing_text",
            "Readability",
            "INFO",
            "No pricing page identified in the sample",
            "No sampled page had a pricing URL or main heading. Absence from a bounded sample does not establish that the site has no public pricing.",
            "If you offer self-serve plans, publish them on a first-party pricing page linked from your main navigation, with prices as HTML text.",
            "LOW",
            start,
            {"pages_measured": len(measured)},
            0,
        )
    ]


def catalog_entries(data):
    """Bounded walk for url/href values with an optional media type.

    The reviewed AgentReady spec does not define a catalog schema, so entries are
    recorded generically and never treated as verified capabilities.
    """
    if isinstance(data, dict) and isinstance(data.get("entries"), list):
        # Published catalogs use {"specVersion", "entries": [{"type", "url", ...}]}.
        data = [entry for entry in data["entries"][:500] if isinstance(entry, dict)]
        return [
            {"url": entry["url"][:2048], "type": str(entry.get("type") or "")[:120]}
            for entry in data
            if isinstance(entry.get("url"), str)
        ][:MAX_CATALOG_ENTRIES]
    found, queue, visited = [], deque([data]), 0
    while queue and len(found) < MAX_CATALOG_ENTRIES and visited < 2000:
        node = queue.popleft()
        visited += 1
        if isinstance(node, dict):
            link = next((node[k] for k in ("url", "href") if isinstance(node.get(k), str)), None)
            media = next(
                (
                    node[k]
                    for k in ("type", "mediaType", "media_type", "contentType")
                    if isinstance(node.get(k), str)
                ),
                "",
            )
            if link:
                found.append({"url": link[:2048], "type": media[:120]})
            queue.extend(v for v in node.values() if isinstance(v, (dict, list)))
        elif isinstance(node, list):
            queue.extend(v for v in node[:500] if isinstance(v, (dict, list)))
    return found


def inspect_catalog(status, body, content_type):
    """Classify the single AI Catalog probe as PRESENT, ABSENT, FAIL or UNKNOWN."""
    if status in (404, 410):
        return "ABSENT", "No AI Catalog at the well-known path", []
    if status != 200:
        return "UNKNOWN", "The catalog path did not return a supported success response", []
    text = body.decode("utf-8-sig", errors="replace").strip()
    if text.startswith("<") or not ("json" in content_type.lower() or text.startswith(("{", "["))):
        return "ABSENT", "The well-known path returned a page, not a JSON catalog", []
    try:
        data = json.loads(text)
    except (ValueError, RecursionError):
        return "FAIL", "AI Catalog JSON could not be parsed", []
    entries = catalog_entries(data) if isinstance(data, (dict, list)) else []
    if not entries:
        return "FAIL", "AI Catalog parsed but lists no resource URLs", []
    version = data.get("specVersion") if isinstance(data, dict) else None
    detail = "JSON parsed and resource URLs listed; listed resources were not verified"
    if isinstance(version, str):
        detail += f" (declares specVersion {version[:20]})"
    return "PRESENT", detail, entries


def catalog_resources(entries, base):
    """Resolve catalog entries into same-format candidates; query URLs are never kept."""
    result = []
    for entry in entries:
        try:
            url = URLValidator.normalize(urljoin(base, entry["url"]))
        except (ValueError, TypeError):
            continue
        if urlsplit(url).query:
            continue
        media = entry["type"].lower()
        kind = (
            "mcp_server_card"
            if "mcp-server-card" in media
            else "openapi"
            if "openapi" in media
            else resource_kind(url, "", media) or "other"
        )
        result.append({"url": url, "kind": kind, "type": entry["type"], "source": "ai-catalog"})
    return result


def _diagnostic_check(
    rule, bucket, status, title, description, recommendation, severity, url, evidence
):
    return Check(
        rule, bucket, status, title, description, recommendation, severity, url, evidence, 0
    )


def agentready_checks(start, data):
    """AI Catalog, MCP server card, OpenAPI contract and Markdown alternate signals."""
    resources = data.get("resources", [])
    catalog = data.get("ai_catalog", {})
    outcome = catalog.get("result", "UNKNOWN")
    advertised = bool(catalog.get("advertised"))
    status, title = {
        "PRESENT": ("PASS", "AI Catalog published and linked")
        if advertised
        else ("FAIL", "AI Catalog is not linked from sampled pages"),
        "ABSENT": ("INFO", "No AI Catalog published"),
        "FAIL": ("FAIL", "AI Catalog needs review"),
    }.get(outcome, ("UNKNOWN", "AI Catalog could not be checked"))
    checks = [
        _diagnostic_check(
            "discovery.ai_catalog",
            "Access",
            status,
            title,
            'One read-only request to /.well-known/ai-catalog.json, plus rel="ai-catalog" links in sampled HTML and HTTP Link headers. The catalog is optional. The reviewed specification defines no catalog schema, so only JSON syntax and listed resource URLs are recorded; listed resources are not verified.',
            'If you publish agent-facing resources, list them in /.well-known/ai-catalog.json and link it from the homepage head with <link rel="ai-catalog"> and an HTTP Link header. Do not publish an empty catalog to satisfy a checklist.',
            "LOW",
            start,
            catalog,
        )
    ]
    card = data.get("mcp_server_card", {})
    outcome = card.get("result", "UNKNOWN")
    status, title = {
        "PASS": ("PASS", "MCP server card retrieved"),
        "FAIL": ("FAIL", "Catalog-listed MCP server card needs review"),
        "ABSENT": ("INFO", "No MCP server card listed"),
    }.get(outcome, ("UNKNOWN", "MCP server card could not be checked"))
    checks.append(
        _diagnostic_check(
            "discovery.mcp_server_card",
            "Actionability",
            status,
            title,
            "Only a server card listed in the AI Catalog with an MCP server-card media type is fetched; reserved endpoint paths are not guessed. A JSON object counts as retrieved. The server-card format is still a draft, and server capabilities and transport are not tested.",
            "If you run an MCP server, publish its server card and list it in /.well-known/ai-catalog.json with type application/mcp-server-card+json. Keep the card accurate to the deployed server.",
            "LOW",
            card.get("url", start),
            card,
        )
    )
    contracts = [item for item in resources if item.get("kind") == "openapi"]
    results = {item.get("result") for item in contracts}
    status = (
        "PASS"
        if "PASS" in results
        else "FAIL"
        if "FAIL" in results
        else "UNKNOWN"
        if contracts or data.get("resources_limited") or not data.get("html_inspected")
        else "INFO"
    )
    checks.append(
        _diagnostic_check(
            "api.openapi_contract",
            "Actionability",
            status,
            {
                "PASS": "Linked OpenAPI contract parsed",
                "FAIL": "Linked OpenAPI contract needs review",
                "INFO": "No linked OpenAPI contract observed",
            }.get(status, "OpenAPI contract could not be checked"),
            "Only OpenAPI documents linked from sampled pages, HTTP Link headers or the AI Catalog are fetched; common paths are not guessed. A basic JSON contract structure counts as parsed. Operations, authentication and completeness are not tested, and whether the product offers a public API is not determined.",
            'If you offer a public API, publish its OpenAPI contract and link it from your developer docs, an HTTP Link header (rel="service-desc") or the AI Catalog.',
            "MEDIUM",
            start,
            {"contracts": contracts[:5], "sample_limited": data.get("resources_limited", False)},
        )
    )
    mirrors = [item for item in resources if item.get("kind") == "markdown_alternate"]
    advertised = data.get("markdown_alternates", 0)
    results = {item.get("result") for item in mirrors}
    status = (
        "PASS"
        if "PASS" in results
        else "FAIL"
        if "FAIL" in results
        else "UNKNOWN"
        if advertised or data.get("resources_limited") or not data.get("html_inspected")
        else "INFO"
    )
    checks.append(
        _diagnostic_check(
            "discovery.markdown_alternate",
            "Readability",
            status,
            {
                "PASS": "Markdown alternate advertised and retrieved",
                "FAIL": "Advertised Markdown alternate needs review",
                "INFO": "No Markdown alternate advertised",
            }.get(status, "Markdown alternate could not be checked"),
            'Looks for <link rel="alternate" type="text/markdown"> in sampled HTML and equivalent HTTP Link headers. At most one advertised mirror is fetched and must return nonempty non-HTML text. Agreement with the HTML page is not verified. Markdown mirrors are optional; the HTML page should work first.',
            'Optionally advertise a Markdown version of documentation pages with <link rel="alternate" type="text/markdown" href="..."> and keep it in sync with the HTML.',
            "LOW",
            start,
            {"advertised": advertised, "sampled": mirrors[:1]},
        )
    )
    return checks


def diagnostic_checks(start, metadata):
    result = []
    data = metadata.get("diagnostics")
    if not isinstance(data, dict):
        return result  # Old scans were not measured; do not manufacture new outcomes.
    # Markdown mirrors and catalog entries have their own checks, not AR-READ-06 links.
    resources = [
        item
        for item in data.get("resources", [])
        if item.get("kind") != "markdown_alternate" and item.get("source") != "ai-catalog"
    ]
    if not resources:
        absent = (
            data.get("html_inspected")
            and not data.get("resources_limited")
            and not data.get("linked_candidates")
        )
        result.append(
            Check(
                "discovery.linked_resources",
                "Access",
                "INFO" if absent else "UNKNOWN",
                "No linked discovery resources observed"
                if absent
                else "Linked-resource validation was not completed",
                "Only the sampled HTML and HTTP Link headers were inspected. Absence is informational, not a readiness failure.",
                "Link existing llms.txt, AGENTS.md, OpenAPI and discovery metadata from pages agents already visit. Do not publish empty files to satisfy a checklist.",
                "LOW",
                start,
                {"sample_limited": data.get("resources_limited", False)},
                0,
            )
        )
    for item in resources:
        result.append(
            Check(
                "discovery.linked_resources",
                "Access",
                item.get("result", "UNKNOWN"),
                "Linked discovery resource needs review"
                if item.get("result") == "FAIL"
                else "Linked discovery resource inspected",
                "A resource was linked in sampled page HTML or an HTTP Link header. Only reachability and a bounded syntax subset were checked.",
                "Repair the observed link or document format. Keep private resources protected and confirm public resources are linked from relevant pages.",
                "MEDIUM",
                item.get("url", start),
                item,
                0,
            )
        )
    if data.get("resources_limited"):
        result.append(
            Check(
                "discovery.linked_resources",
                "Access",
                "UNKNOWN",
                "Linked-resource sample was limited",
                "The resource count or diagnostic time budget prevented a complete sample.",
                url=start,
                evidence={"sample_limited": True},
                weight=0,
            )
        )
    probe = data.get("missing_path", {})
    result.append(
        Check(
            "http.missing_path",
            "Reliability",
            probe.get("result", "UNKNOWN"),
            "Missing-path probe returned a success response"
            if probe.get("result") == "FAIL"
            else "Missing-path behavior sampled",
            "At most one random, unlinked path is requested. A successful HTML response may indicate a soft 404. Disabled, skipped, redirected, restricted and transient responses remain inconclusive; review the recorded detail.",
            "Return HTTP 404 for unknown paths. Preserve valid application routes and intentional redirects. Verify with a fresh unlinked URL after deployment.",
            "MEDIUM",
            start,
            probe,
            0,
        )
    )
    if "ai_catalog" in data:  # Scans before the AgentReady 2.0.1 mapping were not measured.
        result.extend(agentready_checks(start, data))
    return result
