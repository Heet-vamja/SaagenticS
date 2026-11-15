"""Deterministic parity between the extracted catalog and the collected evidence.

A variant may restructure content but never change facts. Prices must be found in the
evidence; a stock claim that contradicts the evidence blocks publishing, and a stock
claim the evidence cannot confirm is removed rather than published.
"""

import re
from dataclasses import dataclass, field

from app.engines.variants.contracts import Catalog, Evidence

NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
STOCK_KEYS = ("stock", "quantity", "qty", "inventory", "available", "in_stock", "inStock")


@dataclass
class ParityReport:
    prices_checked: int = 0
    stock_checked: int = 0
    mismatches: list[dict] = field(default_factory=list)
    unverified: list[dict] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.mismatches and self.prices_checked > 0

    def as_dict(self) -> dict:
        return {
            "passed": self.passed,
            "prices_checked": self.prices_checked,
            "stock_checked": self.stock_checked,
            "mismatches": self.mismatches[:100],
            "unverified": self.unverified[:100],
        }


def _objects(value, depth=0):
    """Every dict inside a JSON value, bounded."""
    if depth > 8:
        return
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _objects(child, depth + 1)
    elif isinstance(value, list):
        for child in value[:2000]:
            yield from _objects(child, depth + 1)


def _numbers(text: str) -> set[float]:
    found = set()
    for match in NUMBER.findall(text or ""):
        try:
            found.add(float(match.replace(",", "")))
        except ValueError:
            continue
    return found


def _mentions(obj: dict, product) -> bool:
    needles = {product.slug.lower(), product.name.lower()}
    return any(isinstance(v, str) and v.strip().lower() in needles for v in obj.values())


def _stock_evidence(objects: list[dict], size: str) -> bool | None:
    """True/False when a candidate object states availability for this size."""
    for obj in objects:
        for value in obj.values():
            # {"sizes": {"9": 3}} style maps.
            if isinstance(value, dict) and size in value:
                amount = value[size]
                if isinstance(amount, bool):
                    return amount
                if isinstance(amount, (int, float)):
                    return amount > 0
            # [{"size": "9", "stock": 3}] style lists.
            if isinstance(value, list):
                for entry in value:
                    if isinstance(entry, dict) and str(entry.get("size")) == size:
                        for key in STOCK_KEYS:
                            amount = entry.get(key)
                            if isinstance(amount, bool):
                                return amount
                            if isinstance(amount, (int, float)):
                                return amount > 0
    return None


def check_parity(catalog: Catalog, evidence: Evidence) -> tuple[ParityReport, Catalog]:
    report = ParityReport()
    page_text = {page.path: page.text for page in evidence.pages}
    all_objects = [obj for item in evidence.data for obj in _objects(item.body)]
    checked = catalog.model_copy(deep=True)
    for product in checked.products:
        candidates = [obj for obj in all_objects if _mentions(obj, product)]
        json_prices = {
            float(v)
            for obj in candidates
            for v in obj.values()
            if isinstance(v, (int, float)) and not isinstance(v, bool)
        }
        text_prices = _numbers(page_text.get(product.path, ""))
        report.prices_checked += 1
        if not any(abs(product.price - value) < 0.005 for value in json_prices | text_prices):
            report.mismatches.append(
                {"slug": product.slug, "field": "price", "detail": "Price not found in evidence"}
            )
        if product.path not in page_text:
            report.unverified.append(
                {"slug": product.slug, "field": "path", "detail": "Product page not rendered"}
            )
        for size in product.sizes:
            if size.in_stock is None:
                continue
            observed = _stock_evidence(candidates, size.size)
            if observed is None:
                report.unverified.append(
                    {"slug": product.slug, "field": f"stock:{size.size}", "detail": "Removed"}
                )
                size.in_stock = None  # Never publish availability the evidence cannot confirm.
                continue
            report.stock_checked += 1
            if observed != size.in_stock:
                report.mismatches.append(
                    {
                        "slug": product.slug,
                        "field": f"stock:{size.size}",
                        "detail": "Availability contradicts evidence",
                    }
                )
    return report, checked
