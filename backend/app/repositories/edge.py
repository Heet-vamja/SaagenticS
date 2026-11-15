from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.domain import AgentRequest, EdgeSite, SiteVariant, VariantPage


class EdgeRecords:
    """Database access only; the service owns transaction boundaries."""

    def __init__(self, session: Session):
        self.session = session

    def site_by_host(self, host: str) -> EdgeSite | None:
        return self.session.scalar(select(EdgeSite).where(EdgeSite.host == host))

    def sites(self, limit: int = 100) -> list[EdgeSite]:
        return list(self.session.scalars(select(EdgeSite).order_by(EdgeSite.host).limit(limit)))

    def add_site(self, site: EdgeSite) -> EdgeSite:
        self.session.add(site)
        self.session.flush()
        return site

    def add_requests(self, rows: list[AgentRequest]) -> None:
        self.session.add_all(rows)
        self.session.flush()

    def recent_requests(self, site_id, limit: int = 100) -> list[AgentRequest]:
        return list(
            self.session.scalars(
                select(AgentRequest)
                .where(AgentRequest.site_id == site_id)
                .order_by(AgentRequest.received_at.desc())
                .limit(limit)
            )
        )

    def published_variant(self, site_id) -> SiteVariant | None:
        return self.session.scalar(
            select(SiteVariant).where(
                SiteVariant.site_id == site_id, SiteVariant.status == "PUBLISHED"
            )
        )

    def variant_pages(self, variant_id) -> list[VariantPage]:
        return list(
            self.session.scalars(select(VariantPage).where(VariantPage.variant_id == variant_id))
        )

    def variants(self, site_id, limit: int = 20) -> list[SiteVariant]:
        return list(
            self.session.scalars(
                select(SiteVariant)
                .where(SiteVariant.site_id == site_id)
                .order_by(SiteVariant.version.desc())
                .limit(limit)
            )
        )

    def variant(self, site_id, version: int) -> SiteVariant | None:
        return self.session.scalar(
            select(SiteVariant).where(
                SiteVariant.site_id == site_id, SiteVariant.version == version
            )
        )

    def next_variant_version(self, site_id) -> int:
        current = self.session.scalar(
            select(func.max(SiteVariant.version)).where(SiteVariant.site_id == site_id)
        )
        return (current or 0) + 1

    def supersede_published(self, site_id) -> None:
        self.session.execute(
            update(SiteVariant)
            .where(SiteVariant.site_id == site_id, SiteVariant.status == "PUBLISHED")
            .values(status="SUPERSEDED")
        )

    def add_variant(self, variant: SiteVariant, pages: list[VariantPage]) -> SiteVariant:
        self.session.add(variant)
        self.session.flush()
        for page in pages:
            page.variant_id = variant.id
        self.session.add_all(pages)
        self.session.flush()
        return variant
