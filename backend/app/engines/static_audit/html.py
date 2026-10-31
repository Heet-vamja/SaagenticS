"""No HTML is retained. Store bounded, redacted measurements and issue examples."""

import json
import re
from pathlib import Path

from bs4 import BeautifulSoup, Comment

from app.engines.agent.privacy import redact
from app.engines.static_audit.checks import Check

VOCABULARY = json.loads(Path(__file__).with_name("schema_vocabulary.json").read_text())
SCHEMA_TYPES = frozenset(VOCABULARY["types"])
SCHEMA_PROPERTIES = frozenset(VOCABULARY["properties"])

CORE_FIELDS = {
    "Product": ("name",),
    "Article": ("headline", "author"),
    "NewsArticle": ("headline", "author"),
    "BlogPosting": ("headline", "author"),
    "FAQPage": ("mainEntity",),
    "Question": ("name", "acceptedAnswer"),
    "Answer": ("text",),
    "Organization": ("name",),
    "WebSite": ("name", "url"),
    "Offer": ("price", "priceCurrency"),
    "BreadcrumbList": ("itemListElement",),
    "SoftwareApplication": ("name",),
    "Person": ("name",),
}
CHALLENGE = re.compile(
    r"verify (?:that )?you are human|checking your browser|just a moment|cf-chl-|challenge-platform|g-recaptcha|h-captcha|cf-turnstile",
    re.IGNORECASE,
)


def clean_text(soup):
    excluded = {"script", "style", "noscript", "template", "textarea"}
    strings = (
        str(text).strip()
        for text in soup.find_all(string=True)
        if not isinstance(text, Comment)
        and text.parent.name not in excluded
        and not any(parent.name in excluded for parent in text.parents)
    )
    return re.sub(r"\s+", " ", " ".join(strings))[:100_000]


def accessible_name(node, soup):
    if node.get("aria-label", "").strip():
        return node["aria-label"].strip()
    labelled = " ".join(
        soup.find(id=key).get_text(" ", strip=True)
        for key in node.get("aria-labelledby", "").split()[:10]
        if soup.find(id=key)
    )
    if labelled.strip():
        return labelled.strip()
    if node.get("id"):
        label = soup.find("label", attrs={"for": node["id"]})
        if label and label.get_text(strip=True):
            return label.get_text(" ", strip=True)
    wrapper = node.find_parent("label")
    if wrapper and wrapper.get_text(strip=True):
        return wrapper.get_text(" ", strip=True)
    return (
        node.get_text(" ", strip=True)
        or " ".join(str(image.get("alt", "")) for image in node.find_all("img", limit=10))
        or node.get("title", "")
    )


def node_selector(node):
    parts = []
    for _ in range(12):
        if not node or node.name == "[document]":
            break
        siblings = list(node.previous_siblings)
        position = 1 + sum(getattr(sibling, "name", None) == node.name for sibling in siblings)
        parts.append(f"{node.name}:nth-of-type({position})")
        node = node.parent
    return " > ".join(reversed(parts))[:700]


def semantic_measurements(soup):
    missing = {"buttons": [], "inputs": [], "links": [], "clickable_divs": []}
    counts = dict.fromkeys(missing, 0)
    for node in soup.select("button,input,select,textarea,a[href],[role=button],[onclick]")[:2000]:
        if (
            node.has_attr("hidden")
            or node.get("aria-hidden") == "true"
            or re.search(
                r"display\s*:\s*none|visibility\s*:\s*hidden", node.get("style", ""), re.IGNORECASE
            )
        ):
            continue
        kind = None
        name = accessible_name(node, soup)
        if node.name in ("input", "select", "textarea"):
            if node.get("type", "text").lower() in ("hidden", "submit", "reset", "button", "image"):
                if node.get("type") in ("submit", "reset", "button"):
                    name = node.get("value", "") or name
                    kind = "buttons"
                else:
                    continue
            else:
                kind = "inputs"
        elif node.name == "button" or node.get("role") == "button":
            kind = "buttons"
        elif node.name == "a":
            kind = "links"
        if kind:
            counts[kind] += 1
            if not name.strip() and len(missing[kind]) < 8:
                missing[kind].append(
                    {
                        "selector": node_selector(node),
                        "tag": node.name,
                        "type": node.get("type"),
                        "example": f"<{node.name} type={node.get('type', '')} role={node.get('role', '')}>",
                    }
                )
        if node.name in ("div", "span") and node.has_attr("onclick"):
            counts["clickable_divs"] += 1
            if (
                node.get("role") != "button" or not node.has_attr("tabindex") or not name.strip()
            ) and len(missing["clickable_divs"]) < 8:
                missing["clickable_divs"].append(
                    {
                        "selector": node_selector(node),
                        "tag": node.name,
                        "role": node.get("role"),
                        "example": f"<{node.name} type={node.get('type', '')} role={node.get('role', '')}>",
                    }
                )
    return {
        "counts": counts,
        "issues": missing,
        "element_limit_reached": len(
            soup.select("button,input,select,textarea,a[href],[role=button],[onclick]")
        )
        > 2000,
    }


def structured_data(soup):
    scripts = soup.find_all(
        "script",
        attrs={"type": re.compile(r"^application/ld\+json(?:\s*;.*)?$", re.IGNORECASE)},
        limit=31,
    )
    errors, missing_fields, types = [], [], set()
    nodes_processed = 0
    truncated = len(scripts) > 30
    for index, script in enumerate(scripts[:30]):
        raw = script.string or script.get_text()
        if len(raw) > 100_000:
            errors.append(
                {"block": index + 1, "error": "JSON-LD block exceeds 100 KB audit budget"}
            )
            continue
        try:
            data = json.loads(
                raw,
                parse_constant=lambda value: (_ for _ in ()).throw(
                    ValueError("Invalid JSON number")
                ),
            )
        except (ValueError, RecursionError):
            errors.append({"block": index + 1, "error": "Malformed JSON-LD"})
            continue
        queue = [(data, False)]
        while queue and nodes_processed < 500:
            value, schema_context = queue.pop()
            nodes_processed += 1
            if isinstance(value, list):
                queue.extend((item, schema_context) for item in value[:100])
            elif isinstance(value, dict):
                context = value.get("@context")
                if context is not None:
                    contexts = context if isinstance(context, list) else [context]
                    schema_context = any(
                        c
                        in (
                            "https://schema.org",
                            "https://schema.org/",
                            "http://schema.org",
                            "http://schema.org/",
                        )
                        for c in contexts
                        if isinstance(c, str)
                    )
                kind = value.get("@type")
                if kind:
                    kinds = kind if isinstance(kind, list) else [kind]
                    for item in kinds[:20]:
                        if not isinstance(item, str):
                            errors.append(
                                {"block": index + 1, "error": "@type must contain strings"}
                            )
                            continue
                        item = item.removeprefix("https://schema.org/").removeprefix(
                            "http://schema.org/"
                        )
                        if schema_context:
                            types.add(item[:100])
                            if item not in SCHEMA_TYPES:
                                errors.append(
                                    {
                                        "block": index + 1,
                                        "error": "Unknown schema.org type",
                                        "type": item[:100],
                                    }
                                )
                            for prop in value:
                                if (
                                    not prop.startswith("@")
                                    and ":" not in prop
                                    and prop not in SCHEMA_PROPERTIES
                                ):
                                    errors.append(
                                        {
                                            "block": index + 1,
                                            "error": "Unknown schema.org property",
                                            "property": prop[:100],
                                        }
                                    )
                            for name in CORE_FIELDS.get(item, ()):
                                if value.get(name) in (None, "", [], {}):
                                    missing_fields.append({"type": item, "recommended_field": name})
                        else:
                            errors.append(
                                {
                                    "block": index + 1,
                                    "error": "Schema.org @context not recognized; remote/custom contexts are not resolved",
                                }
                            )
                queue.extend(
                    (v, schema_context)
                    for k, v in value.items()
                    if not k.startswith("@") or k == "@graph"
                )
        truncated |= bool(queue)
    if scripts and not types and not errors:
        errors.append({"error": "No typed schema.org entities found"})
    return {
        "blocks": len(scripts[:30]),
        "types": sorted(types)[:50],
        "errors": errors[:10],
        "recommended_fields_missing": missing_fields[:10],
        "limited": truncated,
    }


def inspect_html(body: bytes, url: str, soup=None):
    soup = soup if soup is not None else BeautifulSoup(body, "html.parser")
    text = clean_text(soup)
    semantics = semantic_measurements(soup)
    data = structured_data(soup)
    return {
        "text_length": len(text),
        "text_sample": redact(text[:1200], 1200),
        "script_count": len(soup.find_all("script", limit=100)),
        "bot_signals": [m.group(0)[:60] for m in list(CHALLENGE.finditer(str(soup)))[:5]],
        "semantics": semantics,
        "structured_data": data,
        "soft_error": bool(
            soup.title
            and re.match(
                r"^(?:404\b|page not found\b|not found\b|access denied\b)",
                soup.title.get_text(strip=True),
                re.IGNORECASE,
            )
        ),
        "title_present": bool(soup.title and soup.title.get_text(strip=True)),
        "h1_present": bool(soup.find("h1")),
    }


def html_checks(url: str, measurements: dict):
    results = []

    def add(rule, bucket, ok, title, description, fix, evidence, severity="MEDIUM", weight=1):
        results.append(
            Check(
                rule,
                bucket,
                "PASS" if ok else "FAIL",
                title,
                description,
                fix,
                severity,
                url,
                evidence,
                weight,
            )
        )

    add(
        "page.title",
        "Readability",
        measurements["title_present"],
        "Page title is missing",
        "A descriptive document title helps agents identify the page.",
        "Add <title>A specific page title | Your product</title> inside <head>.",
        {},
        "LOW",
    )
    add(
        "page.h1",
        "Readability",
        measurements["h1_present"],
        "Main heading is missing",
        "No H1 was found in the inspected HTML.",
        "Add a descriptive <h1> for the main purpose of this page.",
        {},
        "LOW",
    )
    add(
        "access.challenge",
        "Access",
        not measurements["bot_signals"],
        "Bot challenge signals detected",
        "Challenge text or CAPTCHA markup may prevent automated access; this is heuristic evidence, not proof of a universal block.",
        "Review WAF/challenge rules for the intended read-only agents. Preserve protection for sensitive operations; do not bypass challenges.",
        {"signals": measurements["bot_signals"]},
        "HIGH",
        3,
    )
    for kind, title, fix in [
        (
            "buttons",
            "Controls lack accessible names",
            '<button aria-label="Open navigation">…</button>',
        ),
        (
            "inputs",
            "Form fields lack accessible labels",
            '<label for="work-email">Work email</label><input id="work-email" type="email">',
        ),
        ("links", "Links lack accessible names", '<a href="/pricing">View pricing</a>'),
        (
            "clickable_divs",
            "Clickable elements lack native keyboard semantics",
            'Replace onclick div/span controls with <button type="button">Action name</button> and preserve the click handler.',
        ),
    ]:
        sample = measurements["semantics"]["issues"][kind]
        add(
            "semantic." + kind,
            "Actionability",
            not sample,
            title,
            "Common HTML name/label/keyboard checks found problematic controls. Review examples in context; this is not a complete accessibility audit.",
            fix,
            {"examples": sample, "elements_inspected": measurements["semantics"]["counts"][kind]},
            "HIGH",
            3,
        )
    for check in results:
        if check.rule.startswith("semantic.") and check.evidence.get("elements_inspected") == 0:
            check.status = "NOT_APPLICABLE"
        elif (
            check.rule.startswith("semantic.")
            and measurements["semantics"]["element_limit_reached"]
            and check.status == "PASS"
        ):
            check.status = "UNKNOWN"
    data = measurements["structured_data"]
    add(
        "schema.coverage",
        "Readability",
        bool(data["blocks"]),
        "No JSON-LD structured data found",
        "No JSON-LD blocks were present in the inspected document. Not every page needs structured data.",
        "Where applicable, add schema.org JSON-LD describing the actual Product, Article, Organization or FAQ content. Do not add unrelated markup.",
        {"blocks": data["blocks"], "types": data["types"]},
        "LOW",
    )
    if data["blocks"]:
        add(
            "schema.syntax",
            "Readability",
            not data["errors"],
            "JSON-LD could not be validated",
            "JSON syntax or recognized schema.org context checks failed. Remote/custom contexts are deliberately not fetched.",
            'Use valid JSON with "@context": "https://schema.org" and an appropriate string "@type". Validate the affected block before publishing.',
            data,
            "MEDIUM",
            2,
        )
        add(
            "schema.fields",
            "Readability",
            not data["recommended_fields_missing"],
            "Structured data is missing recommended fields",
            "Common schema.org types omit useful descriptive fields. These are completeness suggestions, not schema.org mandatory-field errors.",
            "Populate the recommended fields shown in evidence with accurate visible page content.",
            {"missing": data["recommended_fields_missing"]},
            "LOW",
        )
    for check in results:
        if check.rule.startswith("schema.") and data["limited"] and check.status == "PASS":
            check.status = "UNKNOWN"
        if (
            check.rule == "schema.syntax"
            and data["errors"]
            and all("context not recognized" in item.get("error", "") for item in data["errors"])
        ):
            check.status = "UNKNOWN"
    return results
