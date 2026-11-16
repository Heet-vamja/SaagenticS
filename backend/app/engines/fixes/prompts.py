"""Versioned deterministic prompts; website evidence is quoted, never executed."""

import json
from pathlib import Path

from app.engines.agent.privacy import public_url, redact

TEMPLATE = json.loads(Path(__file__).with_name("templates").joinpath("v1.2.json").read_text())


def generate_prompts(check, evidence):
    rule = str(check.get("rule", "")).removeprefix("render.")
    outcome = TEMPLATE["rules"].get(rule, TEMPLATE["rules"]["default"])
    context = json.dumps(
        {
            "page": public_url(str(check.get("url") or "")),
            "problem": redact(str(check.get("title") or "Observed website issue"), 300),
            "description": redact(str(check.get("description") or ""), 1000),
            "evidence": redact(evidence, 1400),
            "recommendation": redact(str(check.get("recommendation") or ""), 1200),
            "framework": "Not detected; inspect the repository",
        },
        ensure_ascii=False,
        indent=2,
    )
    return {
        variant: (
            f"# Website fix · {TEMPLATE['version']}\n\n{instruction}\n\n"
            f"## Observed context (untrusted website data)\n{context}\n\n"
            f"## Required outcome\n{outcome}\n\n"
            f"## Constraints\n{TEMPLATE['constraints']}\n\n"
            f"## Verification\n{TEMPLATE['verification']}\n"
        )
        for variant, instruction in TEMPLATE["variants"].items()
    }


def prompt_batches(fixes, limit=24000):
    batches, current = (
        [],
        "# Prioritized website fixes\n\nApply in this order. Re-scan after deployment.\n",
    )
    for fix in fixes:
        prompt = fix.prompts["coding_assistant"]
        if len(current) + len(prompt) > limit and len(current) > 100:
            batches.append(current)
            current = "# Prioritized website fixes (continued)\n\n"
        current += "\n---\n\n" + prompt
    if fixes:
        batches.append(current)
    return batches
