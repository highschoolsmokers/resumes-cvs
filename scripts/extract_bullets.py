#!/usr/bin/env python3
"""
One-time helper: pull every plausible bullet / summary line from each known
resume DOCX so we can hand-curate `bullets.yaml`.

Output is written to stdout as a markdown-ish dump grouped by file. The
downstream step is human: WS Gong verifies every line before we put it in
`bullets.yaml` (see CLAUDE.md §2 Phase 2).
"""
from __future__ import annotations

import sys
from pathlib import Path

from docx import Document

REPO = Path(__file__).resolve().parent.parent

SOURCES = [
    REPO / "WSGong_Resume_Template.docx",
    REPO / "2026-04-17-wsgong-resume-generalized.docx",
    REPO / "NVIDIA" / "billy-gong-resume-2026.docx",
    REPO / "Vercel" / "WSGong_Resume_Vercel.docx",
    REPO / "Handshake" / "WSGong_Resume_AdversarialAI.docx",
    REPO / "APublicSpace" / "WSGong_Resume_APublicSpace.docx",
    REPO / "MarineLayer" / "WSGong_Resume_MarineLayer.docx",
    REPO / "SFMOMA" / "WSGong_Resume_SFMOMA.docx",
]


def iter_text(doc: Document):
    """Walk every paragraph in the main doc body, then every table cell.

    The Swiss template keeps body content in paragraphs plus a 5-row table,
    so we have to look in both places.
    """
    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            yield ("para", text)

    for table in doc.tables:
        for row_idx, row in enumerate(table.rows):
            for cell_idx, cell in enumerate(row.cells):
                for para in cell.paragraphs:
                    text = para.text.strip()
                    if text:
                        yield (f"table[{row_idx},{cell_idx}]", text)


def dump(path: Path) -> None:
    print(f"\n\n===== {path.relative_to(REPO)} =====")
    if not path.exists():
        print("(missing)")
        return
    doc = Document(str(path))
    seen = set()
    for location, text in iter_text(doc):
        # Collapse exact duplicates per-file (the template has repeated shells).
        key = (location, text)
        if key in seen:
            continue
        seen.add(key)
        print(f"- [{location}] {text}")


def main() -> int:
    for path in SOURCES:
        dump(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
