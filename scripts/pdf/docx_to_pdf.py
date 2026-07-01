#!/usr/bin/env python3
"""Render one or more `.docx` files to `.pdf` via headless LibreOffice.

Usage:
    python scripts/pdf/docx_to_pdf.py <input.docx> [--out <output.pdf>]
    python scripts/pdf/docx_to_pdf.py <a.docx> <b.docx> [<c.docx> ...]   # batch

Batch mode: a single `soffice` invocation converts all inputs in one cold
start (~3-4s saved per additional file). PDFs are written as siblings of the
inputs (foo.docx → foo.pdf). `--out` is only meaningful with a single input.

We use LibreOffice headless, not `docx2pdf` (SPEC.md §9 Implementation).
Reason: `docx2pdf` shells out to Word or Pages on macOS and those need a GUI
session; LibreOffice works headless and handles our Inter/#D44500 OOXML
identically to what Word renders. Each run uses a private `-env:UserInstallation`
profile so it never contends with another `soffice` instance.

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
import tempfile
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

    LibreOffice names each output by the input's stem, so two inputs sharing a
    stem (e.g. every application folder's `resume.docx`) would collide. We stage
    each input into one scratch dir under a unique indexed name, run one soffice
    pass, then move each result to its intended sibling PDF. One cold start, N
    files, no stem collisions.
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

    # Unique scratch dir + private LibreOffice profile per run, so concurrent
    # runs and any other open soffice instance never contend for the profile.
    parents = {p.parent for p in out_pdfs}
    scratch_root = next(iter(parents)) if len(parents) == 1 else Path(tempfile.gettempdir())
    scratch_root.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix=".docx_to_pdf_", dir=scratch_root))
    profile_dir = Path(tempfile.mkdtemp(prefix="soffice_profile_"))

    try:
        # Stage inputs under unique stems so same-named files can't overwrite.
        staged: list[tuple[Path, Path]] = []  # (scratch_pdf, out_pdf)
        scratch_docxs: list[Path] = []
        for i, (docx, out_pdf) in enumerate(zip(docxs, out_pdfs)):
            uniq = f"{i:04d}_{docx.stem}"
            scratch_docx = scratch / f"{uniq}.docx"
            shutil.copyfile(docx, scratch_docx)
            scratch_docxs.append(scratch_docx)
            staged.append((scratch / f"{uniq}.pdf", out_pdf))

        soffice = find_soffice()
        cmd = [soffice, f"-env:UserInstallation=file://{profile_dir}",
               "--headless", "--convert-to", "pdf", "--outdir", str(scratch)]
        cmd.extend(str(d) for d in scratch_docxs)
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
        for scratch_pdf, out_pdf in staged:
            if not scratch_pdf.exists():
                sys.stderr.write(
                    f"docx_to_pdf.py: LibreOffice ran but produced no PDF for "
                    f"{out_pdf.name}. Expected {scratch_pdf}. stdout:\n{result.stdout}\n"
                )
                sys.exit(4)
            out_pdf.parent.mkdir(parents=True, exist_ok=True)
            if out_pdf.exists():
                out_pdf.unlink()
            shutil.move(str(scratch_pdf), str(out_pdf))
            produced_paths.append(out_pdf)

        return produced_paths
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
        shutil.rmtree(profile_dir, ignore_errors=True)


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
