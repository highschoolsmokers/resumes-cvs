#!/usr/bin/env python3
"""Bullet outcome tracking — which bullets correlate with interviews / offers?

Pure derived view over data the system already collects:
    bullets.yaml                              — universe of bullet IDs
    applications/*/*/resume.provenance.yaml   — bullet IDs used per application
    applications/*/*/tracker.yaml             — outcome status per application

Joins the three. Writes:
    state/bullet_outcomes.csv  — one row per bullet × counts
    state/bullet_outcomes.md   — leaderboard markdown (top by interview rate,
                                  min 3 uses)

Usage:
    python3 scripts/bullet_outcomes.py
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
BULLETS_YAML = REPO / "bullets.yaml"
APPLICATIONS = REPO / "applications"
STATE_DIR = REPO / "state"
OUTCOMES_CSV = STATE_DIR / "bullet_outcomes.csv"
OUTCOMES_MD = STATE_DIR / "bullet_outcomes.md"

# Statuses we tally as positive vs negative outcomes. `applied`/`screened`/
# `interviewing` count toward "in flight"; everything else is terminal.
INTERVIEW_STATUSES = {"interviewing", "offer", "screened"}
OFFER_STATUSES = {"offer"}
REJECTED_STATUSES = {"rejected"}
GHOSTED_STATUSES = {"ghosted"}
APPLIED_STATUSES = {"applied", "interviewing", "screened", "offer",
                    "rejected", "ghosted", "withdrawn"}

MIN_USES_FOR_LEADERBOARD = 3


def load_bullet_universe() -> set[str]:
    data = yaml.safe_load(BULLETS_YAML.read_text()) or {}
    return {b["id"] for b in (data.get("bullets") or []) if "id" in b}


def find_app_dirs() -> list[Path]:
    """Every <Company>/<role-slug>-<date> folder under applications/."""
    if not APPLICATIONS.exists():
        return []
    out = []
    for company in sorted(APPLICATIONS.iterdir()):
        if not company.is_dir() or company.name.startswith("_"):
            continue
        for role in sorted(company.iterdir()):
            if role.is_dir():
                out.append(role)
    return out


def bullets_used_by(app_dir: Path) -> set[str]:
    """Pull bullet IDs from resume.provenance.yaml in app_dir."""
    prov = app_dir / "resume.provenance.yaml"
    if not prov.exists():
        return set()
    try:
        data = yaml.safe_load(prov.read_text()) or {}
    except yaml.YAMLError:
        return set()
    ids = set()
    for claim in data.get("claims") or []:
        src = (claim or {}).get("source") or ""
        m = re.match(r"^bullet:(.+)$", src.strip())
        if m:
            ids.add(m.group(1))
    return ids


def outcome_of(app_dir: Path) -> str | None:
    """Return tracker.yaml's status, or None if no tracker."""
    tracker = app_dir / "tracker.yaml"
    if not tracker.exists():
        return None
    try:
        data = yaml.safe_load(tracker.read_text()) or {}
    except yaml.YAMLError:
        return None
    return (data.get("status") or "").strip() or None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--min-uses", type=int, default=MIN_USES_FOR_LEADERBOARD,
                        help=f"minimum uses to appear on the leaderboard "
                             f"(default {MIN_USES_FOR_LEADERBOARD})")
    args = parser.parse_args()

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    universe = load_bullet_universe()
    if not universe:
        sys.stderr.write("bullet_outcomes.py: bullets.yaml has no bullets. Nothing to score.\n")
        return 1

    # bullet_id → {applied, interview, offer, rejected, ghosted, withdrawn, untracked}
    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for app in find_app_dirs():
        used = bullets_used_by(app)
        if not used:
            continue
        status = outcome_of(app)
        for bid in used:
            counts[bid]["used"] += 1
            if status is None:
                counts[bid]["untracked"] += 1
                continue
            if status in APPLIED_STATUSES:
                counts[bid]["applied"] += 1
            if status in INTERVIEW_STATUSES:
                counts[bid]["interview"] += 1
            if status in OFFER_STATUSES:
                counts[bid]["offer"] += 1
            if status in REJECTED_STATUSES:
                counts[bid]["rejected"] += 1
            if status in GHOSTED_STATUSES:
                counts[bid]["ghosted"] += 1

    # CSV: every bullet in the universe (even unused ones).
    cols = ["bullet_id", "used", "applied", "interview", "offer",
            "rejected", "ghosted", "untracked"]
    with OUTCOMES_CSV.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for bid in sorted(universe):
            row = counts.get(bid, {})
            w.writerow([bid] + [row.get(c, 0) for c in cols[1:]])

    # Leaderboard: top bullets by interview rate, min uses threshold.
    leaderboard = []
    for bid, row in counts.items():
        used = row.get("used", 0)
        if used < args.min_uses:
            continue
        applied = row.get("applied", 0)
        interview = row.get("interview", 0)
        rate = (interview / applied) if applied else 0.0
        leaderboard.append((bid, used, applied, interview, row.get("offer", 0),
                            row.get("rejected", 0), row.get("ghosted", 0), rate))
    leaderboard.sort(key=lambda r: (-r[7], -r[3], r[0]))

    lines = ["## Bullet leaderboard",
             "",
             f"_Interview rate by bullet. Min {args.min_uses} uses to qualify; "
             f"only applications with a tracker.yaml status count toward rates._",
             ""]
    if not leaderboard:
        lines.append("_Not enough application history yet — keep applying and "
                     "filling tracker.yaml on submission._")
    else:
        lines.append("| bullet_id | used | applied | interview | offer | rejected | ghosted | interview rate |")
        lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
        for bid, used, applied, interview, offer, rejected, ghosted, rate in leaderboard[:20]:
            pct = f"{rate * 100:.0f}%" if applied else "—"
            lines.append(f"| `{bid}` | {used} | {applied} | {interview} | {offer} | {rejected} | {ghosted} | {pct} |")
    lines.append("")
    OUTCOMES_MD.write_text("\n".join(lines))

    print(f"bullet_outcomes.py: wrote {OUTCOMES_CSV.relative_to(REPO)} "
          f"({len(universe)} bullets) and {OUTCOMES_MD.relative_to(REPO)} "
          f"({len(leaderboard)} on the leaderboard)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
