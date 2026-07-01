#!/usr/bin/env python3
"""Map master-resume.md onto LinkedIn's profile fields.

LinkedIn has no public write API for personal profiles, so this script does the
one thing a script honestly can: it parses the single source of truth
(master-resume.md) and emits every LinkedIn field pre-formatted to LinkedIn's
character limits and W.S.'s voice rules. Paste the sections into LinkedIn's
editor, or feed the --json output to the browser-drive step.

It never invents. Every field derives from master-resume.md; parsing reuses
render_resume.parse_master so the LinkedIn copy can never drift from the résumé.

Targets (same three as the résumé, --target picks which drives headline + About;
the rest of the profile is shared):
    devdocs   ← "Dev Docs / DX"      (résumé primary)
    education ← "Developer Education"
    fde       ← "Forward-Deployed Engineering"

Usage:
    python scripts/linkedin/linkedin_export.py --target education
    python scripts/linkedin/linkedin_export.py --target education --out linkedin-profile.md
    python scripts/linkedin/linkedin_export.py --target education --json linkedin-profile.json

LinkedIn field limits enforced (script warns, never silently truncates):
    headline 220 · about 2600 · experience title 100 · experience desc 2000
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "resume"))
import render_resume as rr  # noqa: E402  — reuse the master-resume.md parser (scripts/resume)

REPO = Path(__file__).resolve().parents[2]
MASTER = REPO / 'master-resume.md'

LIMITS = {
    'headline': 220,
    'about': 2600,
    'exp_title': 100,
    'exp_desc': 2000,
    'skills_max': 50,
}


def _no_em_dash(s: str) -> str:
    """Voice rule (profile.md, job-search register): no em-dashes. En-dashes in
    date/number ranges stay. Replace any em-dash with a colon-spaced form and
    collapse the runs of whitespace that produces."""
    return re.sub(r'\s{2,}', ' ', s.replace('—', ': ')).strip()


def _headline(tagline: str, summary: str) -> str:
    """tagline + the summary's opening clause, trimmed to fit 220 chars.

    Fully grounded: every word is already in master-resume.md. No invention."""
    lead = re.split(r'(?<=[a-z])\.\s', summary, maxsplit=1)[0].rstrip('.').strip()
    head = f"{tagline} | {lead}"
    head = _no_em_dash(head)
    if len(head) <= LIMITS['headline']:
        return head
    # Trim the lead clause at a word boundary so the whole thing fits.
    budget = LIMITS['headline'] - len(tagline) - len(' | ')
    words, acc = lead.split(), []
    for w in words:
        if len(' '.join(acc + [w])) > budget:
            break
        acc.append(w)
    return f"{tagline} | {' '.join(acc)}"


def _skills_list(bullets: dict[str, Any]) -> list[str]:
    """LinkedIn skills are discrete tags, not sentences. Split each skills line
    on commas into individual entries, flatten, de-dupe preserving order."""
    seen: set[str] = set()
    out: list[str] = []
    for s in bullets['skills_menu'].values():
        # Split on commas that are NOT inside parentheses, so a parenthetical
        # tool-list like "(Markdown, Vale, Git)" stays with its skill.
        for raw in re.split(r',\s*(?![^()]*\))', s['content']):
            skill = _no_em_dash(raw).strip()
            # Drop a trailing parenthetical qualifier like "(Claude)" or
            # "(Markdown, Vale, Git)" — the tag is the tool name; LinkedIn
            # matches tags, not descriptions.
            skill = re.sub(r'\s*\([^)]*\)\s*$', '', skill).strip()
            if skill and skill.lower() not in seen:
                seen.add(skill.lower())
                out.append(skill)
    return out


def build_profile(target: str) -> dict[str, Any]:
    bullets, plans = rr.parse_master(MASTER.read_text(encoding='utf-8'))
    if target not in plans:
        sys.exit(f"linkedin_export: no summary for target {target!r}")
    plan = plans[target]
    meta = bullets['meta']
    contact = meta['contact']

    experience: list[dict[str, Any]] = []
    for r in bullets['roles']:
        rids = plan['bullets_by_role'].get(r['id'], [])
        if not rids:
            continue
        texts = [_no_em_dash(bullets['_bullets_by_id'][b]['text']) for b in rids]
        if r['id'] == 'earlier' or r['employer'] == 'Earlier Experience':
            # Flat prior-roles list → one "Earlier experience" block, one line each.
            items = texts[0].rstrip('.').split('; ')
            experience.append({
                'title': 'Earlier experience',
                'company': '', 'location': '',
                'start': r['start'], 'end': r['end'],
                'description': '\n'.join(items),
            })
            continue
        experience.append({
            'title': _no_em_dash(r['title_default']),
            'company': _no_em_dash(r['employer']),
            'location': r['location'],
            'start': r['start'], 'end': r['end'],
            'description': '\n'.join(f"• {t}" for t in texts),
        })

    education = []
    for e in bullets['education']:
        yr = f"{e['start']}–{e['end']}" if e['start'] and e['end'] else (e['end'] or e['start'])
        education.append({
            'degree': _no_em_dash(e['degree']),
            'school': e['school'],
            'years': yr,
            'detail': _no_em_dash(e['detail']),
        })

    return {
        'target': target,
        'name': meta['canonical_name'],
        'location': contact['city'],
        'headline': _headline(plan['tagline'], plan['summary_text']),
        'about': _no_em_dash(plan['summary_text']),
        'experience': experience,
        'education': education,
        'skills': _skills_list(bullets),
        'writing': [_no_em_dash(w) for w in bullets.get('publications_activity', [])],
        'links': {
            'website': f"https://{contact['site']}",
            'linkedin': f"https://{contact['linkedin']}",
        },
    }


def _warn_limits(p: dict[str, Any]) -> list[str]:
    warns = []
    if len(p['headline']) > LIMITS['headline']:
        warns.append(f"headline is {len(p['headline'])} chars (limit {LIMITS['headline']})")
    if len(p['about']) > LIMITS['about']:
        warns.append(f"about is {len(p['about'])} chars (limit {LIMITS['about']})")
    for x in p['experience']:
        if len(x['title']) > LIMITS['exp_title']:
            warns.append(f"experience title {x['title']!r} is {len(x['title'])} chars (limit {LIMITS['exp_title']})")
        if len(x['description']) > LIMITS['exp_desc']:
            warns.append(f"experience desc for {x['title']!r} is {len(x['description'])} chars (limit {LIMITS['exp_desc']})")
    if len(p['skills']) > LIMITS['skills_max']:
        warns.append(f"{len(p['skills'])} skills (LinkedIn shows up to {LIMITS['skills_max']})")
    return warns


def render_md(p: dict[str, Any]) -> str:
    L: list[str] = []
    L.append(f"# LinkedIn profile — {p['name']}  ·  target: {p['target']}")
    L.append("")
    L.append("> Generated from master-resume.md by scripts/linkedin/linkedin_export.py.")
    L.append("> Paste each field into LinkedIn's editor. Every claim traces to the résumé.")
    L.append("")
    L.append(f"## Headline  ({len(p['headline'])}/{LIMITS['headline']})")
    L.append("")
    L.append(p['headline'])
    L.append("")
    L.append(f"## About  ({len(p['about'])}/{LIMITS['about']})")
    L.append("")
    L.append(p['about'])
    L.append("")
    L.append("## Experience")
    for x in p['experience']:
        L.append("")
        header = x['title']
        if x['company']:
            header += f" — {x['company']}"
        L.append(f"### {header}")
        meta = "  ·  ".join(v for v in [
            f"{x['start']}–{x['end']}" if x['start'] and x['end'] else (x['end'] or x['start']),
            x['location'],
        ] if v)
        if meta:
            L.append(f"*{meta}*")
        L.append("")
        L.append(x['description'])
    L.append("")
    L.append("## Education")
    for e in p['education']:
        line = f"- **{e['degree']}** · {e['school']} · {e['years']}"
        if e['detail']:
            line += f". {e['detail']}"
        L.append(line)
    L.append("")
    L.append(f"## Skills  ({len(p['skills'])} tags)")
    L.append("")
    L.append(", ".join(p['skills']))
    if p['writing']:
        L.append("")
        L.append("## Writing (Featured / About addendum)")
        for w in p['writing']:
            L.append(f"- {w}")
    L.append("")
    L.append("## Links")
    L.append(f"- Website: {p['links']['website']}")
    L.append(f"- LinkedIn: {p['links']['linkedin']}")
    L.append("")
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--target', default='devdocs',
                    choices=sorted(rr.TARGET_HEADINGS.values()),
                    help='which summary drives headline + About (default: devdocs)')
    ap.add_argument('--out', type=Path, help='write the copy-paste markdown here '
                    '(default: print to stdout)')
    ap.add_argument('--json', type=Path, help='also write machine-readable JSON '
                    '(consumed by the browser-drive step)')
    args = ap.parse_args()

    if not MASTER.exists():
        sys.exit(f"master-resume.md not found: {MASTER}")

    profile = build_profile(args.target)
    for w in _warn_limits(profile):
        print(f"warning: {w}", file=sys.stderr)

    md = render_md(profile)
    if args.out:
        args.out.write_text(md, encoding='utf-8')
        print(f"{args.target} → {args.out}  ({len(md):,} chars)", file=sys.stderr)
    else:
        print(md)

    if args.json:
        args.json.write_text(json.dumps(profile, indent=2, ensure_ascii=False),
                             encoding='utf-8')
        print(f"{args.target} → {args.json}  (json)", file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
