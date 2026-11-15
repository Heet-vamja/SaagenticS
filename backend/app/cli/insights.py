"""Group agent traffic into sessions and label them. Run with python -m app.cli.insights.

`sessions` is deterministic. `label` calls Gemini once per session (GEMINI_API_KEY).
"""

import argparse
import asyncio
import json
import sys

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.engines.agent.provider import InferenceError, InvalidAction
from app.services.insights import build_sessions, label_sessions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    sessions = commands.add_parser("sessions", help="Group new agent requests into sessions")
    sessions.add_argument("--host", required=True)
    label = commands.add_parser("label", help="Label unlabeled sessions with Gemini")
    label.add_argument("--host", required=True)
    label.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    try:
        if args.command == "sessions":
            result = build_sessions(args.host, SessionLocal)
        else:
            result = asyncio.run(
                label_sessions(args.host, get_settings(), SessionLocal, limit=args.limit)
            )
    except (ValueError, InferenceError, InvalidAction) as exc:
        sys.exit(f"error: {exc}")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
