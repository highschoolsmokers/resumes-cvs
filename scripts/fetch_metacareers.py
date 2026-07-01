#!/usr/bin/env python3
"""Fetch a Meta careers JD in one command — no browser, no manual paste.

metacareers.com renders the JD client-side and hard-blocks non-browser HTTP
clients (any plain GET gets an "Error" page with no cookies). So we render it
through the public Jina reader proxy (https://r.jina.ai/<url>), which executes
the page's JS and returns clean markdown, then parse that markdown into the
listing.json / listing.md schema url_ingest.py produces (plus a few extra
Meta-specific keys). Downstream tailoring runs against it with
`requires_user_fill: false`.

Usage:
    python scripts/fetch_metacareers.py <metacareers-url>
    python scripts/fetch_metacareers.py <url> --company Meta        # default
    python scripts/fetch_metacareers.py <url> --commit              # branch+commit
    python scripts/fetch_metacareers.py <url> --print-md            # debug: dump proxy markdown

Why a proxy and not curl: direct requests to metacareers return a 1.5 KB Error
page regardless of headers or cookie warm-up (verified 2026-06-30). The reader
proxy is the only no-browser path that works. If the proxy is ever down, the
script exits non-zero and tells you to paste the JD via
`url_ingest.py --from-stdin`.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import url_ingest as ui  # noqa: E402  — reuse write_application / branch / helpers

READER = "https://r.jina.ai/"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36")

# Sections we lift out of the JD markdown, keyed by a substring of the heading.
_RESP = "responsibilities"
_MIN = "minimum qualifications"
_PREF = "preferred qualifications"

# Light tech-keyword scan for `tech_mentions` (same spirit as url_ingest: a hint,
# not a parse). Extend freely.
TECH_KEYWORDS = [
    "Python", "SQL", "TypeScript", "JavaScript", "React", "Node", "Java", "C++",
    "generative AI", "LLM", "prompt engineering", "annotation", "red-teaming",
    "A/B testing", "model-as-judge", "human eval", "RAG", "agent", "taxonomy",
    "rubric", "golden set", "evaluation", "dashboards",
]


def is_metacareers(url: str) -> bool:
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    return host.endswith("metacareers.com")


def job_id_from_url(url: str) -> str | None:
    m = re.search(r"/job_details/(\d+)", urllib.parse.urlparse(url).path)
    return m.group(1) if m else None


def fetch_markdown(url: str, timeout: float = 45.0) -> str:
    """Render the page through the reader proxy and return its markdown body."""
    req = urllib.request.Request(
        READER + url,
        headers={"User-Agent": UA, "Accept": "text/plain",
                 "X-Return-Format": "markdown"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        body = resp.read().decode("utf-8", errors="replace")
    # Strip the reader's "Title: / URL Source: / Markdown Content:" preamble.
    marker = "Markdown Content:"
    if marker in body:
        body = body.split(marker, 1)[1]
    return body.strip()


# -----------------------------------------------------------------------------
# markdown → structured listing
# -----------------------------------------------------------------------------

def _split_sections(md: str) -> tuple[list[str], dict[str, list[str]]]:
    """Return (preamble_lines, {lowercased_heading: body_lines}) splitting on `## `."""
    preamble: list[str] = []
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in md.splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m and not line.startswith("###"):
            current = m.group(1).strip().lower()
            sections[current] = []
        elif current is None:
            preamble.append(line)
        else:
            sections[current].append(line)
    return preamble, sections


def _bullets(lines: list[str]) -> list[str]:
    out: list[str] = []
    for l in lines:
        s = l.strip()
        # Skip thematic breaks (`* * *`, `---`, `***`) — they can masquerade as
        # a bullet under the `^[-*]\s+` pattern.
        if re.fullmatch(r"(?:[-*]\s*){3,}", s):
            continue
        m = re.match(r"^[-*]\s+(.+)$", s)
        if m:
            text = re.sub(r"\s+", " ", m.group(1)).strip()
            # Guard against a rule whose remainder is only punctuation/asterisks.
            if re.search(r"[A-Za-z0-9]", text):
                out.append(text)
    return out


def _find_section(sections: dict[str, list[str]], needle: str) -> list[str]:
    for heading, body in sections.items():
        if needle in heading:
            return body
    return []


def parse_metacareers_md(md: str, url: str) -> dict:
    preamble, sections = _split_sections(md)

    # Title: the first `# ` H1 in the preamble (not `##`).
    title = None
    h1_idx = None
    for i, line in enumerate(preamble):
        m = re.match(r"^#\s+(.+?)\s*$", line)
        if m and not line.startswith("##"):
            title = m.group(1).strip()
            h1_idx = i
            break

    # Location + intro live between the H1 and the "Apply now" button / first rule.
    location = None
    loc_extra = None
    intro_lines: list[str] = []
    if h1_idx is not None:
        seen_apply = False
        for line in preamble[h1_idx + 1:]:
            s = line.strip()
            if not s or s in {"* * *", "---"}:
                continue
            if re.fullmatch(r"(?i)apply now", s):
                seen_apply = True
                continue
            if not seen_apply:
                # Pre-"Apply now": location line, then tag chips we ignore.
                if location is None and ("," in s or re.search(r"(?i)remote", s)):
                    location = s
                elif re.match(r"^\+\s*\d+\s+locations", s, re.I):
                    loc_extra = s.lstrip("+ ").strip()
            else:
                # Post-"Apply now": the intro paragraph(s), until the first rule.
                intro_lines.append(s)
    if location and loc_extra:
        location = f"{location} (+{loc_extra})"

    intro = " ".join(intro_lines).strip()

    responsibilities = _bullets(_find_section(sections, _RESP))
    min_quals = _bullets(_find_section(sections, _MIN))
    pref_quals = _bullets(_find_section(sections, _PREF))

    # Compensation: a line like "United States of America: $162,000/year to
    # $227,000/year + bonus + equity + benefits" (lives in the About section).
    comp = None
    comp_line = None
    cm = re.search(r"\$[\d,]+/year\s+to\s+\$[\d,]+/year[^\n]*", md)
    if cm:
        comp_line = cm.group(0).strip()
        nums = re.findall(r"\$([\d,]+)/year", comp_line)
        if len(nums) >= 2:
            comp = {
                "currency": "USD",
                "min": int(nums[0].replace(",", "")),
                "max": int(nums[1].replace(",", "")),
                "period": "year",
                "notes": comp_line.split("year", 2)[-1].strip(" +") or None,
            }

    # Assemble a clean, complete description_md for listing.md.
    parts: list[str] = []
    if intro:
        parts.append(intro)
    if responsibilities:
        parts.append("### Responsibilities\n" + "\n".join(f"- {b}" for b in responsibilities))
    if min_quals:
        parts.append("### Minimum Qualifications\n" + "\n".join(f"- {b}" for b in min_quals))
    if pref_quals:
        parts.append("### Preferred Qualifications\n" + "\n".join(f"- {b}" for b in pref_quals))
    if comp_line:
        parts.append(f"**Compensation:** {comp_line}")
    description_md = "\n\n".join(parts).strip()

    blob = md.lower()
    tech = sorted({k for k in TECH_KEYWORDS if k.lower() in blob}, key=str.lower)

    return {
        "source": "metacareers",
        "source_url": url,
        "company": "Meta",
        "title": title,
        "location": location,
        "remote": False,
        "seniority": None,
        "posted_at": None,
        "comp": comp,
        "description_md": description_md,
        "requirements": min_quals,   # min quals are the hard requirements
        "responsibilities": responsibilities,
        "preferred_qualifications": pref_quals,
        "tech_mentions": tech,
        "requires_user_fill": False,
        "metacareers_job_id": job_id_from_url(url),
    }


# -----------------------------------------------------------------------------
# main
# -----------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url", help="metacareers.com job_details URL")
    ap.add_argument("--company", default="Meta", help="company folder name (default: Meta)")
    ap.add_argument("--title", default=None, help="override the parsed title")
    ap.add_argument("--print-md", action="store_true",
                    help="dump the proxy-rendered markdown and exit (debug)")
    ap.add_argument("--commit", action="store_true",
                    help="create the app/* branch and commit the listing folder")
    args = ap.parse_args()

    if not is_metacareers(args.url):
        sys.stderr.write(f"fetch_metacareers.py: not a metacareers.com URL: {args.url}\n")
        return 2

    try:
        md = fetch_markdown(args.url)
    except (urllib.error.URLError, TimeoutError) as e:
        sys.stderr.write(
            f"fetch_metacareers.py: reader proxy fetch failed: {e}\n"
            "  Fallback: copy the JD text and run\n"
            "    python scripts/url_ingest.py <url> --from-stdin --company Meta --title '<Role>'\n")
        return 1

    if args.print_md:
        print(md)
        return 0

    if len(md) < 500 or "Qualifications" not in md:
        sys.stderr.write(
            "fetch_metacareers.py: proxy returned little/no JD content "
            f"({len(md)} chars). The posting may be closed or the proxy is rate-limited.\n"
            "  Try again shortly, or paste via url_ingest.py --from-stdin.\n")
        return 1

    listing = parse_metacareers_md(md, args.url)
    if args.title:
        listing["title"] = args.title
    if not listing.get("title"):
        sys.stderr.write("fetch_metacareers.py: could not parse a title; "
                         "rerun with --title '<Role>'\n")
    listing["company"] = args.company

    folder = ui.write_application(listing)
    rel = folder.relative_to(ui.REPO)
    branch = ui.branch_name(folder)
    commit_msg = f'metacareers: add listing for {listing["company"]} — {listing.get("title")}'

    print(f"Application folder: {rel}")
    print(f"Title:             {listing.get('title')}")
    print(f"Location:          {listing.get('location')}")
    if listing.get("comp"):
        c = listing["comp"]
        print(f"Comp:              ${c['min']:,}–${c['max']:,}/{c['period']}")
    print(f"Responsibilities:  {len(listing['responsibilities'])} · "
          f"Min quals: {len(listing['requirements'])} · "
          f"Preferred: {len(listing['preferred_qualifications'])}")
    print(f"Proposed branch:   {branch}")

    committed = False
    if args.commit:
        cmds = (
            ["git", "-C", str(ui.REPO), "checkout", "-b", branch],
            ["git", "-C", str(ui.REPO), "add", "-f", str(rel)],
            ["git", "-C", str(ui.REPO), "commit", "-m", commit_msg],
        )
        committed = True
        for cmd in cmds:
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode != 0:
                sys.stderr.write(f"fetch_metacareers.py: `{' '.join(cmd[3:])}` "
                                 f"exited {r.returncode}\n{r.stdout}{r.stderr}\n")
                committed = False
                break
    if committed:
        print(f"Branched + committed: {branch}")
    else:
        print()
        print("Next (applications/ is gitignored — the -f is intentional):")
        print(f"  git checkout -b {branch}")
        print(f"  git add -f {rel}")
        print(f'  git commit -m "{commit_msg}"')

    return 0


if __name__ == "__main__":
    sys.exit(main())
