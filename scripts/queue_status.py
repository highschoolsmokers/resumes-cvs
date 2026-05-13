#!/usr/bin/env python3
"""Print a short markdown summary of the apply queue.

Reads queue.jsonl + queue.history.jsonl + queue.failed.jsonl and emits a
markdown table on stdout. Used both standalone and via scripts/dashboard.py.

Usage:
    python3 scripts/queue_status.py            # markdown to stdout
    python3 scripts/queue_status.py --json     # JSON summary instead
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
QUEUE = REPO / "queue.jsonl"
HISTORY = REPO / "queue.history.jsonl"
FAILED = REPO / "queue.failed.jsonl"


def load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    pending = load(QUEUE)
    history = load(HISTORY)
    failed = load(FAILED)

    day_ago = datetime.now(timezone.utc) - timedelta(days=1)
    completed_today = []
    for h in history:
        try:
            ts = datetime.fromisoformat(h.get("completed_at", ""))
            if ts >= day_ago:
                completed_today.append(h)
        except (ValueError, TypeError):
            continue

    summary = {
        "pending": len(pending),
        "completed_24h": len(completed_today),
        "failed": len(failed),
        "pending_urls": [e["url"] for e in pending],
    }

    if args.json:
        json.dump(summary, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    print("## Apply queue")
    print()
    print(f"- **Pending**: {summary['pending']}")
    print(f"- **Completed (last 24h)**: {summary['completed_24h']}")
    print(f"- **Failed**: {summary['failed']}")
    if pending:
        print()
        print("### Pending URLs")
        for e in pending:
            retries = e.get("retries", 0)
            tag = f" (retries: {retries})" if retries else ""
            print(f"- {e['url']}{tag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
