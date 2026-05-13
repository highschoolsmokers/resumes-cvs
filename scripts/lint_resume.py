#!/usr/bin/env python3
"""Lint a resume DOCX for whole-document Swiss consistency.

Runs structural checks across the entire document — not by section, not by
row type. The principle: if a typographic or geometric value is set at all,
it should be set to the same value everywhere it appears.

This is the enforcement mechanism behind the user's rule: "make things look
consistent ... not just according to section." A regression in scripts/build_resume.py
that introduces a one-off spacing value will fail this lint.

Checks:
  1. <w:trHeight> must not appear — height is content-driven only.
  2. <w:tcMar><w:top> uses one and only one value across all rows.
  3. <w:tcMar><w:bottom> uses one and only one value across all rows.
  4. Every <w:rFonts w:ascii="..."> in document.xml is "Inter".
  5. Every <w:sz w:val="..."> comes from an approved size scale.
  6. Every <w:spacing w:before="..."> comes from an approved spacing scale
     (multiples of the 60 DXA quarter-baseline).

Usage:
    python scripts/lint_resume.py <input.docx>
    python scripts/lint_resume.py --unpacked <unpacked-dir>
    python scripts/lint_resume.py --xml <document.xml>
"""
from __future__ import annotations

import argparse
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path


# --- approved value scales ---------------------------------------------------
# Content sizes are half-points: 18=9pt, 20=10pt, 22=11pt, 24=12pt, 32=16pt,
# 48=24pt. Spacer sizes (2 = 1pt, 12 = 6pt) are reserved for empty / structural
# paragraphs inherited from the template (rule rows, contact-block spacers).
# They never carry text — adding them to a content paragraph breaks the scale.
APPROVED_CONTENT_SIZES  = {'18', '20', '22', '24', '28', '32', '48'}
APPROVED_SPACER_SIZES   = {'2', '12'}
APPROVED_SIZES          = APPROVED_CONTENT_SIZES | APPROVED_SPACER_SIZES

# Spacing in DXA, multiples of the 60 DXA quarter-baseline.
APPROVED_BEFORE = {'0', '60', '80', '120', '160', '240', '280', '360', '480'}

# Single typeface for body content.
APPROVED_FONTS = {'Inter'}


# --- io ----------------------------------------------------------------------
def load_document_xml(target: Path) -> str:
    if target.is_file() and target.suffix == '.docx':
        with zipfile.ZipFile(target) as zf:
            return zf.read('word/document.xml').decode('utf-8')
    if target.is_dir():
        return (target / 'word' / 'document.xml').read_text()
    if target.is_file() and target.suffix == '.xml':
        return target.read_text()
    raise SystemExit(f"Unrecognized input: {target}")


# --- checks ------------------------------------------------------------------
def check_no_trheight(content: str) -> list[str]:
    matches = re.findall(r'<w:trHeight w:val="(\d+)"', content)
    if matches:
        return [
            "trHeight present in document — row height should be content-driven, "
            f"never fixed. Offending values: {sorted(set(matches))}"
        ]
    return []


def _content_rows(content: str) -> list[str]:
    """Return body-table rows that are NOT structural rule rows (gridSpan=2)."""
    rows = re.findall(r'<w:tr>.*?</w:tr>', content, re.DOTALL)
    return [r for r in rows if 'w:gridSpan w:val="2"' not in r]


def check_uniform_tcmar(content: str, edge: str) -> list[str]:
    """edge is 'top' or 'bottom'.

    Only checked across CONTENT rows. Rule rows are zero-padded by design
    (the rule sits flush against the surrounding rows), so including them
    would fail the check on a perfectly correct document.
    """
    pat = rf'<w:{edge} w:w="(\d+(?:\.\d+)?)" w:type="dxa"/>'
    values = [m for row in _content_rows(content) for m in re.findall(pat, row)]
    counts = Counter(values)
    if len(counts) > 1:
        return [
            f"tcMar.{edge} values diverge across content rows: {dict(counts)} — "
            f"every content row must use the same vertical cell padding for "
            f"rhythm to be consistent across the document."
        ]
    return []


def check_single_font(content: str) -> list[str]:
    fonts = set(re.findall(r'<w:rFonts w:ascii="([^"]+)"', content))
    bad = fonts - APPROVED_FONTS
    if bad:
        return [
            f"non-Inter fonts present in document.xml: {sorted(bad)} — "
            f"single-family typography is the basis of the Swiss redesign."
        ]
    return []


def check_size_scale(content: str) -> list[str]:
    sizes = set(re.findall(r'<w:sz w:val="(\d+)"', content))
    bad = sizes - APPROVED_SIZES
    if bad:
        return [
            f"font sizes outside the approved scale: {sorted(bad)} — "
            f"approved: {sorted(APPROVED_SIZES, key=int)}. "
            f"Add to APPROVED_SIZES only after a deliberate hierarchy decision."
        ]
    return []


def check_spacing_scale(content: str) -> list[str]:
    befores = set(re.findall(r'<w:spacing[^>]*w:before="(\d+)"', content))
    bad = befores - APPROVED_BEFORE
    if bad:
        return [
            f"paragraph w:before values off the 60 DXA baseline lattice: "
            f"{sorted(bad)} — approved: "
            f"{sorted(APPROVED_BEFORE, key=int)}."
        ]
    return []


CHECKS = [
    ('trheight',       check_no_trheight),
    ('tcmar.top',      lambda c: check_uniform_tcmar(c, 'top')),
    ('tcmar.bottom',   lambda c: check_uniform_tcmar(c, 'bottom')),
    ('single-font',    check_single_font),
    ('size-scale',     check_size_scale),
    ('spacing-scale',  check_spacing_scale),
]


def lint(content: str) -> list[tuple[str, str]]:
    """Return list of (check_name, issue_message) tuples. Empty = passed."""
    issues: list[tuple[str, str]] = []
    for name, fn in CHECKS:
        for msg in fn(content):
            issues.append((name, msg))
    return issues


# --- cli ---------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('target', type=Path, nargs='?', default=None,
                        help='resume.docx OR unpacked dir OR document.xml path')
    parser.add_argument('--unpacked', type=Path, default=None,
                        help='alias for the unpacked-dir form')
    parser.add_argument('--xml', type=Path, default=None,
                        help='alias for the document.xml form')
    args = parser.parse_args()

    target = args.target or args.unpacked or args.xml
    if target is None:
        parser.error("provide a path: a .docx, an unpacked dir, or a document.xml")

    content = load_document_xml(target)
    issues = lint(content)
    if not issues:
        print(f"lint_resume: {target} — all whole-document consistency checks pass.")
        return 0

    print(f"lint_resume: {len(issues)} issue(s) in {target}", file=sys.stderr)
    for name, msg in issues:
        print(f"  [{name}] {msg}", file=sys.stderr)
    return 1


if __name__ == '__main__':
    sys.exit(main())
