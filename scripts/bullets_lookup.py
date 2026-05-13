#!/usr/bin/env python3
"""Search bullets.yaml — useful when drafting a resume plan by hand.

The tailor uses `bullets.yaml` programmatically. This is the human on-ramp:
"show me every MCP bullet", "what do I have under Slack that a DevRel hirer
would care about", etc.

Usage:

    python scripts/bullets_lookup.py --tag mcp
    python scripts/bullets_lookup.py --family developer-relations
    python scripts/bullets_lookup.py --role slack-2017
    python scripts/bullets_lookup.py --keyword "Anthropic SDK"
    python scripts/bullets_lookup.py --list-tags
    python scripts/bullets_lookup.py --list-roles
    python scripts/bullets_lookup.py --list-families

Filters combine with AND. Output is one match per line:

    <bullet_id>  (role) [fam,fam]  text...

`--verbose` prints the full text and tag list per match. `--ids` prints only
the IDs, one per line — handy for piping into a plan file.
"""
from __future__ import annotations

import argparse
import sys
import textwrap
from pathlib import Path

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    sys.stderr.write("bullets_lookup.py needs PyYAML.\n")
    sys.exit(1)


REPO = Path(__file__).resolve().parent.parent
BULLETS_YAML = REPO / "bullets.yaml"


def load(path: Path) -> dict:
    if not path.exists():
        sys.stderr.write(f"bullets.yaml not found at {path}\n")
        sys.exit(1)
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def match(bullet: dict, *,
          tag: str | None,
          family: str | None,
          role: str | None,
          keyword: str | None) -> bool:
    if tag and tag not in (bullet.get("tags") or []):
        return False
    if family and family not in (bullet.get("role_family") or []):
        return False
    if role and bullet.get("role_id") != role:
        return False
    if keyword:
        hay = (bullet.get("text") or "").lower()
        if keyword.lower() not in hay:
            return False
    return True


def print_match(b: dict, roles_by_id: dict, *, verbose: bool,
                ids_only: bool) -> None:
    bid = b.get("id", "?")
    if ids_only:
        print(bid)
        return
    role = roles_by_id.get(b.get("role_id"), {})
    employer = role.get("employer", "?")
    fams = ",".join(b.get("role_family") or [])
    text = (b.get("text") or "").strip()
    header = f"{bid}  ({employer})  [{fams}]"
    if verbose:
        tags = ", ".join(b.get("tags") or [])
        print(header)
        for line in textwrap.wrap(text, width=96):
            print(f"    {line}")
        if tags:
            print(f"    tags: {tags}")
        print()
    else:
        truncated = text if len(text) <= 80 else text[:77] + "..."
        print(f"{header}  {truncated}")


def list_tags(data: dict) -> None:
    tags = sorted({t for b in data.get("bullets", []) for t in (b.get("tags") or [])})
    for t in tags:
        print(t)


def list_roles(data: dict) -> None:
    for r in data.get("roles", []):
        print(f"{r.get('id'):<22}  {r.get('employer')}")


def list_families(data: dict) -> None:
    fams = sorted({fam for b in data.get("bullets", [])
                   for fam in (b.get("role_family") or [])})
    for f in fams:
        print(f)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tag", default=None)
    parser.add_argument("--family", default=None)
    parser.add_argument("--role", default=None)
    parser.add_argument("--keyword", default=None)
    parser.add_argument("--list-tags", action="store_true")
    parser.add_argument("--list-roles", action="store_true")
    parser.add_argument("--list-families", action="store_true")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--ids", action="store_true",
                        help="print only bullet IDs, one per line")
    parser.add_argument("--path", type=Path, default=BULLETS_YAML)
    args = parser.parse_args()

    data = load(args.path)

    if args.list_tags:
        list_tags(data)
        return 0
    if args.list_roles:
        list_roles(data)
        return 0
    if args.list_families:
        list_families(data)
        return 0

    roles_by_id = {r.get("id"): r for r in data.get("roles", [])}
    results = [
        b for b in data.get("bullets", [])
        if match(b, tag=args.tag, family=args.family,
                 role=args.role, keyword=args.keyword)
    ]

    if not results:
        sys.stderr.write("bullets_lookup.py: no matches\n")
        return 1

    for b in results:
        print_match(b, roles_by_id, verbose=args.verbose, ids_only=args.ids)

    if not args.ids:
        print()
        print(f"  {len(results)} bullet(s) matched.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
