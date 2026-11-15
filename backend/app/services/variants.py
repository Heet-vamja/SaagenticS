"""Build, check and publish agent variants for edge sites.

Flow: render evidence from the origin -> Gemini extracts a typed catalog -> deterministic
parity check against the evidence -> deterministic rendering -> persist. A variant is
published only when parity passes; earlier published versions are superseded, never
deleted. Rejected builds are kept with their parity report for review.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from app.core.config import Settings
from app.engines.variants.contracts import Catalog
from app.engines.variants.evidence import collect_evidence
from app.engines.variants.extraction import ensure_provider, extract_catalog
from app.engines.variants.parity import check_parity
from app.engines.variants.render import render_variant
from app.models.domain import SiteVariant, VariantPage
from app.repositories.edge import EdgeRecords
from app.services.edge_sites import normalize_host


@dataclass
class BuildResult:
    version: int
    status: str
    parity: dict
    pages: int
    products: int


def _load_site(session_factory, host: str):
    with session_factory() as session:
        site = EdgeRecords(session).site_by_host(normalize_host(host))
        if site is None:
            raise ValueError(f"{host} is not registered")
        return site.id, site.origin_url


async def build_variant(
    host: str, settings: Settings, session_factory, publish: bool = True, transport=None
) -> BuildResult:
    site_id, origin = _load_site(session_factory, host)
    await ensure_provider(settings, transport=transport)
    evidence = await collect_evidence(origin, settings)
    if not any(page.text for page in evidence.pages):
        raise ValueError("No rendered content was collected from the origin")
    catalog, usage = await extract_catalog(evidence, settings, transport=transport)
    report, checked = check_parity(catalog, evidence)
    generated_at = datetime.now(UTC)
    pages, llms_txt = render_variant(checked, generated_at)
    status = "PUBLISHED" if publish and report.passed else "DRAFT" if report.passed else "REJECTED"
    with session_factory() as session:
        records = EdgeRecords(session)
        version = records.next_variant_version(site_id)
        if status == "PUBLISHED":
            records.supersede_published(site_id)
        records.add_variant(
            SiteVariant(
                site_id=site_id,
                version=version,
                status=status,
                catalog=checked.model_dump(mode="json"),
                parity=report.as_dict(),
                evidence_summary={
                    "pages": len(evidence.pages),
                    "pages_with_text": sum(bool(p.text) for p in evidence.pages),
                    "json_responses": len(evidence.data),
                    "limited": evidence.limited,
                },
                llms_txt=llms_txt,
                model=settings.agent_model,
                usage=usage,
                published_at=generated_at if status == "PUBLISHED" else None,
            ),
            [VariantPage(path=p.path, markdown=p.markdown, html=p.html) for p in pages],
        )
        session.commit()
    return BuildResult(version, status, report.as_dict(), len(pages), len(checked.products))


def publish_variant(host: str, version: int, session_factory) -> None:
    """Publish a DRAFT that already passed parity (built with publish=False)."""
    with session_factory() as session:
        records = EdgeRecords(session)
        site = records.site_by_host(normalize_host(host))
        variant = records.variant(site.id, version) if site else None
        if variant is None:
            raise ValueError("Variant not found")
        if variant.status != "DRAFT" or not variant.parity.get("passed"):
            raise ValueError("Only drafts that passed the parity check can be published")
        records.supersede_published(site.id)
        variant.status = "PUBLISHED"
        variant.published_at = datetime.now(UTC)
        session.commit()


def catalog_of(variant: SiteVariant) -> Catalog:
    return Catalog.model_validate(variant.catalog)
