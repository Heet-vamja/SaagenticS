"""Small, offline generators. Omit facts that were not observed in crawl records."""

import json
import re
from collections import defaultdict
from html import escape
from pathlib import Path
from urllib.parse import urlsplit
from xml.etree.ElementTree import Element, SubElement, tostring

from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException

from app.engines.agent.privacy import public_url, redact
from app.engines.crawling.urls import URLValidator
from app.schemas.fixes import CustomerAsset

VERSION = "crawl-assets-v1"
AI_AGENTS = json.loads(Path(__file__).with_name("ai_agents.json").read_text())


def _public_url(value):
    try:
        return URLValidator.normalize(str(value)) == str(value) and not urlsplit(value).query
    except (ValueError, TypeError):
        return False


def validate_asset(filename, content):
    """Return structural validation errors; never fetch remote contexts or URLs."""
    errors = []
    if not content or len(content.encode()) > 200_000 or "\x00" in content:
        return ["Empty or oversized asset, or invalid text"]
    try:
        if filename.endswith(".jsonld"):
            data = json.loads(content)
            if not isinstance(data, dict) or data.get("@context") != "https://schema.org":
                return ["Expected a schema.org context"]
            nodes = data.get("@graph", [data])
            if not isinstance(nodes, list) or not nodes:
                return ["Expected schema nodes"]
            for node in nodes:
                if not isinstance(node, dict):
                    return ["Expected object nodes"]
                kind = node.get("@type")
                if kind == "WebSite":
                    if not isinstance(node.get("name"), str) or not node["name"].strip():
                        errors.append("WebSite requires an observed name")
                    if not _public_url(node.get("url")):
                        errors.append(
                            "WebSite requires a public HTTP(S) URL without credentials or queries"
                        )
                elif kind == "BreadcrumbList":
                    items = node.get("itemListElement", [])
                    if not isinstance(items, list) or len(items) < 2:
                        errors.append("BreadcrumbList requires at least two observed pages")
                    else:
                        for position, item in enumerate(items, 1):
                            if not isinstance(item, dict) or item.get("@type") != "ListItem":
                                errors.append("Invalid breadcrumb item")
                            elif (
                                item.get("position") != position
                                or not item.get("name")
                                or not _public_url(item.get("item"))
                            ):
                                errors.append(
                                    "Breadcrumb requires name, public item URL and consecutive position"
                                )
                else:
                    errors.append("Unsupported generated schema type")
        elif filename.endswith(".xml"):
            root = ElementTree.fromstring(content, forbid_dtd=True)
            if root.tag != "{http://www.sitemaps.org/schemas/sitemap/0.9}urlset":
                errors.append("Expected sitemap urlset")
            locations = [node.text for node in root.iter() if node.tag.endswith("}loc")]
            if (
                not locations
                or len(locations) != len(set(locations))
                or not all(_public_url(url) for url in locations)
            ):
                errors.append("Sitemap needs unique public URLs")
        elif filename.startswith("robots-"):
            in_group = False
            for raw in content.splitlines():
                line = raw.split("#", 1)[0].strip()
                if not line:
                    continue
                name, sep, value = line.partition(":")
                name, value = name.strip().lower(), value.strip()
                if not sep or name not in {"user-agent", "allow", "disallow", "sitemap"}:
                    errors.append("Invalid robots directive")
                elif name == "user-agent":
                    in_group = bool(re.fullmatch(r"[A-Za-z0-9*._-]+", value))
                    if not in_group:
                        errors.append("Invalid user-agent")
                elif name in {"allow", "disallow"} and (not in_group or not value.startswith("/")):
                    errors.append("Path directive requires a group and absolute path")
                elif name == "sitemap" and not _public_url(value):
                    errors.append("Invalid sitemap URL")
        elif filename == "llms.txt":
            if not re.match(r"^# [^\n]+\n", content) or len(re.findall(r"(?m)^# ", content)) != 1:
                errors.append("Expected one site heading")
            if not re.search(r"(?m)^## .+", content):
                errors.append("Expected grouped links")
            links = re.findall(r"\]\((https?://[^\s)]+)\)", content)
            if not links or not all(_public_url(url) for url in links):
                errors.append("Expected valid public links")
        else:
            errors.append("Unsupported asset type")
    except (
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        RecursionError,
        ElementTree.ParseError,
        DefusedXmlException,
    ):
        errors.append("Malformed asset")
    return errors


def _markdown(value):
    value = escape(redact(str(value), 700)).replace("\n", " ").replace("\r", " ")
    return re.sub(r"([\\`*\[\]()#])", r"\\\1", value)


def generate_assets(pages, starting_url, robots_preset="keep_existing"):
    scope = URLValidator(starting_url)
    observed = {}
    for page in pages:
        if not page.status_code or not 200 <= page.status_code < 300 or page.crawl_error:
            continue
        if not (page.content_type or "").lower().startswith("text/html"):
            continue
        try:
            url = scope.accept(public_url(page.url))
        except ValueError:
            continue
        # Query variants cannot safely become unqualified URLs in generated assets.
        if urlsplit(page.url).query:
            continue
        observed.setdefault(url, page)
    assets, missing = [], []

    def add(filename, content, media_type, placement, provenance):
        errors = validate_asset(filename, content)
        if errors:
            missing.append(f"{filename} withheld: {'; '.join(errors)}")
            return
        assets.append(
            CustomerAsset(
                key=filename,
                filename=filename,
                content=content,
                media_type=media_type,
                placement=placement,
                provenance=provenance,
                validated=True,
                version=VERSION,
            )
        )

    if not observed:
        return [], [
            "No successful public HTML pages were available; re-scan before generating assets."
        ]
    home = next((page for url, page in observed.items() if urlsplit(url).path == "/"), None)
    if home and home.title and home.title.strip():
        groups = defaultdict(list)
        for url, page in sorted(observed.items()):
            path = urlsplit(url).path.strip("/")
            section = path.split("/")[0] if path else "Overview"
            title = page.title or path or url
            description = (
                _markdown(page.meta_description) if page.meta_description else "needs a description"
            )
            groups[section].append(f"- [{_markdown(title)}]({url}): {description}")
        body = f"# {_markdown(home.title)}\n\n"
        if home.meta_description:
            body += f"> {_markdown(home.meta_description)}\n\n"
        else:
            missing.append(
                "Homepage description: add a confirmed summary in the page's meta description."
            )
        for section, lines in groups.items():
            body += f"## {_markdown(section)}\n\n" + "\n".join(lines) + "\n\n"
        add(
            "llms.txt",
            body,
            "text/plain",
            "Review, then upload to /llms.txt. This optional proposal does not guarantee AI visibility.",
            "Observed homepage title, descriptions and successful public page URLs.",
        )
        site = {
            "@context": "https://schema.org",
            "@type": "WebSite",
            "name": redact(home.title, 300),
            "url": public_url(home.url),
        }
        if home.meta_description:
            site["description"] = redact(home.meta_description, 700)
        add(
            "website.jsonld",
            json.dumps(site, ensure_ascii=False, indent=2),
            "application/ld+json",
            "Review the site name, then embed as application/ld+json in the homepage head. Merge with existing markup.",
            "Observed homepage title, URL and meta description only.",
        )
        # Breadcrumbs are generated only for parent/child pages both actually crawled.
        for url, page in sorted(observed.items()):
            if page is home or not page.title:
                continue
            home_url = public_url(home.url)
            if urlsplit(url).netloc != urlsplit(home_url).netloc:
                continue
            if url not in {
                public_url(link)
                for link in home.page_metadata.get("internal_links", [])
                if isinstance(link, str)
            }:
                continue
            breadcrumbs = {
                "@context": "https://schema.org",
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {
                        "@type": "ListItem",
                        "position": 1,
                        "name": redact(home.title, 300),
                        "item": home_url,
                    },
                    {
                        "@type": "ListItem",
                        "position": 2,
                        "name": redact(page.title, 300),
                        "item": url,
                    },
                ],
            }
            add(
                "breadcrumbs.jsonld",
                json.dumps(breadcrumbs, ensure_ascii=False, indent=2),
                "application/ld+json",
                f"Optional two-level breadcrumb for {url}. Confirm this hierarchy matches the site and merge with existing markup.",
                "Only the observed homepage and this page; no unvisited ancestor URLs were invented.",
            )
            break
    else:
        missing.append(
            "Observed homepage name/title: no homepage title was available, so llms.txt and WebSite markup were withheld."
        )
    missing.append(
        "Organization, Product, Article, FAQ and LocalBusiness facts are not retained in this crawl. Confirm required facts before adding those schema types; none were invented."
    )
    no_descriptions = sum(not page.meta_description for page in observed.values())
    if no_descriptions:
        missing.append(
            f"{no_descriptions} sampled page(s) need descriptions; llms.txt labels them 'needs a description'."
        )

    root = Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
    for url in sorted(observed):
        SubElement(SubElement(root, "url"), "loc").text = url
    add(
        "sitemap-suggestions.xml",
        tostring(root, encoding="unicode"),
        "application/xml",
        "Merge successful sampled URLs into your sitemap. This is a bounded sample, not a replacement for the full site sitemap; no lastmod dates were invented.",
        "Successfully fetched, same-site HTML pages only; existing sitemap omissions are not asserted.",
    )
    if robots_preset != "keep_existing":
        lines = [
            "# Proposed groups only. Review and merge; preserve existing restrictions.",
            "# Search access is limited to exact public paths observed in this scan.",
        ]
        for agent in AI_AGENTS["search"]:
            lines.extend([f"User-agent: {agent}", "Disallow: /"])
            lines.extend(f"Allow: {urlsplit(url).path}$" for url in sorted(observed))
            lines.append("")
        if robots_preset == "block_training":
            for agent in AI_AGENTS["training"]:
                lines.extend([f"User-agent: {agent}", "Disallow: /", ""])
        add(
            "robots-policy-proposal.txt",
            "\n".join(lines),
            "text/plain",
            "Owner-selected proposal. Manually merge these groups into /robots.txt, resolve duplicates, and preserve current private-path restrictions. Never replace the existing file blindly.",
            f"Explicit user preset: {robots_preset}; bot list {AI_AGENTS['version']}; only sampled public paths allowed for search.",
        )
    return assets, missing
