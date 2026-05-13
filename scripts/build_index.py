#!/usr/bin/env python3
"""Build the semantic retrieval index over bullets.yaml + voice-corpus/.

Stores everything under `state/` (gitignored). Idempotent — if bullets.yaml
SHA and voice-corpus mtimes haven't moved, exits as a no-op. `--rebuild`
forces a fresh build.

Why this exists: the resume-tailor and cover-letter-writer agents both
linearly scan their full corpora today. As bullets.yaml grows past ~200
entries that read becomes slow AND signal-diluting. With a vector index,
`scripts/retrieve.py` returns the top-K most JD-relevant items in ms.

Usage:
    python3 scripts/build_index.py             # incremental
    python3 scripts/build_index.py --rebuild   # force full rebuild
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
BULLETS_YAML = REPO / "bullets.yaml"
VOICE_CORPUS = REPO / "voice-corpus"
STATE_DIR = REPO / "state"
EMBEDDINGS_NPZ = STATE_DIR / "embeddings.npz"
META_YAML = STATE_DIR / "index_meta.yaml"

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def voice_corpus_signature() -> str:
    """A signature that changes when any voice-corpus file is added/modified."""
    if not VOICE_CORPUS.exists():
        return ""
    parts = []
    for md in sorted(VOICE_CORPUS.glob("*.md")):
        parts.append(f"{md.name}:{md.stat().st_mtime_ns}")
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()


def load_bullets() -> list[dict]:
    """Return the list of bullets with `id` and `text` fields, in file order."""
    data = yaml.safe_load(BULLETS_YAML.read_text()) or {}
    out = []
    for b in data.get("bullets", []) or []:
        bid = b.get("id")
        text = b.get("text")
        if bid and text:
            out.append({"id": bid, "text": text})
    return out


def split_voice_paragraphs() -> list[dict]:
    """Return [{id: '<filename>:<idx>', text: '<paragraph>'}, …]."""
    out = []
    if not VOICE_CORPUS.exists():
        return out
    for md in sorted(VOICE_CORPUS.glob("*.md")):
        if md.name == "README.md":
            continue
        chunks = [c.strip() for c in md.read_text().split("\n\n") if c.strip()]
        for idx, text in enumerate(chunks):
            out.append({"id": f"{md.name}:{idx:03d}", "text": text})
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rebuild", action="store_true",
                        help="ignore cached meta; rebuild from scratch")
    args = parser.parse_args()

    STATE_DIR.mkdir(parents=True, exist_ok=True)

    bullets_sha = file_sha(BULLETS_YAML)
    voice_sig = voice_corpus_signature()

    # Skip if nothing changed
    if not args.rebuild and META_YAML.exists() and EMBEDDINGS_NPZ.exists():
        meta = yaml.safe_load(META_YAML.read_text()) or {}
        if (meta.get("bullets_sha") == bullets_sha and
                meta.get("voice_signature") == voice_sig and
                meta.get("model") == MODEL_NAME):
            print(f"build_index.py: index up-to-date ({EMBEDDINGS_NPZ})")
            return 0

    # Lazy imports — these are heavy and we want the no-op path to stay fast.
    import numpy as np
    from sentence_transformers import SentenceTransformer

    print(f"build_index.py: loading {MODEL_NAME} (first run pulls ~80 MB)…")
    model = SentenceTransformer(MODEL_NAME)

    bullets = load_bullets()
    voice = split_voice_paragraphs()

    if not bullets and not voice:
        sys.stderr.write("build_index.py: nothing to index (bullets.yaml empty, "
                         "voice-corpus empty). Exiting without writing.\n")
        return 1

    print(f"build_index.py: embedding {len(bullets)} bullets, "
          f"{len(voice)} voice passages…")
    bullet_vecs = model.encode([b["text"] for b in bullets],
                               normalize_embeddings=True,
                               show_progress_bar=False) if bullets else np.zeros((0, 384))
    voice_vecs = model.encode([v["text"] for v in voice],
                              normalize_embeddings=True,
                              show_progress_bar=False) if voice else np.zeros((0, 384))

    np.savez(EMBEDDINGS_NPZ,
             bullet_vecs=bullet_vecs.astype("float32"),
             voice_vecs=voice_vecs.astype("float32"))

    META_YAML.write_text(yaml.safe_dump({
        "model": MODEL_NAME,
        "bullets_sha": bullets_sha,
        "voice_signature": voice_sig,
        "bullet_ids": [b["id"] for b in bullets],
        "voice_ids": [v["id"] for v in voice],
    }, sort_keys=False))

    print(f"build_index.py: wrote {EMBEDDINGS_NPZ} "
          f"({EMBEDDINGS_NPZ.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
