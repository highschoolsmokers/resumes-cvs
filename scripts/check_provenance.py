#!/usr/bin/env python3
"""Provenance checker: every concrete claim in an output file must be sourced.

Architecture — CLAUDE.md §6 and spec §8.8:

    resume.docx / cover-letter.md / replies/<thread>.md  ←  output artifacts
        +
    resume.provenance.yaml / *.provenance.yaml           ←  sidecars

The sidecar lists every claim in the output and the source that grounds it.
Valid source kinds:

    bullet:<id>               — ID in bullets.yaml
    summary:<id>              — ID in bullets.yaml summaries
    skill:<key>               — key in bullets.yaml skills_menu
    education:<id>            — ID in bullets.yaml education
    company-fact:<anchor>     — anchor in the sibling company-facts.md
    personal-fact:<dotted.path> — dotted path in config/personal-facts.yaml
    voice:<relative-path>     — path under voice-corpus/
    template:<anchor>         — verbatim in WSGong_Resume_Template.docx or
                                listing.md (rare — accepted for JD echoes)

Sidecar schema (YAML):

    artifact: resume.docx          # relative path from sidecar location
    generated_at: <iso8601>
    generator: build_resume.py|build_cover_letter.py|reply-drafter agent
    claims:
      - claim: "Ships production MCP servers..."
        source: bullet:independent-mcp-servers-paperless-colophon-litverity
      - claim: "contributes to Vercel AI SDK integration guides"
        source: company-fact:vercel-ai-sdk-docs
    unsourced_claims: []           # list of claim strings the agent could
                                   # not ground; MUST be empty to pass

If `unsourced_claims` is non-empty, or any `source:` reference doesn't resolve,
this script emits errors.

Modes:

    --warn   print errors and exit 0 (Phase 2 default — pre-commit warns only)
    --block  print errors and exit non-zero (Phase 3 onward — blocks commits)

Usage:

    # one artifact explicitly
    python scripts/check_provenance.py path/to/resume.provenance.yaml

    # all artifacts under a directory (applications/, archive/)
    python scripts/check_provenance.py --all

    # from a git pre-commit hook (only look at staged sidecars)
    python scripts/check_provenance.py --staged

Template skip:
    applications/_template/ contains skeleton sidecars with literal
    placeholder sources (e.g. `bullet:<bullet-id>`) that intentionally
    never resolve. Bulk modes (--all, --staged) skip this directory. To
    lint the template itself, pass the sidecar path explicitly.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    sys.stderr.write("check_provenance.py needs PyYAML.\n"
                     "    pip install pyyaml --break-system-packages\n")
    sys.exit(1)


REPO = Path(__file__).resolve().parent.parent
BULLETS_YAML = REPO / "bullets.yaml"
PERSONAL_FACTS = REPO / "config" / "personal-facts.yaml"  # gitignored
VOICE_CORPUS = REPO / "voice-corpus"


# -----------------------------------------------------------------------------
# closed-universe loaders
# -----------------------------------------------------------------------------

def _load_bullets() -> dict[str, set]:
    """Return {kind: set-of-ids} for bullets.yaml closed universes."""
    out = {
        "bullet": set(),
        "summary": set(),
        "skill": set(),
        "education": set(),
    }
    if not BULLETS_YAML.exists():
        return out
    with BULLETS_YAML.open() as f:
        data = yaml.safe_load(f) or {}
    out["bullet"] = {b["id"] for b in data.get("bullets", []) if b.get("id")}
    out["summary"] = {
        s["id"]
        for family in (data.get("summaries") or {}).values()
        for s in family
        if s.get("id")
    }
    out["skill"] = set((data.get("skills_menu") or {}).keys())
    out["education"] = {e["id"] for e in data.get("education", []) if e.get("id")}
    return out


def _flatten_keys(obj: Any, prefix: str = "") -> set[str]:
    """All dotted paths through a nested dict. Leaves are strings/numbers/bool."""
    if isinstance(obj, dict):
        keys: set[str] = set()
        for k, v in obj.items():
            path = f"{prefix}.{k}" if prefix else str(k)
            keys.add(path)
            keys |= _flatten_keys(v, path)
        return keys
    return set()


def _load_personal_fact_keys() -> set[str]:
    if not PERSONAL_FACTS.exists():
        return set()
    with PERSONAL_FACTS.open() as f:
        data = yaml.safe_load(f) or {}
    return _flatten_keys(data)


def _load_voice_paths() -> set[str]:
    if not VOICE_CORPUS.exists():
        return set()
    return {str(p.relative_to(VOICE_CORPUS))
            for p in VOICE_CORPUS.rglob("*")
            if p.is_file()}


def _parse_company_facts(path: Path) -> set[str]:
    """Anchors are the text after `## ` in company-facts.md, slugified.

    We accept either a literal `anchor: <slug>` line or a markdown heading.
    """
    if not path.exists():
        return set()
    anchors: set[str] = set()
    for line in path.read_text().splitlines():
        if line.startswith("## "):
            heading = line[3:].strip().lower()
            slug = "".join(
                c if c.isalnum() else "-"
                for c in heading
            ).strip("-")
            # collapse runs
            while "--" in slug:
                slug = slug.replace("--", "-")
            anchors.add(slug)
        elif line.strip().startswith("anchor:"):
            anchors.add(line.split(":", 1)[1].strip())
    return anchors


# -----------------------------------------------------------------------------
# core check
# -----------------------------------------------------------------------------

def check_sidecar(sidecar: Path, universes: dict[str, Any]) -> list[str]:
    """Return list of error strings for this sidecar (empty → pass)."""
    errors: list[str] = []
    try:
        with sidecar.open() as f:
            data = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        return [f"{sidecar}: invalid YAML: {e}"]

    artifact_rel = data.get("artifact")
    if not artifact_rel:
        errors.append(f"{sidecar}: missing `artifact:`")
    else:
        artifact_path = (sidecar.parent / artifact_rel).resolve()
        if not artifact_path.exists():
            errors.append(f"{sidecar}: artifact not found: {artifact_rel}")

    unsourced = data.get("unsourced_claims") or []
    if unsourced:
        errors.append(
            f"{sidecar}: {len(unsourced)} unsourced_claims present — "
            f"must be empty before shipping"
        )
        for u in unsourced:
            errors.append(f"    · {u}")

    # Load per-sidecar company-facts if present.
    company_facts_path = sidecar.parent / "company-facts.md"
    company_facts = _parse_company_facts(company_facts_path)

    for claim_entry in data.get("claims", []):
        source = (claim_entry or {}).get("source")
        claim = (claim_entry or {}).get("claim", "<no-text>")
        if not source:
            errors.append(f"{sidecar}: claim without source: {claim[:80]!r}")
            continue
        if ":" not in source:
            errors.append(f"{sidecar}: malformed source {source!r} for: {claim[:80]!r}")
            continue
        kind, value = source.split(":", 1)
        kind = kind.strip()
        value = value.strip()

        if kind in ("bullet", "summary", "skill", "education"):
            if value not in universes[kind]:
                errors.append(
                    f"{sidecar}: {kind}:{value} not in bullets.yaml "
                    f"(for claim: {claim[:80]!r})"
                )
        elif kind == "company-fact":
            if value not in company_facts:
                errors.append(
                    f"{sidecar}: company-fact:{value} not in {company_facts_path.name} "
                    f"(for claim: {claim[:80]!r})"
                )
        elif kind == "personal-fact":
            if value not in universes["personal_fact_keys"]:
                errors.append(
                    f"{sidecar}: personal-fact:{value} not in config/personal-facts.yaml "
                    f"(for claim: {claim[:80]!r})"
                )
        elif kind == "voice":
            if value not in universes["voice_paths"]:
                errors.append(
                    f"{sidecar}: voice:{value} not under voice-corpus/ "
                    f"(for claim: {claim[:80]!r})"
                )
        elif kind == "template":
            # accepted without further validation — the template anchor scheme
            # is loose by design; reviewer verifies by eye
            pass
        else:
            errors.append(
                f"{sidecar}: unknown source kind {kind!r} for claim: {claim[:80]!r}"
            )

    return errors


# -----------------------------------------------------------------------------
# sidecar discovery
# -----------------------------------------------------------------------------

TEMPLATE_DIR = REPO / "applications" / "_template"


def _is_template_sidecar(path: Path) -> bool:
    """True if `path` lives under applications/_template/.

    The template carries intentional placeholder sources like
    `bullet:<bullet-id>` that never resolve; bulk modes must skip it.
    """
    try:
        path.resolve().relative_to(TEMPLATE_DIR.resolve())
        return True
    except ValueError:
        return False


def all_sidecars() -> list[Path]:
    roots = [REPO / "applications", REPO / "archive"]
    out: list[Path] = []
    for root in roots:
        if root.exists():
            out.extend(sorted(root.rglob("*.provenance.yaml")))
    return [p for p in out if not _is_template_sidecar(p)]


def staged_sidecars() -> list[Path]:
    try:
        res = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=AM"],
            cwd=str(REPO), capture_output=True, text=True, check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        sys.stderr.write(f"check_provenance.py: git diff failed: {e}\n")
        return []
    out: list[Path] = []
    for line in res.stdout.splitlines():
        line = line.strip()
        if line.endswith(".provenance.yaml"):
            p = (REPO / line).resolve()
            if not _is_template_sidecar(p):
                out.append(p)
    return out


# -----------------------------------------------------------------------------
# main
# -----------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("sidecar", type=Path, nargs="?",
                        help="one `.provenance.yaml` to check")
    parser.add_argument("--all", action="store_true",
                        help="check every provenance sidecar under applications/ and archive/")
    parser.add_argument("--staged", action="store_true",
                        help="check sidecars currently git-staged (for pre-commit hook)")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--warn", dest="mode", action="store_const", const="warn",
                       help="print errors, exit 0 (Phase 2 default)")
    group.add_argument("--block", dest="mode", action="store_const", const="block",
                       help="print errors, exit non-zero (Phase 3 onward)")
    parser.set_defaults(mode="warn")
    args = parser.parse_args()

    targets: list[Path] = []
    if args.staged:
        targets = staged_sidecars()
    elif args.all:
        targets = all_sidecars()
    elif args.sidecar:
        targets = [args.sidecar]
    else:
        parser.error("supply one sidecar, or --all, or --staged")

    if not targets:
        print("check_provenance.py: no provenance sidecars found.")
        return 0

    # Shared closed universes
    bullets_universes = _load_bullets()
    universes: dict[str, Any] = {
        **bullets_universes,
        "personal_fact_keys": _load_personal_fact_keys(),
        "voice_paths": _load_voice_paths(),
    }

    all_errors: list[str] = []
    for sidecar in targets:
        all_errors.extend(check_sidecar(sidecar, universes))

    if all_errors:
        sys.stderr.write(
            f"check_provenance.py: {len(all_errors)} issue(s) across "
            f"{len(targets)} sidecar(s):\n"
        )
        for err in all_errors:
            sys.stderr.write(f"  - {err}\n")
        if args.mode == "block":
            sys.stderr.write(
                "\nBLOCKING (--block): fix unsourced claims or missing sources "
                "before committing.\n"
            )
            return 1
        else:
            sys.stderr.write(
                "\nWARNING ONLY (--warn): Phase 2 runs in warn mode. Flip to "
                "--block in Phase 3 (spec §8.8, CLAUDE.md §2 Phase 3 acceptance).\n"
            )
            return 0

    print(f"check_provenance.py: {len(targets)} sidecar(s) OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
