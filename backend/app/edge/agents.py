"""Versioned registry of known agent and crawler user-agents.

Only user-initiated agent fetchers may be routed to a variant. Search and training
crawlers are passed through unchanged (routing them would be cloaking) but logged.
User-agents can be spoofed; classification never grants access to gated content.
"""

import re
from dataclasses import dataclass

REGISTRY_VERSION = "2026-11-14"

# (canonical name, kind, token matched case-insensitively as a whole word)
_KNOWN = (
    ("ChatGPT-User", "agent", "ChatGPT-User"),
    ("Claude-User", "agent", "Claude-User"),
    ("Perplexity-User", "agent", "Perplexity-User"),
    ("MistralAI-User", "agent", "MistralAI-User"),
    ("Googlebot", "crawler", "Googlebot"),
    ("Google-InspectionTool", "crawler", "Google-InspectionTool"),
    ("Bingbot", "crawler", "bingbot"),
    ("GPTBot", "crawler", "GPTBot"),
    ("OAI-SearchBot", "crawler", "OAI-SearchBot"),
    ("ClaudeBot", "crawler", "ClaudeBot"),
    ("Claude-SearchBot", "crawler", "Claude-SearchBot"),
    ("PerplexityBot", "crawler", "PerplexityBot"),
    ("CCBot", "crawler", "CCBot"),
    ("Applebot", "crawler", "Applebot"),
    ("Amazonbot", "crawler", "Amazonbot"),
    ("Bytespider", "crawler", "Bytespider"),
    ("Meta-ExternalAgent", "crawler", "meta-externalagent"),
)
_PATTERNS = tuple(
    (name, kind, re.compile(rf"(?<![\w-]){re.escape(token)}(?!\w)", re.IGNORECASE))
    for name, kind, token in _KNOWN
)


@dataclass(frozen=True)
class Visitor:
    name: str
    kind: str  # "agent", "crawler" or "human"

    @property
    def routable(self) -> bool:
        return self.kind == "agent"


HUMAN = Visitor("human", "human")


def classify(user_agent: str | None) -> Visitor:
    value = (user_agent or "")[:1000]
    for name, kind, pattern in _PATTERNS:
        if pattern.search(value):
            return Visitor(name, kind)
    return HUMAN
