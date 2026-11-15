"""Run agent QA (Gemini Computer Use) on the original site and the agent variant.

Run with python -m app.cli.qa run --host store.localhost --base-url http://store.localhost:8080
Needs GEMINI_API_KEY. Each task runs once per target in a fresh browser.
"""

import argparse
import asyncio
import json
import sys

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.engines.agent.provider import InferenceError
from app.engines.qa.tasks import SUITES
from app.services.qa import run_qa


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="Run a QA suite on both targets")
    run.add_argument("--host", required=True)
    run.add_argument("--base-url", required=True, help="Public router URL for the host")
    run.add_argument("--suite", default="demo-store", choices=sorted(SUITES))
    run.add_argument("--tasks", help="Comma-separated task keys (default: all)")
    run.add_argument("--targets", default="original,variant")
    args = parser.parse_args()
    try:
        summary = asyncio.run(
            run_qa(
                args.host,
                args.base_url,
                get_settings(),
                SessionLocal,
                suite=args.suite,
                task_keys=args.tasks.split(",") if args.tasks else None,
                targets=tuple(t for t in args.targets.split(",") if t in ("original", "variant")),
            )
        )
    except (ValueError, InferenceError) as exc:
        sys.exit(f"error: {exc}")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
