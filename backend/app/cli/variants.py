"""Build, publish and inspect agent variants. Run with python -m app.cli.variants.

Building renders the site, calls Gemini once for extraction and needs GEMINI_API_KEY.
"""

import argparse
import asyncio
import json
import sys

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.engines.agent.provider import InferenceError, InvalidAction
from app.repositories.edge import EdgeRecords
from app.services.edge_sites import normalize_host
from app.services.variants import build_variant, publish_variant


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build", help="Crawl, extract, check parity and render")
    build.add_argument("--host", required=True)
    build.add_argument("--no-publish", action="store_true", help="Keep a passing build as DRAFT")
    publish = commands.add_parser("publish", help="Publish a passing DRAFT")
    publish.add_argument("--host", required=True)
    publish.add_argument("--version", type=int, required=True)
    listing = commands.add_parser("list", help="List variants and their parity results")
    listing.add_argument("--host", required=True)
    args = parser.parse_args()
    try:
        if args.command == "build":
            result = asyncio.run(
                build_variant(args.host, get_settings(), SessionLocal, publish=not args.no_publish)
            )
            print(
                f"v{result.version} {result.status}: {result.products} products, {result.pages} pages"
            )
            print(json.dumps(result.parity, indent=2))
        elif args.command == "publish":
            publish_variant(args.host, args.version, SessionLocal)
            print(f"Published v{args.version}")
        else:
            with SessionLocal() as session:
                records = EdgeRecords(session)
                site = records.site_by_host(normalize_host(args.host))
                if site is None:
                    sys.exit(f"error: {args.host} is not registered")
                for variant in records.variants(site.id):
                    parity = variant.parity
                    print(
                        f"v{variant.version}\t{variant.status}\t"
                        f"prices {parity.get('prices_checked')} checked, "
                        f"{len(parity.get('mismatches', []))} mismatches\t{variant.created_at:%Y-%m-%d %H:%M}"
                    )
    except (ValueError, InferenceError, InvalidAction) as exc:
        sys.exit(f"error: {exc}")


if __name__ == "__main__":
    main()
