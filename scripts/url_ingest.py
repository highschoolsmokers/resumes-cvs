#!/usr/bin/env python3
"""Single-listing entry point — skip the bulk search, drop straight into tailoring.

Spec §3.8 / CLAUDE.md §2 Phase 2.

Usage:
    python scripts/url_ingest.py <URL>
    python scripts/url_ingest.py <URL> --company "Anthropic" --title "Forward Deployed Engineer"
    python scripts/url_ingest.py --from-stdin     # paste JD text manually

What this script does:
    1. Detect the source ATS from the URL.
    2. For Greenhouse / Lever / Ashby — hit the public JSON API and normalise
       to the §3.4 schema.
    3. For LinkedIn and generic URLs — emit a stub listing and print a
       follow-up message explaining the Chrome-MCP / paste-in step the agent
       (or user) has to finish. We never silently accept a half-listing; the
       stub carries `requires_chrome_mcp: true` or `requires_user_fill: true`
       and downstream tailoring will refuse to run until those flags clear.
    4. Write:
           applications/<Company>/<role-slug>-<YYYY-MM-DD>/
               listing.json
               listing.md
    5. Create branch `app/<Company>-<role-slug>-<YYYY-MM-DD>` and emit the
       git commands for the user to run (we don't touch `.git/` from here —
       the Cowork sandbox cannot modify it).
    6. Bypass `search/seen.db` entirely — this is a deliberate, user-initiated
       action. The listing record carries `"ingest": "manual"` so the audit
       trail shows how it entered.

Design choice — no network fallbacks masquerading as success:
    If Greenhouse/Lever/Ashby returns something we can't parse, we dump what
    we got into the listing folder and exit non-zero. The user sees exactly
    what broke. Same for LinkedIn — we do NOT follow up with an HTTP GET
    that will hit a login wall; that's what the Chrome MCP is for.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parent.parent
APPLICATIONS = REPO / "applications"
USER_AGENT = "ws-gong-job-search/0.1 (url_ingest.py)"


# -----------------------------------------------------------------------------
# URL parsing
# -----------------------------------------------------------------------------

def detect_source(url: str) -> tuple[str, dict]:
    """Return (source_key, extracted_ids). Raises on unparseable URLs.

    source_key is one of: 'greenhouse', 'lever', 'ashby', 'linkedin', 'generic'.
    """
    u = urllib.parse.urlparse(url)
    host = (u.hostname or "").lower()
    path = u.path or ""

    # Greenhouse — two host forms
    m = re.match(r"/(?P<token>[^/]+)/jobs/(?P<id>\d+)", path)
    if host in ("boards.greenhouse.io", "job-boards.greenhouse.io") and m:
        return "greenhouse", {"token": m["token"], "id": m["id"]}

    if host == "jobs.lever.co":
        m = re.match(r"/(?P<token>[^/]+)/(?P<id>[0-9a-f-]+)", path)
        if m:
            return "lever", {"token": m["token"], "id": m["id"]}

    if host == "jobs.ashbyhq.com":
        m = re.match(r"/(?P<token>[^/]+)/(?P<id>[0-9a-f-]+)", path)
        if m:
            return "ashby", {"token": m["token"], "id": m["id"]}

    if "linkedin.com" in host and "/jobs/view/" in path:
        m = re.search(r"/jobs/view/(?P<id>\d+)", path)
        if m:
            return "linkedin", {"id": m["id"]}

    return "generic", {}


# -----------------------------------------------------------------------------
# ATS fetchers (structured JSON APIs — no browser needed)
# -----------------------------------------------------------------------------

def _http_json(url: str, timeout: float = 20.0) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT,
                                               "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        body = resp.read().decode("utf-8")
    return json.loads(body)


def fetch_greenhouse(token: str, job_id: str) -> dict:
    api = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs/{job_id}?content=true"
    data = _http_json(api)
    return {
        "source": "greenhouse",
        "source_url": data.get("absolute_url"),
        "company": data.get("company", {}).get("name") or token,
        "title": data.get("title"),
        "location": (data.get("location") or {}).get("name"),
        "remote": None,
        "seniority": None,
        "posted_at": (data.get("updated_at") or "")[:10] or None,
        "comp": None,
        "description_md": _html_to_md(data.get("content") or ""),
        "requirements": [],
        "tech_mentions": [],
    }


def fetch_lever(token: str, job_id: str) -> dict:
    api = f"https://api.lever.co/v0/postings/{token}/{job_id}"
    data = _http_json(api)
    cats = data.get("categories") or {}
    return {
        "source": "lever",
        "source_url": data.get("hostedUrl"),
        "company": token,
        "title": data.get("text"),
        "location": cats.get("location"),
        "remote": cats.get("commitment"),
        "seniority": None,
        "posted_at": _epoch_to_date(data.get("createdAt")),
        "comp": None,
        "description_md": _html_to_md(data.get("descriptionPlain")
                                      or data.get("description") or ""),
        "requirements": [],
        "tech_mentions": [],
    }


def fetch_ashby(token: str, job_id: str) -> dict:
    api = f"https://api.ashbyhq.com/posting-api/job-board/{token}?includeCompensation=true"
    data = _http_json(api)
    jobs = data.get("jobs") or []
    match = next((j for j in jobs if j.get("id") == job_id), None)
    if not match:
        raise RuntimeError(
            f"ashby: job {job_id!r} not found in {token!r} board "
            f"({len(jobs)} postings fetched)"
        )
    return {
        "source": "ashby",
        "source_url": match.get("jobUrl"),
        "company": token,
        "title": match.get("title"),
        "location": match.get("locationName"),
        "remote": match.get("employmentType"),
        "seniority": None,
        "posted_at": (match.get("publishedAt") or "")[:10] or None,
        "comp": None,
        "description_md": _html_to_md(match.get("descriptionHtml")
                                      or match.get("descriptionPlain") or ""),
        "requirements": [],
        "tech_mentions": [],
    }


# -----------------------------------------------------------------------------
# stubbed sources — emit a placeholder, flag for completion
# -----------------------------------------------------------------------------

def stub_linkedin(job_id: str, url: str) -> dict:
    return {
        "source": "linkedin",
        "source_url": url,
        "company": None,            # user or Chrome MCP must fill
        "title": None,
        "location": None,
        "remote": None,
        "seniority": None,
        "posted_at": None,
        "comp": None,
        "description_md": "",
        "requirements": [],
        "tech_mentions": [],
        "requires_chrome_mcp": True,
        "requires_user_fill": True,
        "linkedin_job_id": job_id,
    }


def stub_generic(url: str) -> dict:
    return {
        "source": "generic",
        "source_url": url,
        "company": None,
        "title": None,
        "location": None,
        "remote": None,
        "seniority": None,
        "posted_at": None,
        "comp": None,
        "description_md": "",
        "requirements": [],
        "tech_mentions": [],
        "requires_user_fill": True,
    }


# -----------------------------------------------------------------------------
# helpers
# -----------------------------------------------------------------------------

def _html_to_md(html: str) -> str:
    """Crude HTML → text. Good enough for JDs that tailoring will re-parse anyway.

    We don't pull in html2text here because the dependency wouldn't be worth it
    for a lightly-formatted JD. The tailor reads `description_md` verbatim.
    """
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.I)
    text = re.sub(r"</p>", "\n\n", text, flags=re.I)
    text = re.sub(r"<li[^>]*>", "- ", text, flags=re.I)
    text = re.sub(r"</li>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _epoch_to_date(ms: Any) -> str | None:
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return None


def slugify(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s.lower()).strip("-")
    return s or "role"


def company_dir_name(company: str) -> str:
    """Preserve capitalisation in the company folder for continuity with
    NVIDIA/Vercel/etc., but strip filesystem-hostile characters.
    """
    return re.sub(r"[^A-Za-z0-9&._-]+", "", company) or "Unknown"


def listing_id(source: str, url: str) -> str:
    digest = hashlib.sha256(f"{source}:{url}".encode("utf-8")).hexdigest()[:12]
    return f"{source}:{digest}"


def render_listing_md(listing: dict) -> str:
    lines: list[str] = []
    lines.append(f"# {listing.get('title') or '(title unknown)'}")
    lines.append("")
    lines.append(f"**Company:** {listing.get('company') or '(unknown)'}")
    lines.append(f"**Source:** {listing.get('source')}")
    lines.append(f"**URL:** {listing.get('source_url')}")
    if listing.get("location"):
        lines.append(f"**Location:** {listing['location']}")
    if listing.get("remote"):
        lines.append(f"**Remote / commitment:** {listing['remote']}")
    if listing.get("posted_at"):
        lines.append(f"**Posted:** {listing['posted_at']}")
    if listing.get("comp"):
        lines.append(f"**Comp:** {json.dumps(listing['comp'])}")
    lines.append("")
    if listing.get("requires_chrome_mcp") or listing.get("requires_user_fill"):
        lines.append("> ⚠️  This listing is a stub. "
                     "Completion is required before tailoring — see `listing.json` "
                     "`requires_*` flags.")
        lines.append("")
    lines.append("## Description")
    lines.append("")
    lines.append(listing.get("description_md") or "_(empty — paste JD here)_")
    lines.append("")
    return "\n".join(lines)


# -----------------------------------------------------------------------------
# writing out
# -----------------------------------------------------------------------------

def write_application(listing: dict, *, today: str | None = None) -> Path:
    today = today or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    company = company_dir_name(listing.get("company") or "Unknown")
    role_slug = slugify(listing.get("title") or "role")
    folder = APPLICATIONS / company / f"{role_slug}-{today}"
    folder.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc).isoformat()
    listing = {
        **listing,
        "id": listing_id(listing.get("source") or "generic",
                         listing.get("source_url") or ""),
        "ingest": "manual",
        "fetched_at": now,
    }

    (folder / "listing.json").write_text(json.dumps(listing, indent=2) + "\n")
    (folder / "listing.md").write_text(render_listing_md(listing))
    return folder


def branch_name(folder: Path) -> str:
    # applications/<Company>/<slug-date>
    try:
        company = folder.parent.name
        tail = folder.name
    except Exception:  # pragma: no cover
        return "app/unknown"
    return f"app/{company}-{tail}"


# -----------------------------------------------------------------------------
# main
# -----------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("url", nargs="?", default=None,
                        help="listing URL (LinkedIn / Greenhouse / Lever / Ashby / generic)")
    parser.add_argument("--company", default=None,
                        help="override company name (useful for generic / LinkedIn stubs)")
    parser.add_argument("--title", default=None,
                        help="override role title")
    parser.add_argument("--from-stdin", action="store_true",
                        help="read JD text from stdin (pairs with --company/--title)")
    args = parser.parse_args()

    if args.from_stdin:
        listing = stub_generic(args.url or "stdin://")
        listing["description_md"] = sys.stdin.read().strip()
        listing["requires_user_fill"] = False
    else:
        if not args.url:
            parser.error("URL is required (or use --from-stdin with --company/--title)")
        source, ids = detect_source(args.url)
        try:
            if source == "greenhouse":
                listing = fetch_greenhouse(ids["token"], ids["id"])
            elif source == "lever":
                listing = fetch_lever(ids["token"], ids["id"])
            elif source == "ashby":
                listing = fetch_ashby(ids["token"], ids["id"])
            elif source == "linkedin":
                listing = stub_linkedin(ids["id"], args.url)
            else:
                listing = stub_generic(args.url)
        except (urllib.error.URLError, json.JSONDecodeError,
                RuntimeError, KeyError) as e:
            sys.stderr.write(
                f"url_ingest.py: {source} fetch failed: {e}\n"
                "  Writing a stub listing so you can fill in the JD by hand.\n"
            )
            listing = stub_generic(args.url)

    # CLI overrides (useful for stubs)
    if args.company:
        listing["company"] = args.company
    if args.title:
        listing["title"] = args.title

    if not listing.get("company"):
        sys.stderr.write("url_ingest.py: company unknown — rerun with "
                         "--company <Name> (stub will still be written)\n")
    if not listing.get("title"):
        sys.stderr.write("url_ingest.py: title unknown — rerun with "
                         "--title <Role>\n")

    folder = write_application(listing)
    branch = branch_name(folder)

    print(f"Application folder: {folder.relative_to(REPO)}")
    print(f"Proposed branch:    {branch}")
    print()
    print("Next steps (run locally — the sandbox cannot touch .git):")
    print(f"  git checkout -b {branch}")
    print(f"  git add {folder.relative_to(REPO)}")
    print(f'  git commit -m "url-ingest: add listing for {listing.get("company")} — {listing.get("title")}"')
    if listing.get("requires_chrome_mcp"):
        print()
        print("  NOTE: this LinkedIn listing is a stub. "
              "The agent must finish it via the Chrome MCP before tailoring.")
    elif listing.get("requires_user_fill"):
        print()
        print("  NOTE: this generic listing is a stub. Open listing.md and "
              "paste the JD body, then clear `requires_user_fill` in listing.json.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
