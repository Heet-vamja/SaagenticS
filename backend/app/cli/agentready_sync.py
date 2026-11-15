"""Compare the reviewed AgentReady mapping with upstream practices; never runs during scans.

Run with python -m app.cli.agentready_sync [practices.json]. Without a path, the pinned
snapshot is used. Download a newer upstream file explicitly before a manual review.
"""

import argparse
import json
import sys
from pathlib import Path

STANDARDS = Path(__file__).resolve().parents[1] / "engines" / "standards"
REGISTRY = STANDARDS / "agentready-v2.json"
SNAPSHOT = STANDARDS / "agentready-practices-snapshot.json"


def facts(practices):
    """Normalize an upstream practices.json or the pinned snapshot to comparable facts."""
    return {
        "version": str(practices["version"]),
        "requirements": {
            item["id"]: (item.get("stage") or item.get("category"), item["level"])
            for item in practices["requirements"]
        },
        "retired": sorted(practices.get("retired", [])),
    }


def compare(registry, practices):
    upstream = facts(practices)
    local = {item["id"]: (item["stage"], item["level"]) for item in registry["requirements"]}
    remote = upstream["requirements"]
    drift = [f"Missing locally: {key}" for key in sorted(remote.keys() - local.keys())]
    drift += [f"Not upstream: {key}" for key in sorted(local.keys() - remote.keys())]
    drift += [
        f"Changed {key}: local {local[key]} upstream {remote[key]}"
        for key in sorted(local.keys() & remote.keys())
        if local[key] != remote[key]
    ]
    drift += [f"Retired upstream but mapped: {key}" for key in upstream["retired"] if key in local]
    if registry["spec_version"] != upstream["version"]:
        drift.append(
            f"Spec version: local {registry['spec_version']} upstream {upstream['version']}"
        )
    return drift


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("practices", nargs="?", type=Path, default=SNAPSHOT)
    parser.add_argument(
        "--write-snapshot",
        action="store_true",
        help="Replace the pinned snapshot with facts from the given upstream file",
    )
    args = parser.parse_args()
    practices = json.loads(args.practices.read_text())
    drift = compare(json.loads(REGISTRY.read_text()), practices)
    for line in drift:
        print(line)
    if args.write_snapshot:
        snapshot = json.loads(SNAPSHOT.read_text())
        upstream = facts(practices)
        snapshot.update(
            version=upstream["version"],
            requirements=[
                {"id": key, "stage": stage, "level": level}
                for key, (stage, level) in upstream["requirements"].items()
            ],
            retired=upstream["retired"],
        )
        SNAPSHOT.write_text(json.dumps(snapshot, indent=2) + "\n")
        print("Snapshot updated; review the source URL and the mapping before committing.")
    if not drift:
        print("Mapping matches the upstream requirement facts.")
    sys.exit(1 if drift and not args.write_snapshot else 0)


if __name__ == "__main__":
    main()
