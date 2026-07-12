#!/usr/bin/env python3
"""Voice index — route a cover letter to its calibration samples.

The `voice/` corpus is the set of real letters used to calibrate a new draft
(SPEC.md §7). Each sample carries YAML frontmatter tagging its **register**
(the closed set defined in `profile.md` → "Cover-letter registers") plus two
structural tags, **opener** and **close**. This script reads that frontmatter
and answers "given a register, which known-goods do I calibrate against, and
what shape does each take?" — so routing is deterministic instead of a
read-every-file guess.

It is the routing half of the cover-letter system; the *judgment* half is
the Trained criteria in `SPEC.md` §7 and the *mechanical* half is
`voice_lint.py` (the forbidden-phrase gate).

Frontmatter contract (top of each `voice/*.md`, before the prose annotation):

    ---
    register: qa-sdet
    opener: both-halves
    close: disposition
    establishes: one-line note on the structure this sample teaches
    approved: 2026-07-04
    ---

`register` is required on every sample and must be one of the keys in
`profile.md`. `opener` and `close` are required for job-search registers
(everything except `personal-literary`, which is excluded from routing).

Usage:

    python3 scripts/letter/voice_index.py --register qa-sdet   # shortlist one register
    python3 scripts/letter/voice_index.py --list               # whole catalog
    python3 scripts/letter/voice_index.py --lint                # validate every sample's tags

Runs on system python3 (3.11+); no third-party deps. Exit 1 on --lint failure.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]  # scripts/letter/voice_index.py → repo root
PROFILE = REPO / "profile.md"
VOICE_DIR = REPO / "voice"

NON_ROUTING = "personal-literary"  # valid register, but excluded from job-letter routing


# ─── profile.md: the closed register set + opener/close vocab ─────────────

def _registers_section(md: str) -> list[str]:
    """Return the body lines of the `## Cover-letter registers` section."""
    out: list[str] = []
    current = None
    for line in md.splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m and not line.startswith("###"):
            current = m.group(1).strip()
            continue
        if current == "Cover-letter registers":
            out.append(line)
    return out


def load_vocab(path: Path = PROFILE) -> dict:
    """Parse the closed register set and the opener/close vocab from profile.md.

    Registers come from the first backticked token on each table row; opener and
    close vocab come from the `- **opener:**` / `- **close:**` bullet lines.
    Keeping this parsed (not hardcoded) means profile.md is the single source.
    """
    if not path.exists():
        sys.stderr.write(f"voice_index.py: missing {path}\n")
        sys.exit(2)
    lines = _registers_section(path.read_text(encoding="utf-8"))
    if not lines:
        sys.stderr.write(
            "voice_index.py: no '## Cover-letter registers' section in profile.md\n"
        )
        sys.exit(2)

    registers: list[str] = []
    openers: list[str] = []
    closes: list[str] = []
    for line in lines:
        s = line.strip()
        if s.startswith("|") and "`" in s:
            # table row: first backticked token is the register key
            cells = [c.strip() for c in s.strip("|").split("|")]
            m = re.search(r"`([a-z0-9-]+)`", cells[0])
            if m:
                registers.append(m.group(1))
        elif s.startswith("- **opener:**"):
            openers = re.findall(r"`([a-z0-9-]+)`", s)
        elif s.startswith("- **close:**"):
            closes = re.findall(r"`([a-z0-9-]+)`", s)

    return {"registers": registers, "openers": openers, "closes": closes}


# ─── voice/*.md: frontmatter ─────────────────────────────────────────────

def parse_frontmatter(path: Path) -> dict | None:
    """Return the flat key:value frontmatter of a voice sample, or None if absent.

    Minimal parser: a `---` fence at the very top, `key: value` lines, closing
    `---`. Values are taken verbatim (trimmed). No nested YAML — the contract is
    flat by design.
    """
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    if end == -1:
        return None
    block = text[4:end]
    fm: dict = {}
    for line in block.splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        m = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if m:
            fm[m.group(1).strip()] = m.group(2).strip()
    return fm


def load_samples() -> list[dict]:
    """Every voice/*.md as {id, path, frontmatter or None}, sorted by id."""
    samples = []
    for path in sorted(VOICE_DIR.glob("*.md")):
        samples.append({
            "id": path.stem,
            "path": path,
            "fm": parse_frontmatter(path),
        })
    return samples


# ─── commands ────────────────────────────────────────────────────────────

def _fmt(sample: dict) -> str:
    fm = sample["fm"] or {}
    opener = fm.get("opener", "-")
    close = fm.get("close", "-")
    est = fm.get("establishes", "")
    head = f"  {sample['id']}"
    tags = f"[opener: {opener} · close: {close}]"
    return f"{head}\n    {tags}\n    {est}" if est else f"{head}\n    {tags}"


def cmd_list(samples: list[dict]) -> int:
    by_reg: dict[str, list[dict]] = {}
    for s in samples:
        reg = (s["fm"] or {}).get("register", "(untagged)")
        by_reg.setdefault(reg, []).append(s)
    for reg in sorted(by_reg):
        print(f"\n{reg}")
        for s in by_reg[reg]:
            print(_fmt(s))
    return 0


def cmd_register(samples: list[dict], key: str, vocab: dict) -> int:
    if key not in vocab["registers"]:
        sys.stderr.write(
            f"voice_index.py: '{key}' is not a register in profile.md. "
            f"Known: {', '.join(vocab['registers'])}\n"
        )
        return 2
    hits = [s for s in samples if (s["fm"] or {}).get("register") == key]
    if not hits:
        print(f"{key}: no known-goods tagged yet. Calibrate from the nearest register.")
        return 0
    print(f"{key} — calibrate against:")
    for s in hits:
        print(_fmt(s))
    return 0


def cmd_lint(samples: list[dict], vocab: dict) -> int:
    problems: list[str] = []
    for s in samples:
        fm = s["fm"]
        if fm is None:
            problems.append(f"{s['id']}: no frontmatter")
            continue
        reg = fm.get("register")
        if not reg:
            problems.append(f"{s['id']}: missing 'register'")
            continue
        if reg not in vocab["registers"]:
            problems.append(f"{s['id']}: register '{reg}' not in profile.md closed set")
            continue
        if reg == NON_ROUTING:
            continue  # non-routing: opener/close not required
        for tag, allowed in (("opener", vocab["openers"]), ("close", vocab["closes"])):
            val = fm.get(tag)
            if not val:
                problems.append(f"{s['id']}: missing '{tag}'")
            elif allowed and val not in allowed:
                problems.append(f"{s['id']}: {tag} '{val}' not in vocab ({', '.join(allowed)})")
    if problems:
        sys.stderr.write("voice_index.py: lint failed\n")
        for p in problems:
            sys.stderr.write(f"  - {p}\n")
        return 1
    print(f"voice_index.py: {len(samples)} samples OK")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--register", metavar="KEY", help="shortlist known-goods for one register")
    g.add_argument("--list", action="store_true", help="print the whole catalog")
    g.add_argument("--lint", action="store_true", help="validate every sample's frontmatter")
    args = ap.parse_args()

    if not VOICE_DIR.exists():
        sys.stderr.write(f"voice_index.py: no voice/ dir at {VOICE_DIR}\n")
        return 2

    vocab = load_vocab()
    samples = load_samples()

    if args.list:
        return cmd_list(samples)
    if args.lint:
        return cmd_lint(samples, vocab)
    return cmd_register(samples, args.register, vocab)


if __name__ == "__main__":
    sys.exit(main())
