#!/usr/bin/env python3
"""Drain the apply queue by invoking Claude Code headless mode per URL.

For each entry in queue.jsonl, run `claude -p '/apply <url>'` and either:
  - On exit 0: remove from queue, append to queue.history.jsonl.
  - On non-zero: increment retries; after 3 fails, move to queue.failed.jsonl.

Designed to be called by the scheduled-tasks MCP every ~30 min OR run by
hand with --once. Re-entrant: file locking prevents two drainer processes
from grabbing the same entry.

Usage:
    python3 scripts/apply_queue.py --once             # single drain pass
    python3 scripts/apply_queue.py                    # loop until empty
    python3 scripts/apply_queue.py --once --dry-run   # show what would run

Environment:
    CLAUDE_BIN   path to the `claude` binary (default: `claude` on PATH)
    APPLY_QUEUE_MAX_RETRIES  default 3
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
QUEUE = REPO / "queue.jsonl"
HISTORY = REPO / "queue.history.jsonl"
FAILED = REPO / "queue.failed.jsonl"
LOCK = REPO / ".queue.lock"

MAX_RETRIES = int(os.environ.get("APPLY_QUEUE_MAX_RETRIES", "3"))
CLAUDE_BIN = os.environ.get("CLAUDE_BIN", "claude")


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def read_queue() -> list[dict]:
    if not QUEUE.exists():
        return []
    out = []
    for line in QUEUE.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError as e:
            sys.stderr.write(f"apply_queue.py: skipping malformed line: {e}\n")
    return out


def write_queue(entries: list[dict]) -> None:
    QUEUE.write_text("".join(json.dumps(e) + "\n" for e in entries))


def append_jsonl(path: Path, entry: dict) -> None:
    with path.open("a") as f:
        f.write(json.dumps(entry) + "\n")


def reset_to_main() -> bool:
    """Ensure we're on main before invoking the next /apply.

    Each /apply creates an app/<…> branch; without resetting, queue entries
    after the first stack their branches on top of each other. Returns
    False if main can't be checked out cleanly (uncommitted changes, etc.).
    """
    try:
        r = subprocess.run(["git", "-C", str(REPO), "checkout", "main"],
                           capture_output=True, text=True)
        if r.returncode != 0:
            sys.stderr.write(f"apply_queue.py: `git checkout main` failed:\n"
                             f"{r.stderr}\n")
            return False
    except FileNotFoundError:
        sys.stderr.write("apply_queue.py: git not found on PATH.\n")
        return False
    return True


def run_one(entry: dict, dry_run: bool) -> bool:
    """Return True on success."""
    prompt = f"/apply {entry['url']}"
    if entry.get("company_hint"):
        prompt += f' --company "{entry["company_hint"]}"'
    if entry.get("title_hint"):
        prompt += f' --title "{entry["title_hint"]}"'

    # `--output-format stream-json` requires `--verbose` per Claude Code.
    cmd = [CLAUDE_BIN, "-p", prompt,
           "--output-format", "stream-json",
           "--verbose",
           "--max-turns", "30"]
    if dry_run:
        print(f"DRY: would run: {' '.join(cmd)}")
        return True

    if not reset_to_main():
        return False

    print(f"apply_queue.py: running {prompt}")
    try:
        r = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True)
    except FileNotFoundError:
        sys.stderr.write(f"apply_queue.py: {CLAUDE_BIN} not found on PATH. "
                         "Install Claude Code or set CLAUDE_BIN.\n")
        return False

    if r.returncode != 0:
        sys.stderr.write(f"apply_queue.py: claude exited {r.returncode}\n")
        sys.stderr.write((r.stderr or "")[-2000:])
        return False
    return True


def drain_once(dry_run: bool = False) -> int:
    """Drain one pass; return count of entries processed."""
    entries = read_queue()
    if not entries:
        return 0

    processed = 0
    remaining: list[dict] = []
    for entry in entries:
        ok = run_one(entry, dry_run)
        if ok:
            entry["completed_at"] = now_iso()
            append_jsonl(HISTORY, entry)
            processed += 1
        else:
            entry["retries"] = int(entry.get("retries", 0)) + 1
            entry["last_failed_at"] = now_iso()
            if entry["retries"] >= MAX_RETRIES:
                sys.stderr.write(f"apply_queue.py: giving up on {entry['url']} "
                                 f"after {entry['retries']} tries\n")
                append_jsonl(FAILED, entry)
            else:
                remaining.append(entry)

    write_queue(remaining)
    return processed


def with_lock(fn):
    """Run fn under an exclusive flock on LOCK; bail if held."""
    LOCK.touch(exist_ok=True)
    fd = LOCK.open("w")
    try:
        try:
            fcntl.flock(fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            sys.stderr.write("apply_queue.py: another drainer is running; exiting.\n")
            return 0
        return fn()
    finally:
        try:
            fcntl.flock(fd.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        fd.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--once", action="store_true",
                        help="single drain pass; default loops until empty")
    parser.add_argument("--dry-run", action="store_true",
                        help="print what would run; don't execute")
    parser.add_argument("--max-minutes", type=int, default=25,
                        help="loop ceiling in minutes (default 25)")
    args = parser.parse_args()

    def run():
        if args.once:
            return drain_once(args.dry_run)
        deadline = time.time() + args.max_minutes * 60
        total = 0
        while time.time() < deadline:
            count = drain_once(args.dry_run)
            if count == 0:
                return total
            total += count
        return total

    total = with_lock(run)
    print(f"apply_queue.py: processed {total} entries")
    return 0


if __name__ == "__main__":
    sys.exit(main())
