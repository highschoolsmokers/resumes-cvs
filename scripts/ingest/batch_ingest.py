#!/usr/bin/env python3
"""Batch-ingest a list of job-listing URLs into applications/ folders.

Wraps url_ingest.py: for each URL, detect the source, fetch it
(Greenhouse / Lever / Ashby via ATS JSON APIs — no browser) or emit a stub
(LinkedIn / generic), and write applications/<Company>/<slug>-<date>/
listing.{json,md}. Does NO git (the folders are gitignored).

Prints ONE JSON array to stdout so the /batch-apply orchestrator knows each
folder and whether it is a stub that still needs a browser fetch or a pasted JD:

    [{"url", "folder", "company", "title", "source",
      "requires_chrome_mcp", "requires_user_fill", "error"}, ...]

Usage:
    python3 scripts/ingest/batch_ingest.py <url1> <url2> ...
    printf '%s\\n' <url1> <url2> | python3 scripts/ingest/batch_ingest.py --stdin
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import url_ingest as ing  # noqa: E402  — reuse detect/fetch/stub/write


def ingest_one(url: str) -> dict:
    entry: dict = {
        "url": url, "folder": None, "company": None, "title": None,
        "source": None, "requires_chrome_mcp": False,
        "requires_user_fill": False, "error": None,
    }
    try:
        source, ids = ing.detect_source(url)
        entry["source"] = source
        if source == "greenhouse":
            listing = ing.fetch_greenhouse(ids["token"], ids["id"])
        elif source == "lever":
            listing = ing.fetch_lever(ids["token"], ids["id"])
        elif source == "ashby":
            listing = ing.fetch_ashby(ids["token"], ids["id"])
        elif source == "linkedin":
            listing = ing.stub_linkedin(ids["id"], url)
        else:
            listing = ing.stub_generic(url)
    except Exception as e:  # noqa: BLE001 — ATS fetch/parse failure → generic stub
        entry["error"] = f"{type(e).__name__}: {e}"
        listing = ing.stub_generic(url)
        listing["requires_user_fill"] = True

    folder = ing.write_application(listing)
    entry["folder"] = str(folder)
    entry["company"] = listing.get("company")
    entry["title"] = listing.get("title")
    entry["requires_chrome_mcp"] = bool(listing.get("requires_chrome_mcp"))
    entry["requires_user_fill"] = bool(listing.get("requires_user_fill"))
    return entry


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("urls", nargs="*")
    ap.add_argument("--stdin", action="store_true",
                    help="also read URLs from stdin, one per line")
    ap.add_argument("--workers", type=int, default=8,
                    help="concurrent fetches (default 8)")
    args = ap.parse_args()

    urls = list(args.urls)
    if args.stdin:
        urls += [ln.strip() for ln in sys.stdin if ln.strip()]

    seen: set[str] = set()
    ordered: list[str] = []
    for u in urls:
        if u and u not in seen:
            seen.add(u)
            ordered.append(u)
    if not ordered:
        ap.error("no URLs given (pass URLs as args or via --stdin)")

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
        results = list(ex.map(ingest_one, ordered))

    json.dump(results, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
