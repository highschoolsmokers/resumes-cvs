#!/usr/bin/env python3
"""Top-of-funnel job search driver.

Reads config/sites.yaml + config/criteria.yaml, fetches listings from each
configured source, normalises them to the schema in job-search-agent-spec.md
§3.4, de-duplicates against search/seen.db, rule-scores per §3.5, and writes
listings.jsonl + scored.jsonl + summary.md under search/runs/<timestamp>/.

Usage:
    python search/run.py                # full run
    python search/run.py --dry-run      # fetch + normalise, skip seen.db write
    python search/run.py --only greenhouse lever   # subset of sources

Acceptance (CLAUDE.md §2 Phase 1):
    - From an empty seen.db, a single run produces >= 30 normalised listings.
    - Rerun within 24h adds zero new rows.
    - summary.md groups `recommend: yes` listings by company with source URLs.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import os
import re
import sqlite3
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Iterable

import yaml
import requests

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO = Path(__file__).resolve().parent.parent
CONFIG = REPO / "config"
SEARCH = REPO / "search"
RUNS = SEARCH / "runs"
SEEN_DB = SEARCH / "seen.db"

# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

TECH_VOCAB = [
    # Languages
    "Python", "TypeScript", "JavaScript", "Go", "Rust", "Ruby", "Java", "Kotlin",
    "Swift", "C++", "C#",
    # Frameworks / stacks
    "React", "Next.js", "Node.js", "Django", "Flask", "FastAPI", "Rails",
    "Tailwind", "Electron", "GraphQL", "REST",
    # AI / agents
    "MCP", "Model Context Protocol", "Claude", "Anthropic", "OpenAI", "LLM",
    "agent", "RAG", "embedding", "prompt", "fine-tuning",
    # Cloud / infra
    "AWS", "GCP", "Azure", "Kubernetes", "Docker", "Terraform", "Vercel",
    "Cloudflare", "PostgreSQL", "Redis", "Kafka",
    # Docs / DX
    "docs-as-code", "documentation", "OpenAPI", "Swagger", "developer experience",
    "Markdown", "MDX", "Sphinx", "MkDocs",
    # Testing
    "Playwright", "Cypress", "Jest", "pytest", "Lighthouse",
    # CMS / content
    "Sanity", "Contentful", "WordPress", "Notion",
]
# Case-insensitive regex, preserving the display form from TECH_VOCAB.
TECH_RE = re.compile(
    r"\b(" + "|".join(re.escape(t) for t in TECH_VOCAB) + r")\b",
    re.IGNORECASE,
)

TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"[ \t]+")
NL_RE = re.compile(r"\n{3,}")


def html_to_text(s: str | None) -> str:
    """Light HTML → plain text. Not a real converter; good enough for scoring."""
    if not s:
        return ""
    s = html.unescape(s)
    # Turn <br>, </p>, </div>, </li> into newlines before stripping tags.
    s = re.sub(r"</(p|div|li|h[1-6])>", "\n", s, flags=re.IGNORECASE)
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.IGNORECASE)
    s = re.sub(r"<li[^>]*>", "- ", s, flags=re.IGNORECASE)
    s = TAG_RE.sub("", s)
    s = WS_RE.sub(" ", s)
    s = NL_RE.sub("\n\n", s)
    return s.strip()


def tech_mentions(text: str) -> list[str]:
    """Unique, preserved-case tech terms found in text."""
    found: dict[str, None] = {}  # dict preserves insertion order and uniqueness
    for match in TECH_RE.finditer(text or ""):
        term = match.group(1)
        # Normalise to the canonical display form from TECH_VOCAB.
        canon = next((t for t in TECH_VOCAB if t.lower() == term.lower()), term)
        found[canon] = None
    return list(found.keys())


def infer_seniority(title: str) -> str:
    t = title.lower()
    if re.search(r"\bprincipal\b", t): return "principal"
    if re.search(r"\bstaff\b", t): return "staff"
    if re.search(r"\bsenior\b|\bsr\.?\b|\blead\b", t): return "senior"
    if re.search(r"\bjunior\b|\bjr\.?\b|\bassociate\b", t): return "junior"
    if re.search(r"\bintern\b", t): return "intern"
    return "mid"


def infer_remote(location: str, description: str) -> str:
    loc = (location or "").lower()
    desc = (description or "").lower()[:2000]  # first 2k chars
    if "remote" in loc or re.search(r"\bfully remote\b|\b100% remote\b", desc):
        return "remote"
    if "hybrid" in loc or re.search(r"\bhybrid\b", desc):
        return "hybrid"
    if loc and not any(k in loc for k in ["remote", "hybrid"]):
        return "onsite"
    return "unknown"


def listing_hash(source: str, source_url: str) -> str:
    return hashlib.sha256(f"{source}|{source_url}".encode("utf-8")).hexdigest()


def now_iso() -> str:
    return dt.datetime.now().astimezone().replace(microsecond=0).isoformat()


# ---------------------------------------------------------------------------
# Adapters
# ---------------------------------------------------------------------------

UA = {"User-Agent": "wsgong-job-search/0.1 (+https://ws-gong.com)"}
TIMEOUT = 30


def fetch_json(url: str, retries: int = 1) -> Any:
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, headers=UA, timeout=TIMEOUT)
            if r.status_code == 200:
                return r.json()
            if r.status_code in (429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(2 * (attempt + 1))
                continue
            raise RuntimeError(f"HTTP {r.status_code} fetching {url}")
        except Exception as e:
            last_exc = e
            if attempt >= retries:
                raise
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"exhausted retries fetching {url}: {last_exc}")


def parse_greenhouse(token: str, payload: dict) -> list[dict]:
    out = []
    for j in (payload or {}).get("jobs", []):
        loc = (j.get("location") or {}).get("name") or ""
        content_html = j.get("content") or ""
        desc = html_to_text(content_html)
        pay = _extract_pay_greenhouse(j)
        out.append({
            "id": f"greenhouse:{token}:{j.get('id')}",
            "source": "greenhouse",
            "source_token": token,
            "source_url": j.get("absolute_url"),
            "company": _company_from_token(token),
            "title": j.get("title") or "",
            "location": loc,
            "remote": infer_remote(loc, desc),
            "seniority": infer_seniority(j.get("title") or ""),
            "posted_at": (j.get("updated_at") or "")[:10] or None,
            "comp": pay,
            "description_md": desc,
            "requirements": [],
            "tech_mentions": tech_mentions(f"{j.get('title','')} {desc}"),
            "fetched_at": now_iso(),
        })
    return out


def _extract_pay_greenhouse(j: dict) -> dict | None:
    ranges = j.get("pay_input_ranges") or j.get("pay_ranges") or []
    if ranges:
        r = ranges[0]
        return {
            "min": _to_int(r.get("min_cents", r.get("min")) and (r.get("min_cents", 0) // 100 if r.get("min_cents") else r.get("min"))),
            "max": _to_int(r.get("max_cents", r.get("max")) and (r.get("max_cents", 0) // 100 if r.get("max_cents") else r.get("max"))),
            "currency": r.get("currency", "USD"),
            "equity": None,
        }
    # Fallback: look in metadata[] for a "Pay range" field (some Greenhouse boards).
    for m in j.get("metadata") or []:
        name = (m.get("name") or "").lower()
        if "pay" in name or "salary" in name or "compensation" in name:
            val = m.get("value")
            if isinstance(val, str):
                nums = re.findall(r"\$?([\d,]{3,})", val)
                if len(nums) >= 2:
                    return {
                        "min": _to_int(nums[0]),
                        "max": _to_int(nums[1]),
                        "currency": "USD",
                        "equity": None,
                    }
    return None


def parse_lever(token: str, payload: list) -> list[dict]:
    out = []
    for j in payload or []:
        cats = j.get("categories") or {}
        loc = cats.get("location") or ""
        desc_html = (j.get("description") or "") + "\n".join(
            li.get("content", "") for li in j.get("lists", [])
        )
        desc = html_to_text(desc_html)
        posted_ms = j.get("createdAt")
        posted = dt.datetime.fromtimestamp(posted_ms / 1000).date().isoformat() if posted_ms else None
        out.append({
            "id": f"lever:{token}:{j.get('id')}",
            "source": "lever",
            "source_token": token,
            "source_url": j.get("hostedUrl"),
            "company": _company_from_token(token),
            "title": j.get("text") or "",
            "location": loc,
            "remote": infer_remote(loc, desc),
            "seniority": infer_seniority(j.get("text") or ""),
            "posted_at": posted,
            "comp": None,   # Lever rarely exposes comp
            "description_md": desc,
            "requirements": [],
            "tech_mentions": tech_mentions(f"{j.get('text','')} {desc}"),
            "fetched_at": now_iso(),
        })
    return out


def parse_ashby(token: str, payload: dict) -> list[dict]:
    out = []
    for j in (payload or {}).get("jobs", []):
        loc = j.get("location") or ""
        desc = html_to_text(j.get("descriptionHtml") or j.get("descriptionPlain") or "")
        pay = _extract_pay_ashby(j)
        is_remote = j.get("isRemote")
        remote = "remote" if is_remote else infer_remote(loc, desc)
        out.append({
            "id": f"ashby:{token}:{j.get('id')}",
            "source": "ashby",
            "source_token": token,
            "source_url": j.get("jobUrl"),
            "company": _company_from_token(token),
            "title": j.get("title") or "",
            "location": loc,
            "remote": remote,
            "seniority": infer_seniority(j.get("title") or ""),
            "posted_at": (j.get("publishedDate") or "")[:10] or None,
            "comp": pay,
            "description_md": desc,
            "requirements": [],
            "tech_mentions": tech_mentions(f"{j.get('title','')} {desc}"),
            "fetched_at": now_iso(),
        })
    return out


def _extract_pay_ashby(j: dict) -> dict | None:
    comp = j.get("compensation") or {}
    comps = comp.get("summaryComponents") or []
    for c in comps:
        if c.get("compensationType") == "Salary":
            cur = c.get("currencyCode", "USD")
            mn, mx = c.get("minValue"), c.get("maxValue")
            if mn or mx:
                return {"min": _to_int(mn), "max": _to_int(mx), "currency": cur, "equity": None}
    return None


def _to_int(x) -> int | None:
    if x is None: return None
    if isinstance(x, int): return x
    if isinstance(x, float): return int(x)
    s = str(x).replace(",", "").replace("$", "").strip()
    try:
        return int(float(s))
    except ValueError:
        return None


def _company_from_token(token: str) -> str:
    """Pretty-print a board token. Overrides handle known special cases."""
    overrides = {
        "openai": "OpenAI",
        "nvidia": "NVIDIA",
        "ibm": "IBM",
        "hashicorp": "HashiCorp",
        "langchain": "LangChain",
        "braintrust": "Braintrust",
    }
    if token.lower() in overrides:
        return overrides[token.lower()]
    return token.replace("-", " ").replace("_", " ").title()


PARSERS = {
    "greenhouse": parse_greenhouse,
    "lever": parse_lever,
    "ashby": parse_ashby,
}


# ---------------------------------------------------------------------------
# De-dupe cache
# ---------------------------------------------------------------------------

def init_seen_db() -> sqlite3.Connection:
    conn = sqlite3.connect(SEEN_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS seen (
            hash TEXT PRIMARY KEY,
            seen_at TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def dedupe(conn: sqlite3.Connection, listings: Iterable[dict], dry_run: bool = False) -> list[dict]:
    fresh: list[dict] = []
    cur = conn.cursor()
    for l in listings:
        if not l.get("source_url"):
            continue  # can't hash, can't track
        h = listing_hash(l["source"], l["source_url"])
        row = cur.execute("SELECT 1 FROM seen WHERE hash = ?", (h,)).fetchone()
        if row:
            continue
        if not dry_run:
            cur.execute("INSERT INTO seen(hash, seen_at) VALUES (?, ?)", (h, now_iso()))
        fresh.append(l)
    if not dry_run:
        conn.commit()
    return fresh


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def score_listing(listing: dict, criteria: dict) -> dict:
    title = (listing.get("title") or "").lower()
    desc = (listing.get("description_md") or "").lower()
    company = (listing.get("company") or "")
    reasons: list[str] = []

    # Hard reject: excluded title keyword or company.
    for ex in criteria.get("title_keywords_exclude", []) or []:
        if ex.lower() in title:
            return {"score": 0, "recommend": "no", "rationale": f"excluded title keyword: '{ex}'"}
    for ex in criteria.get("company_exclude", []) or []:
        if ex.lower() == company.lower():
            return {"score": 0, "recommend": "no", "rationale": f"excluded company: '{ex}'"}

    score = 0

    # +40 title include
    include_hits = [kw for kw in (criteria.get("title_keywords_include") or []) if kw.lower() in title]
    if include_hits:
        score += 40
        reasons.append(f"title matches {include_hits[0]!r}")

    # +10 per tech affinity, cap +30
    affinity_hits = []
    for term in (criteria.get("tech_affinity_boost") or []):
        if term.lower() in desc or term in (listing.get("tech_mentions") or []):
            affinity_hits.append(term)
    bonus = min(30, 10 * len(affinity_hits))
    if bonus:
        score += bonus
        reasons.append(f"affinity +{bonus} ({', '.join(affinity_hits[:4])}{'…' if len(affinity_hits) > 4 else ''})")

    # +10 seniority match
    if listing.get("seniority") in (criteria.get("seniority") or []):
        score += 10
        reasons.append(f"seniority={listing['seniority']}")

    # +10 location / remote match
    loc = (listing.get("location") or "").lower()
    loc_cfg = criteria.get("location") or {}
    base = (loc_cfg.get("base") or "").lower()
    remote_ok = bool(loc_cfg.get("remote_ok"))
    relocate_for = [r.lower() for r in (loc_cfg.get("relocate_for") or [])]
    loc_hit = False
    if remote_ok and listing.get("remote") == "remote":
        loc_hit = True; reasons.append("remote-ok")
    elif base and (base in loc or any(p in loc for p in base.split() if len(p) > 3)):
        loc_hit = True; reasons.append(f"location matches base ({listing.get('location')})")
    elif any(r in loc for r in relocate_for):
        loc_hit = True; reasons.append(f"relocate-ok ({listing.get('location')})")
    if loc_hit:
        score += 10

    # ±comp
    floor = criteria.get("comp_floor_usd")
    comp = listing.get("comp") or {}
    mn = comp.get("min") if comp else None
    if floor is not None and mn is not None:
        if mn >= floor:
            score += 5
            reasons.append(f"comp ≥ floor (${mn:,})")
        else:
            score -= 10
            reasons.append(f"comp below floor (${mn:,} < ${floor:,})")

    score = max(0, min(100, score))

    thr = (criteria.get("score_thresholds") or {})
    yes_t, maybe_t = thr.get("yes", 70), thr.get("maybe", 40)
    if score >= yes_t: rec = "yes"
    elif score >= maybe_t: rec = "maybe"
    else: rec = "no"

    return {"score": score, "recommend": rec, "rationale": "; ".join(reasons) or "no positive signals"}


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def write_summary(run_dir: Path, scored: list[dict]) -> None:
    ts = run_dir.name
    total = len(scored)
    hard_rejects = sum(1 for l in scored if l["recommend"] == "no" and l["score"] == 0)
    buckets = {"yes": [], "maybe": [], "no": []}
    for l in scored:
        buckets[l["recommend"]].append(l)

    out: list[str] = []
    out.append(f"# Search run {ts}\n")
    out.append(f"- Listings fetched: **{total}**")
    out.append(f"- Hard rejects: **{hard_rejects}**")
    out.append(f"- Yes: **{len(buckets['yes'])}**    Maybe: **{len(buckets['maybe'])}**    No: **{len(buckets['no']) - hard_rejects}**\n")

    def render_bucket(name: str, label: str) -> None:
        rows = buckets[name]
        if not rows:
            return
        out.append(f"\n## {label}\n")
        # Group by company, companies ordered by their top-scoring row.
        by_company: dict[str, list[dict]] = {}
        for l in rows:
            by_company.setdefault(l["company"], []).append(l)
        companies = sorted(by_company.items(), key=lambda kv: -max(x["score"] for x in kv[1]))
        for company, rows in companies:
            rows.sort(key=lambda l: -l["score"])
            out.append(f"### {company}\n")
            for l in rows:
                out.append(
                    f"- **{l['title']}** — {l['location'] or '—'}, "
                    f"{l['seniority']} · score {l['score']}  \n"
                    f"  <{l['source_url']}>  \n"
                    f"  *{l['rationale']}*\n"
                )

    render_bucket("yes", "Yes")
    render_bucket("maybe", "Maybe")

    (run_dir / "summary.md").write_text("\n".join(out), encoding="utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def load_yaml(path: Path) -> Any:
    with path.open() as f:
        return yaml.safe_load(f)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="do not update seen.db")
    ap.add_argument("--only", nargs="*", help="only run these source names")
    args = ap.parse_args()

    criteria = load_yaml(CONFIG / "criteria.yaml") or {}
    sites = load_yaml(CONFIG / "sites.yaml") or []
    if args.only:
        sites = [s for s in sites if s.get("name") in set(args.only)]

    ts = dt.datetime.now().strftime("%Y-%m-%d-%H%M")
    run_dir = RUNS / ts
    (run_dir / "raw").mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    all_listings: list[dict] = []

    for site in sites:
        name = site.get("name")
        parser = PARSERS.get(name)
        if parser is None:
            errors.append(f"[{name}] no parser registered; skipped")
            continue
        endpoint = site.get("endpoint_template") or ""
        rate = float(site.get("rate_limit_sec", 1))
        for token in site.get("tokens", []):
            url = endpoint.format(token=token)
            try:
                payload = fetch_json(url, retries=1)
                (run_dir / "raw" / f"{name}-{token}.json").write_text(
                    json.dumps(payload, indent=2), encoding="utf-8"
                )
                rows = parser(token, payload)
                all_listings.extend(rows)
                print(f"[{name}:{token}] {len(rows)} listings")
            except Exception as e:
                msg = f"[{name}:{token}] {type(e).__name__}: {e}"
                print(msg, file=sys.stderr)
                errors.append(msg + "\n" + traceback.format_exc())
            time.sleep(rate)

    # De-dupe.
    conn = init_seen_db()
    fresh = dedupe(conn, all_listings, dry_run=args.dry_run)
    conn.close()

    # Write listings.jsonl.
    with (run_dir / "listings.jsonl").open("w", encoding="utf-8") as f:
        for l in fresh:
            f.write(json.dumps(l, ensure_ascii=False) + "\n")

    # Score.
    scored: list[dict] = []
    for l in fresh:
        s = score_listing(l, criteria)
        scored.append({**l, **s})

    with (run_dir / "scored.jsonl").open("w", encoding="utf-8") as f:
        for l in scored:
            f.write(json.dumps(l, ensure_ascii=False) + "\n")

    write_summary(run_dir, scored)

    if errors:
        (run_dir / "errors.log").write_text("\n\n---\n\n".join(errors), encoding="utf-8")

    print(f"\nRun complete: {run_dir}")
    print(f"  fetched total : {len(all_listings)}")
    print(f"  fresh (new)   : {len(fresh)}")
    print(f"  yes recs      : {sum(1 for l in scored if l['recommend']=='yes')}")
    print(f"  maybe recs    : {sum(1 for l in scored if l['recommend']=='maybe')}")
    if errors:
        print(f"  errors        : {len(errors)}  (see errors.log)")
    print(f"\n→ open {run_dir/'summary.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
