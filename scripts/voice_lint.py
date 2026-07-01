#!/usr/bin/env python3
"""Voice lint — mechanical tells only, for job-search cover letters.

This is the enforceable half of the "safeguards" plan: a check that runs
OUTSIDE the model's judgment. It catches the specific mechanical tells that
kept slipping into drafts (profile.md Voice). It does NOT judge "voice" — that
is what the known-good examples in `voice/` are for.

Deliberately conservative: every rule is a concrete pattern, scoped so it does
NOT flag anything in the approved known-good letter. Rules that would produce
false positives on W.S.'s real style (e.g. a blanket "colon-then-list" ban —
he uses colon lists in P1 and P3) are intentionally omitted.

What it CANNOT catch, by design: semantic flourishes ("so the docs read
clearly"), buried ledes, over-claiming. A regex can't see those without
false-flagging real prose. Those stay the job of the example + human review.

Usage:
    python scripts/voice_lint.py applications/<...>/cover-letter.md
    python scripts/voice_lint.py --list      # print the rules
Exit code 1 if any tell is found, 0 if clean.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
VOICE_MD = REPO / "profile.md"  # forbidden-phrase list parsed from the ## Forbidden phrases heading in profile.md


# ─── body extraction (mirrors build_cover_letter.parse_letter_md) ──────────

def body_paragraphs(md_path: Path) -> list[str]:
    """Blocks between blank lines; drop salutation (first) and signature (last)."""
    text = md_path.read_text(encoding="utf-8")
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)  # drop HTML comments
    blocks: list[str] = []
    buf: list[str] = []
    for line in text.splitlines():
        if line.strip() == "":
            if buf:
                blocks.append(" ".join(b.strip() for b in buf).strip())
                buf = []
        else:
            buf.append(line)
    if buf:
        blocks.append(" ".join(b.strip() for b in buf).strip())
    blocks = [b for b in blocks if b]
    return blocks[1:-1] if len(blocks) >= 3 else blocks


def first_sentence(paras: list[str]) -> str:
    if not paras:
        return ""
    return re.split(r"(?<=[.?!])\s", paras[0], maxsplit=1)[0]


# ─── forbidden phrases from SPEC.md (promoted from warn → fail) ───────────

def load_forbidden(path: Path = VOICE_MD) -> list[str]:
    if not path.exists():
        return []
    out: list[str] = []
    in_section = False
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            in_section = m.group(1).strip().lower() == "forbidden phrases"
            continue
        if in_section and line.strip().startswith("- "):
            out.append(line.strip()[2:].strip().lower())
    return out


# ─── rules ─────────────────────────────────────────────────────────────────
# Each rule: (name, human description, callable(body, first_sent) -> snippet|None)

def _rule_em_dash(body: str, first: str) -> str | None:
    # Em-dash banned in the job-search register. En-dash (–) for ranges is fine.
    m = re.search(r"\S*\s*—\s*\S*", body)
    return m.group(0).strip() if m else None


def _rule_fronted_time_opener(body: str, first: str) -> str | None:
    # The OPENING sentence must not be a fronted time-span hook.
    pat = re.compile(
        r"^\s*(i have spent|i've spent|having spent|for the (last|past)\b|"
        r"for \w+ years|over the (last|past)\b)",
        re.I,
    )
    return first if pat.match(first) else None


def _rule_rote_application(body: str, first: str) -> str | None:
    # "I am writing to apply/express", "I'm applying for" — the form-letter open.
    # NOTE: "I am interested in the ___ position" is NOT flagged (W.S. uses it).
    m = re.search(r"\b(i am writing to (apply|express)|i['’]?m applying for|"
                  r"i am applying for)\b", body, re.I)
    return m.group(0) if m else None


def _rule_clipped_role_pointer(body: str, first: str) -> str | None:
    # "That's the ___ role/position" clipped pivot.
    m = re.search(r"\bthat['’]?s the\b[^.?!]{0,50}\b(role|position)\b", body, re.I)
    return m.group(0) if m else None


def _rule_forbidden(body: str, first: str) -> str | None:
    low = body.lower()
    for phrase in load_forbidden():
        if phrase and phrase in low:
            return phrase
    return None


RULES = [
    ("em-dash", "no em-dashes in the job-search register (en-dash for ranges is ok)", _rule_em_dash),
    ("fronted-time-opener", "first sentence must not open with a time-span hook (\"I have spent N years...\")", _rule_fronted_time_opener),
    ("rote-application-open", "no \"I am writing to apply/express\" / \"I'm applying for\" (\"interested in\" is fine)", _rule_rote_application),
    ("clipped-role-pointer", "no \"That's the ___ role\" clipped pivot", _rule_clipped_role_pointer),
    ("forbidden-phrase", "no phrase from SPEC.md → Forbidden phrases", _rule_forbidden),
]


def lint(md_path: Path) -> list[tuple[str, str]]:
    paras = body_paragraphs(md_path)
    body = " ".join(paras)
    first = first_sentence(paras)
    findings: list[tuple[str, str]] = []
    for name, _desc, fn in RULES:
        snippet = fn(body, first)
        if snippet:
            findings.append((name, snippet))
    return findings


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", nargs="?", type=Path, help="cover-letter.md to lint")
    ap.add_argument("--list", action="store_true", help="print the rules and exit")
    args = ap.parse_args()

    if args.list:
        for name, desc, _ in RULES:
            print(f"  {name:22} {desc}")
        return 0
    if not args.path:
        ap.error("path is required (or use --list)")
    if not args.path.exists():
        sys.exit(f"voice_lint: file not found: {args.path}")

    findings = lint(args.path)
    if not findings:
        print(f"voice_lint: clean — {args.path}")
        return 0
    sys.stderr.write(f"voice_lint: {len(findings)} tell(s) in {args.path}\n")
    for name, snippet in findings:
        sys.stderr.write(f"  [{name}] → {snippet!r}\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
