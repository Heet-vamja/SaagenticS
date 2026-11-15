"""Anonymous pilot aggregates. Run with python -m app.cli.pilot_metrics."""

import argparse
import json
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.domain import Project, ReportFixEvent, ReportShare, Scan, ScanStatus
from app.services.customer_fixes import compare_fixes


def collect_metrics(session, days=30):
    cutoff = datetime.now(UTC) - timedelta(days=days)
    rows = session.execute(
        select(ReportShare, Scan, Project.website_url)
        .join(Scan, ReportShare.scan_id == Scan.id)
        .join(Project, Scan.project_id == Project.id)
        .where(ReportShare.created_at >= cutoff)
    ).all()
    domains, completed, rescanned, verified = set(), set(), set(), set()
    shares, confirmed = {}, set()
    for share, scan, url in rows:
        if (scan.audit_summary or {}).get("scan_mode") != "FREE_REPORT":
            continue
        domain = (urlsplit(url).hostname or "").removeprefix("www.")
        domains.add(domain)
        shares[share.id] = domain
        if scan.status == ScanStatus.COMPLETED:
            completed.add(domain)
        if share.baseline_scan_id:
            rescanned.add(domain)
            baseline = session.get(Scan, share.baseline_scan_id)
            if baseline and baseline.project_id == scan.project_id:
                comparison = compare_fixes(baseline, scan)
                for result in comparison.results:
                    if result.status == "VERIFIED_FIXED":
                        verified.add(domain)
                        confirmed.add((domain, result.key))
    events = session.execute(
        select(ReportFixEvent.share_id, ReportFixEvent.event_type)
        .join(ReportShare, ReportFixEvent.share_id == ReportShare.id)
        .where(ReportShare.created_at >= cutoff)
    ).all()
    engaged = {}
    for share_id, kind in events:
        if share_id in shares:
            engaged.setdefault(kind, set()).add(shares[share_id])
    return {
        "window_days": days,
        "submitted_domains": len(domains),
        "completed_domains": len(completed),
        "report_links": len(shares),
        "useful_report_domains": len(engaged.get("USEFUL", set())),
        "not_yet_useful_domains": len(engaged.get("NOT_USEFUL", set())),
        "prompt_copied_domains": len(engaged.get("PROMPT_COPIED", set())),
        "fix_pack_download_domains": len(engaged.get("PACK_DOWNLOADED", set())),
        "self_reported_fix_applied_domains": len(engaged.get("FIX_APPLIED", set())),
        "rescan_domains": len(rescanned),
        "confirmed_fix_domains": len(verified),
        "distinct_confirmed_checks": len(confirmed),
        "hypothetical_39_dollar_interest_domains": len(engaged.get("PRICE_INTERESTED", set())),
        "note": "Domains approximate businesses. Applied actions are self-reported. Price interest is not payment or willingness-to-pay validation. Counts include no personal identifiers.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=30)
    options = parser.parse_args()
    if not 1 <= options.days <= 365:
        parser.error("--days must be between 1 and 365")
    with SessionLocal() as session:
        print(json.dumps(collect_metrics(session, options.days), indent=2))


if __name__ == "__main__":
    main()
