"""Register or list edge router sites. Run with python -m app.cli.edge_sites."""

import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.engines.variants.actions import DeliveryRules
from app.repositories.edge import EdgeRecords
from app.services.edge_sites import register_site


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    add = commands.add_parser("add", help="Serve a host through the edge router")
    add.add_argument("--host", required=True, help="Public host, e.g. store.localhost")
    add.add_argument("--origin", required=True, help="Origin, e.g. https://shop.example.com")
    add.add_argument("--name", required=True)
    commands.add_parser("list", help="List registered sites")
    delivery = commands.add_parser(
        "set-delivery", help="Set owner-approved delivery rules for check_delivery"
    )
    delivery.add_argument("--host", required=True)
    delivery.add_argument("--rules", required=True, help="DeliveryRules JSON file, or - for stdin")
    args = parser.parse_args()
    with SessionLocal() as session:
        if args.command == "set-delivery":
            site = EdgeRecords(session).site_by_host(args.host.strip().lower())
            if site is None:
                sys.exit(f"error: {args.host} is not registered")
            try:
                raw = sys.stdin.read() if args.rules == "-" else Path(args.rules).read_text()
                rules = DeliveryRules.model_validate(json.loads(raw))
            except (OSError, ValueError, ValidationError) as exc:
                sys.exit(f"error: invalid delivery rules: {exc}")
            site.delivery_rules = rules.model_dump()
            session.commit()
            print(f"Delivery rules saved for {site.host}")
        elif args.command == "add":
            try:
                site = register_site(session, get_settings(), args.host, args.origin, args.name)
            except ValueError as exc:
                sys.exit(f"error: {exc}")
            print(f"Registered {site.host} -> {site.origin_url}")
        else:
            for site in EdgeRecords(session).sites():
                state = "routing" if site.routing_enabled else "pass-through only"
                print(f"{site.host}\t{site.origin_url}\t{site.name}\t{state}")


if __name__ == "__main__":
    main()
