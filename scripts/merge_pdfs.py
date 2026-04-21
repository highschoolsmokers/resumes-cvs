#!/usr/bin/env python3
"""Merge several PDFs into one, preserving page order.

Usage:
    python scripts/merge_pdfs.py <out.pdf> <in1.pdf> <in2.pdf> [in3.pdf ...]

Convention from spec §8.6 / CLAUDE.md §1.5: the resume goes first, the cover
letter goes second. That produces the `combined.pdf` that lives beside each
application and is what gets uploaded wherever a single PDF is required.

If an input PDF is missing or unreadable we fail loud with an actionable
error rather than silently dropping it.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def merge(out_pdf: Path, inputs: list[Path]) -> Path:
    try:
        from pypdf import PdfWriter, PdfReader  # type: ignore
    except ImportError:  # pragma: no cover
        sys.stderr.write(
            "merge_pdfs.py needs pypdf.\n"
            "    pip install pypdf --break-system-packages\n"
        )
        sys.exit(1)

    if not inputs:
        sys.stderr.write("merge_pdfs.py: no input PDFs given\n")
        sys.exit(1)
    for path in inputs:
        if not path.exists():
            sys.stderr.write(f"merge_pdfs.py: input not found: {path}\n")
            sys.exit(1)
        if path.suffix.lower() != ".pdf":
            sys.stderr.write(f"merge_pdfs.py: not a .pdf: {path}\n")
            sys.exit(1)

    writer = PdfWriter()
    for path in inputs:
        reader = PdfReader(str(path))
        for page in reader.pages:
            writer.add_page(page)

    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    with out_pdf.open("wb") as f:
        writer.write(f)
    writer.close()
    return out_pdf


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("out", type=Path, help="output .pdf path")
    parser.add_argument("inputs", nargs="+", type=Path,
                        help="input PDFs in desired order (resume first, cover letter second)")
    args = parser.parse_args()

    merged = merge(args.out, args.inputs)
    size = merged.stat().st_size
    print(f"Merged PDF written → {merged}  ({size:,} bytes, "
          f"{len(args.inputs)} inputs)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
