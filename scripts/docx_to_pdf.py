#!/usr/bin/env python3
"""Render one or more `.docx` files to `.pdf` via headless LibreOffice.

Usage:
    python scripts/docx_to_pdf.py <input.docx> [--out <output.pdf>]
    python scripts/docx_to_pdf.py <a.docx> <b.docx> [<c.docx> ...]   # batch

Batch mode: a single `soffice` invocation converts all inputs in one cold
start (~3-4s saved per additional file). PDFs are written as siblings of the
inputs (foo.docx → foo.pdf). `--out` is only meaningful with a single input.

Decision committed in spec §8.6 / CLAUDE.md §4: we use LibreOffice headless,
not `docx2pdf`. Reason: `docx2pdf` shells out to Word or Pages on macOS and
those need a GUI session; LibreOffice works from cron / scheduled tasks and
handles our Inter/#D44500 OOXML identically to what Word renders.

The Homebrew install target is:
    brew install --cask libreoffice

If LibreOffice is not installed we fail loud with an actionable message
rather than producing a silent bad output.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


SOFFICE_CANDIDATES = [
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",  # Homebrew cask
    "/usr/bin/soffice",                                      # Linux apt / Homebrew
    "/usr/bin/libreoffice",
    "/opt/homebrew/bin/soffice",
    "/opt/homebrew/bin/libreoffice",
    "soffice",                                               # whatever's on $PATH
    "libreoffice",
]


def find_soffice() -> str:
    """Return the first soffice binary we can actually run."""
    env_path = os.environ.get("LIBREOFFICE_BIN")
    if env_path:
        return env_path
    for candidate in SOFFICE_CANDIDATES:
        resolved = shutil.which(candidate) if "/" not in candidate else (
            candidate if Path(candidate).exists() else None
        )
        if resolved:
            return resolved
    sys.stderr.write(
        "docx_to_pdf.py: LibreOffice not found.\n"
        "  Install: brew install --cask libreoffice\n"
        "  Or set LIBREOFFICE_BIN=/path/to/soffice\n"
    )
    sys.exit(2)


def convert_batch(docxs: list[Path], out_pdfs: list[Path]) -> list[Path]:
    """Convert a list of .docx files in a single `soffice` invocation.

    LibreOffice writes each PDF next to the input with the same stem. We don't
    get to choose names through CLI args, so we run into a shared scratch
    directory and rename into place. One process, one cold start, N files.
    """
    if not docxs:
        return []
    if len(docxs) != len(out_pdfs):
        raise ValueError("docxs and out_pdfs must be the same length")
    for d in docxs:
        if not d.exists():
            sys.stderr.write(f"docx_to_pdf.py: input not found: {d}\n")
            sys.exit(1)
        if d.suffix.lower() != ".docx":
            sys.stderr.write(f"docx_to_pdf.py: expected a .docx, got {d.suffix}\n")
            sys.exit(1)
    # LibreOffice writes outputs to scratch keyed by stem; same stem from two
    # inputs would collide. Guard against silent overwrite.
    stems = [d.stem for d in docxs]
    if len(set(stems)) != len(stems):
        dupes = sorted({s for s in stems if stems.count(s) > 1})
        sys.stderr.write(f"docx_to_pdf.py: input files share stems "
                         f"({', '.join(dupes)}); LibreOffice would overwrite.\n"
                         "Rename inputs or convert separately.\n")
        sys.exit(1)

    # Single shared scratch dir at the first output's parent (or /tmp if mixed).
    parents = {p.parent for p in out_pdfs}
    if len(parents) == 1:
        scratch_root = next(iter(parents))
    else:
        scratch_root = Path("/tmp")
    scratch_root.mkdir(parents=True, exist_ok=True)
    scratch = scratch_root / ".docx_to_pdf_scratch"
    scratch.mkdir(parents=True, exist_ok=True)

    soffice = find_soffice()
    cmd = [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(scratch)]
    cmd.extend(str(d) for d in docxs)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        sys.stderr.write(f"docx_to_pdf.py: could not execute {soffice!r}\n")
        sys.exit(2)

    if result.returncode != 0:
        sys.stderr.write("docx_to_pdf.py: LibreOffice exited non-zero.\n")
        sys.stderr.write(result.stdout)
        sys.stderr.write(result.stderr)
        sys.exit(result.returncode or 3)

    produced_paths = []
    for docx, out_pdf in zip(docxs, out_pdfs):
        produced = scratch / (docx.stem + ".pdf")
        if not produced.exists():
            sys.stderr.write(
                f"docx_to_pdf.py: LibreOffice ran but produced no PDF for {docx}. "
                f"Expected {produced}. stdout:\n{result.stdout}\n"
            )
            sys.exit(4)
        out_pdf.parent.mkdir(parents=True, exist_ok=True)
        if out_pdf.exists():
            out_pdf.unlink()
        shutil.move(str(produced), str(out_pdf))
        produced_paths.append(out_pdf)

    try:
        shutil.rmtree(scratch)
    except OSError:
        pass
    return produced_paths


def convert(docx: Path, out_pdf: Path) -> Path:
    """Convert a single .docx. Thin wrapper around convert_batch for back-compat."""
    return convert_batch([docx], [out_pdf])[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("docx", type=Path, nargs="+",
                        help="one or more input .docx paths")
    parser.add_argument("--out", type=Path, default=None,
                        help="output .pdf path (single-input mode only; "
                             "batch mode writes siblings)")
    args = parser.parse_args()

    if len(args.docx) > 1 and args.out is not None:
        sys.stderr.write("docx_to_pdf.py: --out is only valid with a single input. "
                         "In batch mode, PDFs are written as siblings.\n")
        return 1

    if len(args.docx) == 1 and args.out is not None:
        out_pdfs = [args.out]
    else:
        out_pdfs = [d.with_suffix(".pdf") for d in args.docx]

    pdfs = convert_batch(args.docx, out_pdfs)
    for pdf in pdfs:
        size = pdf.stat().st_size
        print(f"PDF written → {pdf}  ({size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
