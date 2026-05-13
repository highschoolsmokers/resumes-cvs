#!/usr/bin/env python3
"""Deterministic driver for the tracker-agent's Apple Mail sweep.

Architecture (spec §6.3 / §6.5 / §9.4, CLAUDE.md §2 Phase 4):

    applications/<…>/tracker.yaml         ← per-app state (status, mail_message_ids, …)
    applications/<…>/listing.json         ← company_domains, role, source URL
    Apple Mail.app (iCloud)               ← queried via `osascript`

    scripts/sweep.py --find-unseen   →  sweep/runs/<ts>/batch.jsonl
    scripts/sweep.py --rebuild-dashboard →  dashboard.md (repo root)

`sweep.py` does only the deterministic parts: walk open applications,
query Apple Mail, dedupe against `mail_message_ids`, emit a batch
manifest. Classification of each thread (screen / scheduling / questions
/ rejection / offer / other) lives in `agents/tracker-agent.md` — the
agent reads the batch, classifies, updates trackers, hands off to
reply-drafter or scheduler, and calls back here for dashboard regen.

Why subprocess-shell to `osascript` instead of the Control-your-Mac MCP
for reads: the MCP is only reachable inside the Cowork runtime; this
script must also be runnable from a terminal on the user's machine for
debugging and from a scheduled task. Write-side operations (moving
messages into JobSearch/<Company>, staging drafts) stay in the agent,
which does have the MCP available.

Usage:

    python scripts/sweep.py --find-unseen
    python scripts/sweep.py --rebuild-dashboard
    python scripts/sweep.py --find-unseen --rebuild-dashboard   # both, in order
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    sys.stderr.write("sweep.py needs PyYAML.\n"
                     "    pip install pyyaml --break-system-packages\n")
    sys.exit(1)


REPO = Path(__file__).resolve().parent.parent
APPS = REPO / "applications"
DASHBOARD = REPO / "dashboard.md"
RUNS = REPO / "sweep" / "runs"

# Statuses that count as "open" — the sweep only queries for these.
OPEN_STATUSES = {"applied", "screened", "interviewing"}

# Recruiter-ATS sender domains always considered relevant, regardless
# of the per-company domain list. Kept small and verified — adding a
# false positive here pulls unrelated email into someone's tracker.
RECRUITER_ATS_DOMAINS = (
    "greenhouse.io",
    "ashbyhq.com",
    "lever.co",
    "gem.com",
    "ripplematch.com",
    "hire.lever.co",
    "us.greenhouse-mail.io",
)


# ---------------------------------------------------------------------------
# tracker / listing loaders
# ---------------------------------------------------------------------------


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def open_applications() -> list[Path]:
    """Return paths to application folders whose tracker says `open`."""
    if not APPS.exists():
        return []
    out: list[Path] = []
    for tracker_path in sorted(APPS.rglob("tracker.yaml")):
        # Skip the template.
        if "_template" in tracker_path.parts:
            continue
        tracker = _load_yaml(tracker_path)
        status = (tracker.get("status") or "").strip()
        if status in OPEN_STATUSES:
            out.append(tracker_path.parent)
    return out


def company_domains(app_dir: Path) -> list[str]:
    """Sender-allowlist for this application.

    Order of precedence:
        1. tracker.yaml → company_domains (list)
        2. listing.json → company_domain (string, best-effort from search-agent)
        3. fall through to just the recruiter-ATS allowlist
    """
    tracker = _load_yaml(app_dir / "tracker.yaml")
    tracker_domains = tracker.get("company_domains") or []
    if isinstance(tracker_domains, str):
        tracker_domains = [tracker_domains]

    listing = _load_json(app_dir / "listing.json")
    listing_domain = listing.get("company_domain") or None

    out = list(dict.fromkeys(
        [d.strip().lower() for d in tracker_domains if d] +
        ([listing_domain.strip().lower()] if listing_domain else [])
    ))
    return out


# ---------------------------------------------------------------------------
# AppleScript query
# ---------------------------------------------------------------------------


def _applescript_sender_filter(domains: list[str]) -> str:
    """Emit the `whose` clause for Mail.app covering every allowed domain.

    Mail.app's AppleScript `whose` predicate supports OR via `or`; each
    term matches substrings in the `sender` field (which looks like
    `"Name <local@domain>"`).
    """
    all_domains = list(dict.fromkeys(list(domains) + list(RECRUITER_ATS_DOMAINS)))
    terms = [f'sender contains "{d}"' for d in all_domains]
    return " or ".join(terms) if terms else 'sender contains "@"'


def _escape_applescript_string(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _applescript_fetch(
    mailbox_path: str | None,   # None → inbox; else e.g. "JobSearch/Vercel"
    since_iso: str,
    domains: list[str],
) -> str:
    """Return an AppleScript body producing a JSON-ish list of match dicts.

    The script prints one JSON line per matched message, followed by a
    terminating `__END__` marker on its own line. We parse line-by-line
    rather than relying on osascript's output escaping.
    """
    sender_filter = _applescript_sender_filter(domains)

    # Parse since_iso into "mm/dd/yyyy hh:mm:ss" for AppleScript's `date`
    # constructor, which is timezone-naive and interprets the string in the
    # user's local tz. Convert to local BEFORE stringifying so a UTC-suffixed
    # `since_iso` doesn't slip through 8 hours off across DST or for
    # non-Pacific users.
    since_dt = dt.datetime.fromisoformat(since_iso.replace("Z", "+00:00"))
    if since_dt.tzinfo is None:
        since_dt = since_dt.replace(tzinfo=dt.timezone.utc)
    since_local = since_dt.astimezone()
    as_date = since_local.strftime("%m/%d/%Y %H:%M:%S")

    if mailbox_path is None:
        mailbox_expr = "inbox"
    else:
        # Nested mailbox: `mailbox "JobSearch" of iCloud account`
        parts = mailbox_path.split("/")
        mailbox_expr = f'mailbox "{_escape_applescript_string(parts[-1])}"'
        for parent in reversed(parts[:-1]):
            mailbox_expr = f'mailbox "{_escape_applescript_string(parent)}" of ({mailbox_expr})'
        # The mailbox lives on the iCloud account; let AppleScript resolve it.
        mailbox_expr = f'{mailbox_expr} of (first account whose name contains "iCloud")'

    return f'''
tell application "Mail"
    set cutoff to date "{as_date}"
    set msgList to every message of ({mailbox_expr}) whose (date received > cutoff) and ({sender_filter})
    repeat with m in msgList
        set mid to (message id of m) as string
        set subj to (subject of m) as string
        set snd to (sender of m) as string
        set dt_ to (date received of m) as «class isot» as string
        try
            set snip to (content of m) as string
            if (length of snip) > 240 then
                set snip to (text 1 thru 240 of snip)
            end if
        on error
            set snip to ""
        end try
        set row to "{{" & ¬
            "\\"message_id\\":" & my toJSONString(mid) & "," & ¬
            "\\"subject\\":" & my toJSONString(subj) & "," & ¬
            "\\"from\\":" & my toJSONString(snd) & "," & ¬
            "\\"date\\":" & my toJSONString(dt_) & "," & ¬
            "\\"snippet\\":" & my toJSONString(snip) & ¬
            "}}"
        log row
    end repeat
    log "__END__"
end tell

on toJSONString(s)
    set t to ""
    repeat with i from 1 to length of s
        set c to character i of s
        if c is "\\"" then
            set t to t & "\\\\\\""
        else if c is "\\\\" then
            set t to t & "\\\\\\\\"
        else if (id of c) < 32 then
            set t to t & " "
        else
            set t to t & c
        end if
    end repeat
    return "\\"" & t & "\\""
end toJSONString
'''


def query_mailbox(mailbox_path: str | None, since_iso: str, domains: list[str]) -> list[dict[str, Any]]:
    """Run osascript and parse its `log` output into dicts."""
    script = _applescript_fetch(mailbox_path, since_iso, domains)
    try:
        proc = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, check=False, timeout=60,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        sys.stderr.write(f"sweep.py: osascript failed: {e}\n")
        return []
    # AppleScript `log` writes to stderr. stdout is the final expression's value.
    raw = proc.stderr or ""
    rows: list[dict[str, Any]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line == "__END__":
            continue
        if line.startswith("{") and line.endswith("}"):
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


# ---------------------------------------------------------------------------
# --find-unseen
# ---------------------------------------------------------------------------


def _default_since(tracker: dict[str, Any]) -> str:
    """Pick a cutoff. Prefer `last_checked_at`; fall back to 14 days ago."""
    last = tracker.get("last_checked_at")
    if last:
        return str(last)
    return (dt.datetime.now().astimezone() - dt.timedelta(days=14)).isoformat()


def find_unseen(run_dir: Path) -> Path:
    """Emit `batch.jsonl` describing every unseen matched message across apps."""
    run_dir.mkdir(parents=True, exist_ok=True)
    batch_path = run_dir / "batch.jsonl"
    now_iso = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    count = 0
    total_apps = 0

    with batch_path.open("w") as out:
        for app_dir in open_applications():
            total_apps += 1
            tracker = _load_yaml(app_dir / "tracker.yaml")
            seen = set(tracker.get("mail_message_ids") or [])
            since = _default_since(tracker)
            domains = company_domains(app_dir)
            company = tracker.get("company") or app_dir.parent.name

            rows: list[dict[str, Any]] = []
            rows.extend(query_mailbox(None, since, domains))
            rows.extend(query_mailbox(f"JobSearch/{company}", since, domains))

            for row in rows:
                mid = row.get("message_id")
                if not mid or mid in seen:
                    continue
                record = {
                    "app_dir": str(app_dir.relative_to(REPO)),
                    "company": company,
                    "role": tracker.get("role"),
                    "status": tracker.get("status"),
                    "message_id": mid,
                    "subject": row.get("subject"),
                    "from": row.get("from"),
                    "date": row.get("date"),
                    "snippet": row.get("snippet"),
                }
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
                count += 1

    manifest = {
        "generated_at": now_iso,
        "apps_scanned": total_apps,
        "unseen_messages": count,
        "batch": str(batch_path.relative_to(REPO)),
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"sweep.py: {count} unseen message(s) across {total_apps} open app(s) → {batch_path.relative_to(REPO)}")
    return batch_path


# ---------------------------------------------------------------------------
# --rebuild-dashboard
# ---------------------------------------------------------------------------


def rebuild_dashboard() -> Path:
    """Regenerate dashboard.md at repo root by calling scripts/dashboard.py."""
    dashboard_py = REPO / "scripts" / "dashboard.py"
    if not dashboard_py.exists():
        sys.stderr.write("sweep.py: scripts/dashboard.py not found — cannot rebuild dashboard.\n")
        sys.exit(1)
    proc = subprocess.run(
        [sys.executable, str(dashboard_py)],
        cwd=str(REPO), capture_output=False, text=True, check=False,
    )
    if proc.returncode != 0:
        sys.stderr.write("sweep.py: dashboard.py exited non-zero\n")
        sys.exit(proc.returncode)
    return DASHBOARD


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--find-unseen", action="store_true",
                        help="query Apple Mail for unseen matched messages across all open apps")
    parser.add_argument("--rebuild-dashboard", action="store_true",
                        help="regenerate dashboard.md from every tracker.yaml under applications/")
    parser.add_argument("--run-dir", type=Path,
                        help="explicit sweep/runs/<…>/ directory (default: autogenerated timestamp)")
    args = parser.parse_args()

    if not (args.find_unseen or args.rebuild_dashboard):
        parser.error("supply --find-unseen and/or --rebuild-dashboard")

    if args.find_unseen:
        ts = dt.datetime.now().astimezone().strftime("%Y%m%dT%H%M%S")
        run_dir = args.run_dir or (RUNS / ts)
        find_unseen(run_dir)

    if args.rebuild_dashboard:
        dashboard_path = rebuild_dashboard()
        print(f"sweep.py: dashboard rebuilt → {dashboard_path.relative_to(REPO)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
