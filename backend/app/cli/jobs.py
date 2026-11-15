"""Run dashboard-started site jobs. Run with python -m app.cli.jobs worker.

Runs where Gemini is configured and the edge router is reachable (the `jobs` service in
Docker Compose). Use --once to process at most one job and exit.
"""

import argparse
import asyncio
import logging

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.site_jobs import work


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    worker = commands.add_parser("worker", help="Poll for queued jobs and run them")
    worker.add_argument("--once", action="store_true", help="Process at most one job")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        asyncio.run(work(get_settings(), SessionLocal, once=args.once))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
