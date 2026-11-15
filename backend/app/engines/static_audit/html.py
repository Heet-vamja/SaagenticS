"""No HTML is retained. Store bounded, redacted measurements and issue examples."""

import json
import re
from itertools import pairwise
from pathlib import Path

from bs4 import BeautifulSoup, Comment

from app.engines.agent.privacy import redact
from app.engines.static_audit.checks import Check
from app.engines.static_audit.resources import (
    code_example_check,
    code_examples,
    html_resource_links,
    pricing_check,
    pricing_measurements,
)

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
    headings = [int(node.name[1]) for node in soup.find_all([f"h{i}" for i in range(1, 7)])]
    heading_jumps = [
        {"from": previous, "to": current}
        for previous, current in pairwise(headings)
        if current > previous + 1
    ]
    description = soup.find(
        "meta", attrs={"name": lambda value: value and value.lower() == "description"}
    )
    canonical = soup.find("link", rel=lambda value: value and "canonical" in value)
    robots = soup.find(
        "meta", attrs={"name": lambda value: value and value.lower() in ("robots", "googlebot")}
    )
    navigation = soup.select("nav")
    navigation_links = [link for nav in navigation for link in nav.find_all("a", href=True)]
    return {
        "code_examples": code_examples(soup),
        "discovery_resources": html_resource_links(soup, url),
        "pricing": pricing_measurements(soup, url, text),
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
        "heading_levels": headings[:200],
        "heading_jumps": heading_jumps[:50],
        "meta_description_present": bool(
            description and (description.get("content") or "").strip()
        ),
        "meta_description_length": len((description.get("content") or "").strip())
        if description
        else 0,
        "canonical_present": bool(canonical and canonical.get("href")),
        "robots_meta": (robots.get("content") or "")[:200] if robots else None,
        "navigation_regions": len(navigation),
        "navigation_links": len(navigation_links),
        "navigation_unnamed_links": sum(
            not accessible_name(link, soup).strip() for link in navigation_links[:200]
        ),
    }


def html_checks(url: str, measurements: dict):
    results = []
    if isinstance(measurements.get("code_examples"), dict):
        results.append(code_example_check(url, measurements["code_examples"]))
    if isinstance(measurements.get("pricing"), dict) and (
        check := pricing_check(url, measurements["pricing"])
    ):
        results.append(check)
    pass_titles = {
        "page.title": "Page title is present",
        "page.h1": "Main heading is present",
        "page.heading_hierarchy": "Heading hierarchy is consistent",
        "navigation.links": "Navigation links have accessible names",
        "access.challenge": "No known bot challenge signal was observed",
        "semantic.buttons": "Buttons have accessible names",
        "semantic.inputs": "Form fields have labels",
        "semantic.links": "Links have accessible names",
        "semantic.clickable_divs": "No unsupported clickable elements were observed",
        "schema.syntax": "JSON-LD passed the supported syntax checks",
    }

    def add(rule, bucket, ok, title, description, fix, evidence, severity="MEDIUM", weight=1):
        results.append(
            Check(
                rule,
                bucket,
                "PASS" if ok else "FAIL",
                pass_titles.get(rule, title) if ok else title,
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
        {"h1_present": measurements["h1_present"]},
        "LOW",
    )
    hierarchy_start = len(results)
    add(
        "page.heading_hierarchy",
        "Readability",
        not measurements.get("heading_jumps"),
        "Heading levels skip content sections",
        "A heading level jumps over one or more levels, which can make a page outline harder to follow.",
        "Use heading levels in order to reflect the content outline. Do not choose a heading only for its visual size.",
        {"heading_jumps": measurements.get("heading_jumps", [])},
        "LOW",
    )
    if not measurements.get("heading_levels"):
        results[hierarchy_start].status = "NOT_APPLICABLE"
        results[hierarchy_start].title = "No headings were present to check hierarchy"
    if measurements.get("navigation_regions"):
        add(
            "navigation.links",
            "Actionability",
            measurements.get("navigation_links", 0) > 0
            and measurements.get("navigation_unnamed_links", 0) == 0,
            "Navigation links need clearer destinations or names",
            "A navigation region was present, but it contained no links or links without accessible names.",
            "Use real anchor elements with clear visible text or an accessible name for navigation destinations.",
            {
                "regions": measurements.get("navigation_regions", 0),
                "links": measurements.get("navigation_links", 0),
                "unnamed_links": measurements.get("navigation_unnamed_links", 0),
            },
            "MEDIUM",
        )
    if measurements.get("robots_meta"):
        directives = [item.strip().lower() for item in measurements["robots_meta"].split(",")]
        if "noindex" in directives:
            results.append(
                Check(
                    "page.indexability",
                    "Access",
                    "INFO",
                    "Page requests no indexing",
                    "A robots meta directive includes noindex. This may be intentional; confirm it matches the page’s publication goals.",
                    url=url,
                    evidence={"robots_meta": measurements["robots_meta"]},
                    weight=0,
                )
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
        count = measurements["semantics"]["counts"][kind]
        add(
            "semantic." + kind,
            "Actionability",
            not sample,
            title,
            "Common HTML name/label/keyboard checks found problematic controls. Review examples in context; this is not a complete accessibility audit.",
            fix,
            {"examples": sample, "elements_inspected": count},
            "HIGH",
            3,
        )
    for check in results:
        if check.rule.startswith("semantic.") and check.evidence.get("elements_inspected") == 0:
            check.status = "NOT_APPLICABLE"
            check.title = "No applicable elements were present"
        elif (
            check.rule.startswith("semantic.")
            and measurements["semantics"]["element_limit_reached"]
            and check.status == "PASS"
        ):
            check.status = "UNKNOWN"
            check.title = "Could not inspect every element for this check"
    data = measurements["structured_data"]
    results.append(
        Check(
            "schema.coverage",
            "Readability",
            "INFO",
            "JSON-LD structured data found"
            if data["blocks"]
            else "No JSON-LD structured data found",
            "JSON-LD was present in the inspected document. Its absence is not evidence that the page is unusable; presence alone does not establish accurate or complete markup.",
            url=url,
            evidence={"blocks": data["blocks"], "types": data["types"]},
            weight=0,
        )
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
            "Structured data is missing recommended fields"
            if data["recommended_fields_missing"]
            else "Recommended structured-data fields were reviewed",
            "Common schema.org types omit useful descriptive fields. These are completeness suggestions, not schema.org mandatory-field errors.",
            "Populate the recommended fields shown in evidence with accurate visible page content.",
            {"missing": data["recommended_fields_missing"]},
            "LOW",
        )
        results[-1].status = "INFO"
    for check in results:
        if check.rule.startswith("schema.") and data["limited"] and check.status == "PASS":
            check.status = "UNKNOWN"
            check.title = "Could not inspect all structured-data items"
        if (
            check.rule == "schema.syntax"
            and data["errors"]
            and all("context not recognized" in item.get("error", "") for item in data["errors"])
        ):
            check.status = "UNKNOWN"
            check.title = "Schema context could not be resolved safely"
    return results
