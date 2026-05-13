#!/usr/bin/env python3
"""Add a job-listing URL to the apply queue.

The queue is a JSONL file at the repo root (gitignored). `scripts/apply_queue.py`
drains it; the scheduled-tasks MCP fires that every 30 min by default.

Usage:
    python3 scripts/queue_add.py <URL> [--company X] [--title Y]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
QUEUE = REPO / "queue.jsonl"
HISTORY = REPO / "queue.history.jsonl"

# Reuse url_ingest.detect_source for validation.
sys.path.insert(0, str(REPO / "scripts"))
from url_ingest import detect_source  # noqa: E402


def existing_urls() -> set[str]:
    seen = set()
    for path in (QUEUE, HISTORY):
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                seen.add(json.loads(line)["url"])
            except (json.JSONDecodeError, KeyError):
                continue
    return seen


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("url", help="listing URL")
    parser.add_argument("--company", default=None, help="company hint (optional)")
    parser.add_argument("--title", default=None, help="title hint (optional)")
    args = parser.parse_args()

    try:
        source, _ = detect_source(args.url)
    except Exception as e:
        sys.stderr.write(f"queue_add.py: cannot parse URL: {e}\n")
        return 1

    if args.url in existing_urls():
        sys.stderr.write("queue_add.py: URL already in queue or history; skipping.\n")
        return 1

    entry = {
        "url": args.url,
        "added_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "company_hint": args.company,
        "title_hint": args.title,
        "source": source,
        "retries": 0,
    }
    with QUEUE.open("a") as f:
        f.write(json.dumps(entry) + "\n")
    print(f"queue_add.py: queued ({source}) {args.url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
