"""Small structured event sink. Never pass prompts, credentials or provider bodies."""

import json
import logging

logger = logging.getLogger("agentreadiness.agent")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
logger.propagate = False


def event(name: str, **fields):
    logger.info(json.dumps({"event": name, **fields}, separators=(",", ":")))
