"""Agent lane early-access requests: who wants to join, for which site."""

from sqlalchemy.dialects.postgresql import insert

from app.models.domain import EarlyAccessRequest
from app.services.website_access import digest, domain_url, email_address, rate_limit


def request_early_access(session, email: str, website_url: str, identity: str) -> None:
    """Record a request once per email and domain. Repeats succeed silently, so the
    response never reveals whether an address is already on the list."""
    rate_limit(session, identity, "early-access", 5)
    address = email_address(email)
    website_url = website_url.strip()
    if "://" not in website_url:
        website_url = "https://" + website_url  # people type "example.com"
    domain, url = domain_url(website_url)
    session.execute(
        insert(EarlyAccessRequest)
        .values(email=address, domain=domain, website_url=url, identity_hash=digest(identity))
        .on_conflict_do_nothing(constraint="uq_early_access_email_domain")
    )
    session.commit()
