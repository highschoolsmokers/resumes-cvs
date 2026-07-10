#!/usr/bin/env python3
"""Domain → fetch-recipe registry — "training fetches" for the ingest step.

The problem this solves: for a JS-rendered / bot-walled listing site, the first
time we hit it we burn a round of trial GETs figuring out which route actually
returns the JD (direct HTTP? reader proxy? a .json endpoint? a browser UA?).
That knowledge used to scatter into ad-hoc memory files. This registry captures
it once, keyed by domain, so the *next* listing from the same domain skips the
tests and goes straight to the working method.

Data lives in `fetch_recipes.json` next to this file. A recipe is matched by the
longest registered hostname suffix of the URL (so a recipe for `amazon.jobs`
covers `www.amazon.jobs`).

CLI:
    python3 scripts/ingest/fetch_recipes.py <url>          # print the recipe for a URL
    python3 scripts/ingest/fetch_recipes.py --list         # dump the whole registry
    python3 scripts/ingest/fetch_recipes.py record \\      # train a newly-solved domain
        --domain amazon.jobs --method curl_browser_ua \\
        --note "..." [--command "curl ... '{url}'"] [--extract "..."] \\
        [--verified 2026-07-04] [--source-memory reference_amazon_jobs_jd_fetch]

As a module:
    from fetch_recipes import lookup
    recipe = lookup(url)   # dict or None
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REGISTRY = Path(__file__).resolve().with_name("fetch_recipes.json")

METHODS = (
    "ats_json",         # structured ATS JSON API — url_ingest handles it natively
    "json_endpoint",    # a JSON API the agent curls directly (not auto-handled), e.g. Workday CXS
    "dedicated_script", # a purpose-built fetcher exists; run `command`
    "curl_browser_ua",  # curl the HTML with a browser User-Agent, then extract
    "reader_proxy",     # render via a reader proxy (r.jina.ai) — the JS route
    "chrome_mcp",       # needs the browser MCP (login/bot wall); finish the stub
    "user_fill",        # no machine route — paste the JD body by hand
)

# What to do when no domain recipe is registered yet (encodes the proxy-first
# rule: cheap direct fetch, then a reader proxy — do not spelunk browser tools).
DEFAULT_RECIPE = {
    "domain": None,
    "method": "reader_proxy",
    "note": (
        "No recipe for this domain yet. Try the cheap direct fetch first; the "
        "moment it comes back bot-walled or JS-empty, go straight to the reader "
        "proxy (https://r.jina.ai/<url>) — do NOT cycle through Playwright / the "
        "Chrome extension / AppleScript. Once you find the route that works, run "
        "`fetch_recipes.py record` so the next listing from this domain skips the "
        "tests."
    ),
    "command": "curl -sL 'https://r.jina.ai/{url}'",
}


# -----------------------------------------------------------------------------
# load / save
# -----------------------------------------------------------------------------

def _load() -> dict:
    with REGISTRY.open() as fh:
        return json.load(fh)


def _save(data: dict) -> None:
    # ensure_ascii=False keeps the registry human-editable (em-dashes etc. stay
    # literal rather than \uXXXX); it's a hand-maintained data file.
    REGISTRY.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def hostname(url: str) -> str:
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


# -----------------------------------------------------------------------------
# lookup
# -----------------------------------------------------------------------------

def lookup(url: str) -> dict | None:
    """Return the recipe whose domain is the longest matching suffix of the
    URL's hostname, or None. Suffix match is label-aligned: 'amazon.jobs' matches
    'www.amazon.jobs' but not 'notamazon.jobs'.
    """
    host = hostname(url)
    if not host:
        return None
    best: dict | None = None
    for recipe in _load().get("recipes", []):
        dom = (recipe.get("domain") or "").lower()
        if host == dom or host.endswith("." + dom):
            if best is None or len(dom) > len(best["domain"]):
                best = recipe
    return best


def resolve(url: str) -> tuple[dict, bool]:
    """(recipe, is_known). Falls back to DEFAULT_RECIPE with is_known=False."""
    hit = lookup(url)
    if hit is not None:
        return hit, True
    return {**DEFAULT_RECIPE, "domain": hostname(url) or None}, False


# -----------------------------------------------------------------------------
# record (the "training" half)
# -----------------------------------------------------------------------------

def record(domain: str, method: str, note: str, *, command: str | None = None,
           extract: str | None = None, verified: str | None = None,
           source_memory: str | None = None) -> tuple[dict, bool]:
    """Add or update a recipe. Returns (recipe, replaced_existing)."""
    domain = domain.lower().lstrip(".")
    if domain.startswith("www."):
        domain = domain[4:]
    if method not in METHODS:
        raise ValueError(f"method must be one of {METHODS}, got {method!r}")
    verified = verified or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    recipe: dict[str, Any] = {"domain": domain, "method": method, "note": note}
    if command:
        recipe["command"] = command
    if extract:
        recipe["extract"] = extract
    recipe["verified_at"] = verified
    if source_memory:
        recipe["source_memory"] = source_memory

    data = _load()
    recipes = data.setdefault("recipes", [])
    replaced = False
    for i, existing in enumerate(recipes):
        if (existing.get("domain") or "").lower() == domain:
            recipes[i] = recipe
            replaced = True
            break
    if not replaced:
        recipes.append(recipe)
    _save(data)
    return recipe, replaced


# -----------------------------------------------------------------------------
# rendering
# -----------------------------------------------------------------------------

def render(recipe: dict, url: str | None = None, *, known: bool = True) -> str:
    lines = []
    dom = recipe.get("domain") or "(any)"
    tag = "recipe" if known else "no recipe — default"
    lines.append(f"[{tag}] {dom} → {recipe.get('method')}")
    if recipe.get("note"):
        lines.append(f"  note:    {recipe['note']}")
    cmd = recipe.get("command")
    if cmd:
        if url:
            cmd = cmd.replace("{url}", url)
        lines.append(f"  command: {cmd}")
    if recipe.get("extract"):
        lines.append(f"  extract: {recipe['extract']}")
    if recipe.get("verified_at"):
        lines.append(f"  verified: {recipe['verified_at']}")
    if recipe.get("source_memory"):
        lines.append(f"  memory:  {recipe['source_memory']}")
    return "\n".join(lines)


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------

def _main_record(argv: list[str]) -> int:
    rec = argparse.ArgumentParser(prog="fetch_recipes.py record",
                                  description="add or update a recipe for a domain")
    rec.add_argument("--domain", required=True, help="hostname suffix, e.g. amazon.jobs")
    rec.add_argument("--method", required=True, choices=METHODS)
    rec.add_argument("--note", required=True, help="why the obvious routes fail / what works")
    rec.add_argument("--command", default=None, help="exact shell command; use {url} placeholder")
    rec.add_argument("--extract", default=None, help="hints for pulling JD/quals/comp from the bytes")
    rec.add_argument("--verified", default=None, help="YYYY-MM-DD (default: today)")
    rec.add_argument("--source-memory", default=None, help="related memory slug")
    args = rec.parse_args(argv)
    recipe, replaced = record(
        args.domain, args.method, args.note, command=args.command,
        extract=args.extract, verified=args.verified,
        source_memory=args.source_memory)
    print(("Updated" if replaced else "Added") + f" recipe for {recipe['domain']}:")
    print(render(recipe))
    return 0


def main() -> int:
    # `record` is dispatched by hand so a bare URL can stay a plain positional
    # (an argparse subparser would claim the first positional as the subcommand).
    if len(sys.argv) > 1 and sys.argv[1] == "record":
        return _main_record(sys.argv[2:])

    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--list", action="store_true", help="dump the whole registry")
    parser.add_argument("url", nargs="?", default=None, help="listing URL to look up")
    args = parser.parse_args()

    if args.list:
        for recipe in _load().get("recipes", []):
            print(render(recipe))
            print()
        return 0

    if not args.url:
        parser.error("pass a URL to look up, --list, or the `record` subcommand")

    recipe, known = resolve(args.url)
    print(render(recipe, args.url, known=known))
    return 0 if known else 3  # exit 3 = no recipe (a new domain worth recording)


if __name__ == "__main__":
    sys.exit(main())
