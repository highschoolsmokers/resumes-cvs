#!/usr/bin/env python3
"""Top-K retrieval over the bullets / voice-corpus index built by build_index.py.

Usage:
    python3 scripts/retrieve.py --query "<text>" --k 8
    python3 scripts/retrieve.py --query-file <path> --k 5 --source voice
    cat jd-analysis.md | python3 scripts/retrieve.py --query-stdin --k 15

The agent calls this BEFORE reading the full bullets.yaml / voice-corpus.
The full file remains the source of truth — retrieval just focuses attention.

Output (stdout, JSON, one per line):
    {"id": "bullet:<id>", "score": 0.842, "text": "<bullet text>"}
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
STATE_DIR = REPO / "state"
EMBEDDINGS_NPZ = STATE_DIR / "embeddings.npz"
META_YAML = STATE_DIR / "index_meta.yaml"
BULLETS_YAML = REPO / "bullets.yaml"
VOICE_CORPUS = REPO / "voice-corpus"

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def stale_warning(meta: dict) -> str | None:
    """Detect drift between the index and current bullets.yaml / voice-corpus."""
    import hashlib

    if BULLETS_YAML.exists():
        cur_bullets = hashlib.sha256(BULLETS_YAML.read_bytes()).hexdigest()
        if meta.get("bullets_sha") != cur_bullets:
            return ("bullets.yaml has changed since the index was built. "
                    "Run `python3 scripts/build_index.py --rebuild`.")

    if VOICE_CORPUS.exists():
        parts = []
        for md in sorted(VOICE_CORPUS.glob("*.md")):
            parts.append(f"{md.name}:{md.stat().st_mtime_ns}")
        cur_voice = hashlib.sha256("\n".join(parts).encode()).hexdigest()
        if meta.get("voice_signature") != cur_voice:
            return ("voice-corpus has changed since the index was built. "
                    "Run `python3 scripts/build_index.py --rebuild`.")

    return None


def load_bullet_texts() -> dict[str, str]:
    data = yaml.safe_load(BULLETS_YAML.read_text()) or {}
    return {b["id"]: b["text"] for b in (data.get("bullets") or []) if "id" in b}


def load_voice_texts() -> dict[str, str]:
    out = {}
    if not VOICE_CORPUS.exists():
        return out
    for md in sorted(VOICE_CORPUS.glob("*.md")):
        if md.name == "README.md":
            continue
        chunks = [c.strip() for c in md.read_text().split("\n\n") if c.strip()]
        for idx, text in enumerate(chunks):
            out[f"{md.name}:{idx:03d}"] = text
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    qg = parser.add_mutually_exclusive_group(required=True)
    qg.add_argument("--query", help="query text inline")
    qg.add_argument("--query-file", type=Path, help="read query from a file")
    qg.add_argument("--query-stdin", action="store_true", help="read query from stdin")
    parser.add_argument("--k", type=int, default=8, help="top-K (default 8)")
    parser.add_argument("--source", choices=["bullets", "voice"], default="bullets",
                        help="which index to query (default: bullets)")
    args = parser.parse_args()

    if not EMBEDDINGS_NPZ.exists() or not META_YAML.exists():
        sys.stderr.write("retrieve.py: no index found. "
                         "Run `python3 scripts/build_index.py` first.\n")
        return 1

    meta = yaml.safe_load(META_YAML.read_text()) or {}
    warning = stale_warning(meta)
    if warning:
        sys.stderr.write(f"retrieve.py WARNING: {warning}\n")

    if args.query:
        query = args.query
    elif args.query_file:
        query = args.query_file.read_text()
    else:
        query = sys.stdin.read()
    query = query.strip()
    if not query:
        sys.stderr.write("retrieve.py: empty query\n")
        return 1

    import numpy as np
    from sentence_transformers import SentenceTransformer

    data = np.load(EMBEDDINGS_NPZ)
    if args.source == "bullets":
        vecs = data["bullet_vecs"]
        ids = meta.get("bullet_ids", [])
        text_map = load_bullet_texts()
        id_prefix = "bullet"
    else:
        vecs = data["voice_vecs"]
        ids = meta.get("voice_ids", [])
        text_map = load_voice_texts()
        id_prefix = "voice"

    if vecs.shape[0] == 0:
        sys.stderr.write(f"retrieve.py: index for --source {args.source} is empty\n")
        return 1

    model = SentenceTransformer(MODEL_NAME)
    qv = model.encode([query], normalize_embeddings=True)[0].astype("float32")

    # Cosine similarity (vectors are L2-normalized → cosine == dot product)
    scores = vecs @ qv
    top = np.argsort(-scores)[: args.k]

    for idx in top:
        item_id = ids[int(idx)]
        score = float(scores[int(idx)])
        text = text_map.get(item_id, "")
        json.dump({"id": f"{id_prefix}:{item_id}", "score": round(score, 4), "text": text},
                  sys.stdout)
        sys.stdout.write("\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
