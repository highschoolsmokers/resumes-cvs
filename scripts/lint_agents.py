#!/usr/bin/env python3
"""Lint `agents/*.md` for drift against the rest of the repo.

What it catches:

  1. **Frontmatter sanity** — every agent has YAML frontmatter with `name`
     and `description` fields.
  2. **File reference resolution** — any backtick-quoted relative path the
     agent mentions (e.g. `bullets.yaml`, `scripts/check_provenance.py`,
     `config/voice.yaml`) actually exists on disk. Skips template-style
     paths with `<…>`, `<Company>`, etc.
  3. **§-reference resolution** — any `§N.N` reference resolves to a
     heading in `job-search-agent-spec.md` (or CLAUDE.md when prefixed
     with "CLAUDE.md §"). Catches the case where the spec restructures
     and a prompt is left dangling.
  4. **Opaque MCP IDs** — flags `mcp__<long-hex>__*` (session-hash-based,
     not portable). Prompts should use the friendly name instead
     (e.g. "Google Calendar MCP").
  5. **Script invocations** — any `python(3)? <script>.py` or
     `scripts/<name>.py` reference points at a real script. Warns if a
     `--flag` mentioned in the prompt isn't in the script's argparse.
  6. **Output completeness (warning)** — agents that produce committed
     artifacts should have an `## Acceptance` or `## Output` section.

Usage:
    python3 scripts/lint_agents.py             # all agents, warning mode
    python3 scripts/lint_agents.py --strict    # warnings → errors
    python3 scripts/lint_agents.py --staged    # only staged agents/*.md
    python3 scripts/lint_agents.py agents/foo.md  # one file
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
AGENTS_DIR = REPO / "agents"
SPEC = REPO / "job-search-agent-spec.md"
CLAUDE_MD = REPO / "CLAUDE.md"
SCRIPTS_DIR = REPO / "scripts"

# Skip template placeholder paths that contain these markers — they don't
# refer to real files, they're examples.
PLACEHOLDER_MARKERS = ("<", ">", "*", "…", "...", "{")

# Known good non-file backticked terms we don't want to validate as paths.
NON_PATH_BACKTICKS = {
    "claude", "claude -p", "claude --version", "tail", "head", "grep",
    "git", "git add", "git commit", "git checkout", "git log", "git mv",
    "git status", "git rebase", "git push", "git pull", "git diff",
    "bash", "sh", "zsh", "make", "brew", "pip", "pip install",
    "python", "python3", "yaml", "json", "json5",
    "true", "false", "null", "None",
    # AppleScript verbs (referenced in tracker/reply-drafter prompts)
    "send", "save", "move", "make new outgoing message",
    "make new", "delete",
    # Single tokens that match the backtick-path regex but aren't files
    "main", "master", "head",
    # Common references
    "applications/_template", "applications/_template/",
    "voice-corpus/", "voice-corpus", "voice-corpus/*",
    "search/", "applications/", "config/", "agents/", "scripts/", "docs/",
    ".githooks/", ".githooks", "state/", "sweep/",
}

# Patterns that look path-ish but aren't real on-disk references. URL path
# fragments, suffixes, IANA tz names, etc.
NON_PATH_PREFIXES = ("/", "*", "America/", "Europe/", "Asia/", "Pacific/",
                     "Africa/", "Australia/", "UTC")
NON_PATH_SUFFIXES = (".unpacked/", "_template/")
NON_PATH_BASENAMES = {
    # Per-application artifact filenames — they live under applications/<…>/
    # which the agent prompt elides. These are real but the literal path
    # at the repo root never exists, so we skip them.
    "resume.docx", "resume.pdf", "resume.unpacked",
    "cover-letter.docx", "cover-letter.pdf", "cover-letter.md",
    "cover-letter.provenance.yaml", "resume.provenance.yaml",
    "listing.json", "listing.md", "company-facts.md",
    "tracker.yaml", "notes.md", "fit-report.md",
    "resume-plan.yaml", "jd-analysis.md",
    "batch.jsonl", "manifest.json", "listings.jsonl", "scored.jsonl",
    "summary.md", "raw/",
    # Generated/derived names referenced by template
    "state.db", "errors.log", "queue.jsonl",
    "applications/_plans/",   # gitignored dir; ref is to-pattern, not literal
}

# Regex to find inline-code refs like `scripts/foo.py` or `bullets.yaml`.
# Match backticks containing what looks like a path or filename.
BACKTICK_PATH_RE = re.compile(r"`([A-Za-z0-9_./\-]+)`")

# Regex for §N.N references. Inline form preferred; some prompts use
# "spec §X.Y" or "CLAUDE.md §X.Y".
SECTION_REF_RE = re.compile(r"(CLAUDE\.md\s*§|spec\s*§|§)(\d+(?:\.\d+(?:\.\d+)?)?)")

# MCP ID pattern: mcp__ followed by what looks like a UUID-ish hex blob.
MCP_HASH_RE = re.compile(r"mcp__[a-f0-9]{8,}-[a-f0-9-]{4,}")

# Script invocation pattern: capture the script path.
SCRIPT_INVOKE_RE = re.compile(
    r"(?:python3?\s+)?(?:scripts/)?([A-Za-z0-9_]+\.py)\b"
)


def spec_headings() -> set[str]:
    """Collect '1', '1.1', '1.1.1', etc. heading numbers from the spec.

    Also collect §11 list-items (the open-questions list uses numbered
    bullets that prompts cite as §11.3, §11.10, etc.).
    """
    out: set[str] = set()
    if not SPEC.exists():
        return out
    in_section_11 = False
    for line in SPEC.read_text(encoding="utf-8").splitlines():
        # Headings: ## N. or ### N.N or #### N.N.N
        m = re.match(r"^#{2,4}\s+(\d+(?:\.\d+(?:\.\d+)?)?)[\. ]", line)
        if m:
            out.add(m.group(1))
        # Section 11 numbered bullets
        if line.startswith("## 11."):
            in_section_11 = True
            continue
        if in_section_11 and re.match(r"^## ", line):
            in_section_11 = False
        if in_section_11:
            bm = re.match(r"^(\d+)\.\s", line)
            if bm:
                out.add(f"11.{bm.group(1)}")
    return out


def claude_md_headings() -> set[str]:
    """Same idea against CLAUDE.md."""
    out: set[str] = set()
    if not CLAUDE_MD.exists():
        return out
    for line in CLAUDE_MD.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^#{2,4}\s+(\d+(?:\.\d+(?:\.\d+)?)?)[\. ]", line)
        if m:
            out.add(m.group(1))
    return out


def script_flags(script_path: Path) -> set[str]:
    """Best-effort extraction of --flags from an argparse-using Python script.

    Greps for `add_argument("--foo")` / `add_argument('--foo', ...)` etc.
    Returns the set of flag names INCLUDING the leading --.
    """
    flags: set[str] = set()
    if not script_path.exists() or script_path.suffix != ".py":
        return flags
    try:
        text = script_path.read_text(encoding="utf-8")
    except OSError:
        return flags
    for m in re.finditer(r"""add_argument\(\s*['"](--[A-Za-z0-9_\-]+)['"]""", text):
        flags.add(m.group(1))
    # Also pick up dest= renames if any
    return flags


def lint_one(path: Path,
             spec_secs: set[str],
             claude_secs: set[str]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    text = path.read_text(encoding="utf-8")

    # 1. Frontmatter sanity.
    if not text.startswith("---\n"):
        errors.append(f"{path.name}: missing YAML frontmatter")
    else:
        try:
            body = text.split("---\n", 2)[1]
            fm = yaml.safe_load(body) or {}
        except yaml.YAMLError as e:
            errors.append(f"{path.name}: frontmatter YAML parse: {e}")
            fm = {}
        if not fm.get("name"):
            errors.append(f"{path.name}: frontmatter missing `name`")
        if not fm.get("description"):
            errors.append(f"{path.name}: frontmatter missing `description`")
        # Filename should match frontmatter name
        if fm.get("name") and fm["name"] != path.stem:
            warnings.append(
                f"{path.name}: frontmatter name={fm['name']!r} ≠ filename "
                f"stem={path.stem!r}"
            )

    # 2. File reference resolution.
    for m in BACKTICK_PATH_RE.finditer(text):
        ref = m.group(1)
        # Skip if it has placeholder markers
        if any(c in ref for c in PLACEHOLDER_MARKERS):
            continue
        if ref in NON_PATH_BACKTICKS:
            continue
        if ref in NON_PATH_BASENAMES:
            continue
        # URL path fragments, IANA tz, suffix-only constructs
        if ref.startswith(NON_PATH_PREFIXES):
            continue
        if ref.endswith(NON_PATH_SUFFIXES):
            continue
        # Skip short tokens / single words (e.g. `text`, `id`, `applied`)
        if "/" not in ref and "." not in ref:
            continue
        # Skip URLs and email-ish things
        if ref.startswith(("http://", "https://", "mailto:")):
            continue
        candidate = REPO / ref
        if candidate.exists():
            continue
        # Many references are to per-app files (no leading applications/<Co>/
        # because the prompt elides that). Skip docx/pdf/unpacked suffixes.
        if ref.endswith((".docx", ".pdf", ".unpacked")) and "applications/" not in ref:
            continue
        # Per-app subpaths like replies/<...>, schedule/<...> — placeholder
        # markers should've caught these, but bare `replies/` slips through.
        if ref.rstrip("/") in {"replies", "schedule"}:
            continue
        # We only flag paths that LOOK absolute (have `/`).
        if "/" in ref:
            errors.append(f"{path.name}: file reference {ref!r} does not exist")

    # 3. §-reference resolution.
    for m in SECTION_REF_RE.finditer(text):
        prefix, num = m.group(1), m.group(2)
        is_claude_ref = "CLAUDE.md" in prefix
        target = claude_secs if is_claude_ref else spec_secs
        if num not in target:
            label = "CLAUDE.md" if is_claude_ref else "spec"
            errors.append(
                f"{path.name}: §{num} does not resolve in {label}"
            )

    # 4. Opaque MCP IDs.
    for m in MCP_HASH_RE.finditer(text):
        errors.append(
            f"{path.name}: opaque MCP id {m.group(0)!r} — use the "
            f"friendly name (e.g. 'Google Calendar MCP') instead"
        )

    # 5. Script invocations — verify the script exists. Flag validation is
    #    proximity-based and too noisy in prose, so we skip it.
    for m in SCRIPT_INVOKE_RE.finditer(text):
        script_name = m.group(1)
        if script_name in {"setup.py", "__init__.py"}:
            continue
        loc = None
        for candidate in (SCRIPTS_DIR / script_name, REPO / script_name):
            if candidate.exists():
                loc = candidate
                break
        if loc is None:
            errors.append(f"{path.name}: invocation references nonexistent "
                          f"script {script_name!r}")

    # 6. Output completeness.
    if "## Acceptance" not in text and "## Output" not in text:
        warnings.append(
            f"{path.name}: no `## Acceptance` or `## Output` section "
            "— consumers can't verify the agent finished its job"
        )

    return errors, warnings


def staged_agents() -> list[Path]:
    try:
        r = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=AM"],
            cwd=str(REPO), capture_output=True, text=True, check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        sys.stderr.write(f"lint_agents.py: git diff failed: {e}\n")
        return []
    out = []
    for line in r.stdout.splitlines():
        line = line.strip()
        if line.startswith("agents/") and line.endswith(".md"):
            p = REPO / line
            if p.exists():
                out.append(p)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="*", type=Path,
                        help="agent .md files to lint (default: all agents/*.md)")
    parser.add_argument("--strict", action="store_true",
                        help="treat warnings as errors")
    parser.add_argument("--staged", action="store_true",
                        help="only lint agents/*.md staged for commit")
    args = parser.parse_args()

    if args.staged:
        targets = staged_agents()
        if not targets:
            print("lint_agents.py: no staged agents/*.md")
            return 0
    elif args.paths:
        targets = [p if p.is_absolute() else REPO / p for p in args.paths]
    else:
        targets = sorted(AGENTS_DIR.glob("*.md"))

    if not targets:
        sys.stderr.write("lint_agents.py: no agent files to lint\n")
        return 1

    spec_secs = spec_headings()
    claude_secs = claude_md_headings()

    total_errors: list[str] = []
    total_warnings: list[str] = []
    for path in targets:
        if not path.exists():
            total_errors.append(f"{path}: not found")
            continue
        errs, warns = lint_one(path, spec_secs, claude_secs)
        total_errors.extend(errs)
        total_warnings.extend(warns)

    if total_warnings:
        print(f"[warn] {len(total_warnings)} warning(s):")
        for w in total_warnings:
            print(f"  - {w}")
    if total_errors:
        print(f"[err ] {len(total_errors)} error(s):", file=sys.stderr)
        for e in total_errors:
            print(f"  - {e}", file=sys.stderr)

    fail = bool(total_errors) or (args.strict and total_warnings)
    if not fail:
        print("lint_agents.py: OK" + (" (with warnings)" if total_warnings else ""))
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
