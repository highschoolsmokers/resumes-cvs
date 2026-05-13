#!/usr/bin/env python3
"""Lint `bullets.yaml` — catch structural drift before it hits a resume.

Checks:

1. **Unique IDs** — bullet IDs, summary IDs, role IDs, education IDs, skill
   keys must each be globally unique within their namespace.
2. **Role references resolve** — every bullet's `role_id` points at a role
   declared in the `roles:` list.
3. **Role families match** — every bullet's `role_family` entries are known
   families (from config/criteria.yaml if present; else the fixed fallback).
4. **Summary provenance** — every `built_from:` ID in a summary resolves to a
   bullet ID.
5. **Skill-order keys exist** — every key in `skill_order` / skills_menu is
   consistent across the menu.
6. **Minimum coverage** — each active role (anything except earlier-1997)
   has ≥ 1 bullet for each role family declared in config/criteria.yaml.
   Emits warnings, not errors, so gaps surface during tailoring rather than
   blocking build.
7. **source_doc sanity** — every bullet's `source_doc` points at a path that
   exists (relative to the repo root). Warning-only.

Exit codes:
    0 — no issues OR only warnings
    1 — one or more errors

Usage:
    python scripts/lint_bullets.py
    python scripts/lint_bullets.py --strict   # promote warnings to errors
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    sys.stderr.write("lint_bullets.py needs PyYAML.\n")
    sys.exit(1)


REPO = Path(__file__).resolve().parent.parent
BULLETS_YAML = REPO / "bullets.yaml"
CRITERIA_YAML = REPO / "config" / "criteria.yaml"


FALLBACK_FAMILIES = {
    "developer-relations",
    "forward-deployed-engineer",
    "agentic-programmer",
    "technical-writer",
}


def load_role_families() -> set[str]:
    """Prefer criteria.yaml; fall back to the known canonical set."""
    if not CRITERIA_YAML.exists():
        return set(FALLBACK_FAMILIES)
    with CRITERIA_YAML.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    families = data.get("role_families")
    if isinstance(families, dict):
        return set(families.keys())
    if isinstance(families, list):
        return set(families)
    return set(FALLBACK_FAMILIES)


def lint(data: dict, families: set[str]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    roles = data.get("roles", []) or []
    bullets = data.get("bullets", []) or []
    summaries_dict = data.get("summaries") or {}
    skills_menu = data.get("skills_menu") or {}
    education = data.get("education") or []

    # 1. Uniqueness
    for label, items in (
        ("role id", [r.get("id") for r in roles]),
        ("bullet id", [b.get("id") for b in bullets]),
        ("education id", [e.get("id") for e in education]),
    ):
        counts = Counter(x for x in items if x)
        for value, n in counts.items():
            if n > 1:
                errors.append(f"duplicate {label}: {value!r} ({n}×)")

    summary_ids = [s.get("id") for fam in summaries_dict.values() for s in fam]
    for value, n in Counter(x for x in summary_ids if x).items():
        if n > 1:
            errors.append(f"duplicate summary id: {value!r} ({n}×)")

    # 2. role_id references
    role_ids = {r["id"] for r in roles if r.get("id")}
    for b in bullets:
        rid = b.get("role_id")
        if rid and rid not in role_ids:
            errors.append(
                f"bullet {b.get('id')!r} references unknown role_id {rid!r}"
            )

    # 3. role_family known
    for b in bullets:
        for fam in b.get("role_family") or []:
            if fam not in families:
                errors.append(
                    f"bullet {b.get('id')!r} has unknown role_family {fam!r} "
                    f"(known: {sorted(families)})"
                )

    # role-level title_alternates keys (optional but must be known if present)
    for r in roles:
        alts = r.get("title_alternates") or {}
        for fam in alts.keys():
            if fam not in families:
                warnings.append(
                    f"role {r.get('id')!r} has title_alternate for unknown "
                    f"family {fam!r}"
                )

    # 4. summary built_from resolves
    bullet_ids = {b["id"] for b in bullets if b.get("id")}
    for family_key, fam in summaries_dict.items():
        if family_key not in families:
            warnings.append(
                f"summaries section {family_key!r} is not a known role_family"
            )
        for s in fam:
            for bid in s.get("built_from") or []:
                if bid not in bullet_ids:
                    errors.append(
                        f"summary {s.get('id')!r} cites missing bullet "
                        f"{bid!r}"
                    )

    # 5. skills_menu sanity (check entries carry label+content)
    for key, entry in skills_menu.items():
        if not isinstance(entry, dict):
            errors.append(f"skills_menu/{key}: expected mapping")
            continue
        if not entry.get("label"):
            errors.append(f"skills_menu/{key}: missing `label`")
        if not entry.get("content"):
            errors.append(f"skills_menu/{key}: missing `content`")

    # 6. coverage per role per family (warning only)
    for r in roles:
        rid = r.get("id")
        if rid == "earlier-1997":
            continue
        role_bullets = [b for b in bullets if b.get("role_id") == rid]
        if not role_bullets:
            warnings.append(f"role {rid!r} has zero bullets")
            continue
        fams_covered = {
            fam
            for b in role_bullets
            for fam in (b.get("role_family") or [])
        }
        for family in families:
            if family not in fams_covered:
                warnings.append(
                    f"role {rid!r} has no bullet tagged for family {family!r}"
                )

    # 7. source_doc exists on disk (warning)
    for b in bullets:
        src = b.get("source_doc")
        if src and not (REPO / src).exists():
            warnings.append(
                f"bullet {b.get('id')!r} source_doc does not exist: {src}"
            )

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--strict", action="store_true",
                        help="treat warnings as errors")
    parser.add_argument("--path", type=Path, default=BULLETS_YAML,
                        help="bullets.yaml path")
    args = parser.parse_args()

    if not args.path.exists():
        sys.stderr.write(f"bullets.yaml not found at {args.path}\n")
        return 1

    with args.path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        sys.stderr.write("bullets.yaml did not parse to a mapping\n")
        return 1

    families = load_role_families()
    errors, warnings = lint(data, families)

    if warnings:
        print(f"[warn] {len(warnings)} warning(s):")
        for w in warnings:
            print(f"  - {w}")
    if errors:
        print(f"[err ] {len(errors)} error(s):", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)

    fail = bool(errors) or (args.strict and warnings)
    if not fail:
        print("lint_bullets.py: OK"
              + ("" if not warnings else " (with warnings)"))
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
