#!/usr/bin/env python3
"""Render a `.docx` file to `.pdf` via headless LibreOffice.

Usage:
    python scripts/docx_to_pdf.py <input.docx> [--out <output.pdf>]

Decision committed in spec §8.6 / CLAUDE.md §4: we use LibreOffice headless,
not `docx2pdf`. Reason: `docx2pdf` shells out to Word or Pages on macOS and
those need a GUI session; LibreOffice works from cron / scheduled tasks and
handles our Raleway+Lato+#D44500 OOXML identically to what Word renders.

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


def convert(docx: Path, out_pdf: Path) -> Path:
    """Invoke `soffice --headless --convert-to pdf` and move the result into place.

    LibreOffice writes the PDF next to the input with the same stem. We don't
    get to choose the output name through CLI args, so we run it into a scratch
    directory and rename.
    """
    if not docx.exists():
        sys.stderr.write(f"docx_to_pdf.py: input not found: {docx}\n")
        sys.exit(1)
    if docx.suffix.lower() != ".docx":
        sys.stderr.write(f"docx_to_pdf.py: expected a .docx, got {docx.suffix}\n")
        sys.exit(1)

    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    soffice = find_soffice()
    scratch = out_pdf.parent / ".docx_to_pdf_scratch"
    scratch.mkdir(parents=True, exist_ok=True)

    cmd = [
        soffice,
        "--headless",
        "--convert-to", "pdf",
        "--outdir", str(scratch),
        str(docx),
    ]
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

    produced = scratch / (docx.stem + ".pdf")
    if not produced.exists():
        sys.stderr.write(
            "docx_to_pdf.py: LibreOffice ran but produced no PDF. "
            f"Expected {produced}. stdout:\n{result.stdout}\n"
        )
        sys.exit(4)

    if out_pdf.exists():
        out_pdf.unlink()
    shutil.move(str(produced), str(out_pdf))
    # Best-effort scratch cleanup; OK if it's already gone.
    try:
        shutil.rmtree(scratch)
    except OSError:
        pass
    return out_pdf


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("docx", type=Path, help="input .docx path")
    parser.add_argument("--out", type=Path, default=None,
                        help="output .pdf path (default: sibling of input with .pdf)")
    args = parser.parse_args()

    out = args.out or args.docx.with_suffix(".pdf")
    pdf = convert(args.docx, out)
    size = pdf.stat().st_size
    print(f"PDF written → {pdf}  ({size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
