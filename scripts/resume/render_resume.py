#!/usr/bin/env python3
"""Render W.S. Gong's styled résumé PDFs directly from master-resume.md.

master-resume.md is the single source of truth. This script parses it into the
two dicts the proven Swiss/Inter OOXML engine in build_resume.py already
consumes (a `bullets` dict and a `plan` dict), then reuses that engine verbatim
to emit a .docx, and converts to PDF with LibreOffice headless.

Three targets, selected from the "## Summary (by target)" section:
    devdocs   ← "Dev Docs / DX"
    education ← "Developer Education"
    fde       ← "Forward-Deployed Engineering"

Usage:
    python scripts/resume/render_resume.py --target devdocs --out path/to/resume.pdf
    python scripts/resume/render_resume.py --all --outdir path/to/dir

The engine (template fonts-swap to Inter, #D44500 accent, two-column layout) is
imported, not reimplemented. We only PARSE markdown into its input shapes.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_resume as engine  # noqa: E402  — reuse the proven OOXML engine

REPO = Path(__file__).resolve().parents[2]
MASTER = REPO / 'master-resume.md'
TEMPLATE = REPO / 'resume-template.docx'

# Heading in "## Summary (by target)" → target key.
TARGET_HEADINGS = {
    'Dev Docs / DX': 'devdocs',
    'Developer Education': 'education',
    'Forward-Deployed Engineering': 'fde',
}

# Skills section label → engine skills_menu key (stable, target-independent).
SKILL_KEYS = {
    'AI & agents': 'ai-agents',
    'Documentation': 'documentation',
    'Languages': 'languages',
    'Testing & CI': 'testing-ci',
    'Platforms': 'platforms',
}

# Per-target skill ordering (CLAUDE-spec'd; FDE leads with agents).
SKILL_ORDER = {
    'devdocs':   ['documentation', 'ai-agents', 'languages', 'platforms', 'testing-ci'],
    'education': ['documentation', 'ai-agents', 'languages', 'platforms', 'testing-ci'],
    'fde':       ['ai-agents', 'languages', 'platforms', 'documentation', 'testing-ci'],
}

# Skills menu label as it should render (title-case "AI & Agents", "Testing &
# CI"). Keyed by the engine key.
SKILL_LABELS = {
    'ai-agents':     'AI & Agents',
    'documentation': 'Documentation',
    'languages':     'Languages',
    'testing-ci':    'Testing & CI',
    'platforms':     'Platforms',
}


# -----------------------------------------------------------------------------
# markdown helpers
# -----------------------------------------------------------------------------

def _strip_md(text: str) -> str:
    """Strip inline markdown emphasis (**bold**, *italic*) — bullets render plain."""
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    return text.strip()


def _slug(s: str) -> str:
    s = re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')
    return s


def split_sections(md: str) -> dict[str, str]:
    """Split the document on `## ` headings → {heading: body}."""
    out: dict[str, str] = {}
    current = None
    buf: list[str] = []
    for line in md.splitlines():
        m = re.match(r'^##\s+(.+?)\s*$', line)
        if m and not line.startswith('###'):
            if current is not None:
                out[current] = '\n'.join(buf)
            current = m.group(1).strip()
            buf = []
        else:
            buf.append(line)
    if current is not None:
        out[current] = '\n'.join(buf)
    return out


# -----------------------------------------------------------------------------
# parse master-resume.md → engine `bullets` dict + per-target `plan` dicts
# -----------------------------------------------------------------------------

def parse_master(md: str) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    lines = md.splitlines()

    # Header block: line 1 = "# Name", line 3 = contact line.
    name = lines[0].lstrip('#').strip()
    contact_line = lines[2].strip()
    parts = [p.strip() for p in contact_line.split('·')]
    if len(parts) != 4:
        sys.exit(f"render_resume: expected 4 '·'-separated contact fields, got {len(parts)}: {contact_line!r}")
    city, email, site_url, linkedin_url = parts
    site = re.sub(r'^https?://', '', site_url).rstrip('/')
    linkedin = re.sub(r'^https?://', '', linkedin_url).rstrip('/')

    sections = split_sections(md)

    bullets: dict[str, Any] = {
        'meta': {
            'canonical_name': name,
            'contact': {'city': city, 'email': email, 'site': site, 'linkedin': linkedin},
        },
        'roles': [],
        'bullets': [],
        'summaries': {},
        'skills_menu': {},
        'education': [],
        'publications_activity': [],
        'community': [],
    }

    _parse_experience(sections.get('Experience', ''), bullets)
    _parse_skills(sections.get('Skills', ''), bullets)
    _parse_education(sections.get('Education', ''), bullets)

    _build_indexes(bullets)
    plans = _parse_summaries(_section_for_summaries(md), bullets)
    return bullets, plans


def _build_indexes(bullets: dict[str, Any]) -> None:
    """Add the `_*_by_id` lookup keys the engine's render() expects."""
    bullets['_bullets_by_id'] = {b['id']: b for b in bullets['bullets']}
    bullets['_roles_by_id'] = {r['id']: r for r in bullets['roles']}
    bullets['_summaries_by_id'] = {}
    bullets['_skills_by_id'] = dict(bullets['skills_menu'])
    bullets['_education_by_id'] = {e['id']: e for e in bullets['education']}


def _parse_experience(body: str, bullets: dict[str, Any]) -> None:
    """Parse `### Title` / meta-line / `- bullet` entries.

    "Previous Experience" is a flat bullet list (no meta line) → one synthetic
    role + one joined bullet, matching the golden `earlier-1997` shape.
    """
    # Split on ### entry headings.
    entries = re.split(r'^###\s+', body, flags=re.MULTILINE)
    for raw in entries:
        raw = raw.strip()
        if not raw:
            continue
        elines = raw.splitlines()
        title = elines[0].strip()
        rest = [l for l in elines[1:]]

        if title == 'Previous Experience':
            items = [_strip_md(l[2:]) for l in rest if l.lstrip().startswith('- ')]
            role_id = 'earlier'
            # Date span derives from the year ranges in the flat list: earliest
            # start to latest end found across "(YYYY–YYYY)" parentheticals.
            years = [int(y) for pair in re.findall(r'\((\d{4})[–-](\d{4})\)', ' '.join(items))
                     for y in pair]
            start = str(min(years)) if years else ''
            end = str(max(years)) if years else ''
            bullets['roles'].append({
                'id': role_id, 'employer': 'Earlier Experience',
                'title_default': '', 'location': '',
                'start': start, 'end': end,
            })
            bullets['bullets'].append({
                'id': f'{role_id}-summary', 'role_id': role_id,
                'text': '; '.join(items) + '.',
                'source_doc': 'master-resume.md',
            })
            continue

        # Meta line: first non-blank, non-bullet line.
        meta = ''
        bullet_start = 0
        for i, l in enumerate(rest):
            if l.strip() and not l.lstrip().startswith('- '):
                meta = l.strip()
                bullet_start = i + 1
                break
        m = [p.strip() for p in meta.split('·')]
        employer = m[0] if len(m) > 0 else ''
        dates = m[1] if len(m) > 1 else ''
        location = m[2] if len(m) > 2 else ''
        start = end = ''
        dm = re.match(r'\s*(\S+?)\s*[–-]\s*(\S+?)\s*$', dates)
        if dm:
            start, end = dm.group(1), dm.group(2)
        elif dates:
            start = end = dates

        # Stable role id from employer + start year.
        role_id = f"{_slug(employer.split('(')[0])}-{start}".strip('-')
        bullets['roles'].append({
            'id': role_id, 'employer': employer,
            'title_default': title, 'location': location,
            'start': start, 'end': end,
        })

        n = 0
        for l in rest[bullet_start:]:
            if l.lstrip().startswith('- '):
                n += 1
                bullets['bullets'].append({
                    'id': f'{role_id}-{n}', 'role_id': role_id,
                    'text': _strip_md(l.lstrip()[2:]),
                    'source_doc': 'master-resume.md',
                })


def _parse_skills(body: str, bullets: dict[str, Any]) -> None:
    for l in body.splitlines():
        l = l.strip()
        m = re.match(r'^-\s+\*\*(.+?):\*\*\s+(.+)$', l)
        if not m:
            continue
        label_raw, content = m.group(1).strip(), m.group(2).strip()
        key = SKILL_KEYS.get(label_raw)
        if not key:
            sys.exit(f"render_resume: unknown skills label {label_raw!r}; update SKILL_KEYS")
        bullets['skills_menu'][key] = {
            'label': SKILL_LABELS[key], 'content': content,
            'source_doc': 'master-resume.md',
        }


def _parse_education(body: str, bullets: dict[str, Any]) -> None:
    for l in body.splitlines():
        l = l.strip()
        # Education degree line: `- **Degree** · School · year[. detail]`
        m = re.match(r'^-\s+\*\*(.+?)\*\*\s+·\s+(.+)$', l)
        if m:
            degree = m.group(1).strip()
            rest = m.group(2).strip()
            rp = [p.strip() for p in rest.split('·')]
            school = rp[0] if rp else ''
            tail = rp[1] if len(rp) > 1 else ''
            # tail like "2021–2024. detail" or "1995" or "2023"
            detail = ''
            year = tail
            if '.' in tail:
                year, detail = tail.split('.', 1)
                year, detail = year.strip(), detail.strip()
            start = end = ''
            ym = re.match(r'\s*(\S+?)\s*[–-]\s*(\S+?)\s*$', year)
            if ym:
                start, end = ym.group(1), ym.group(2)
            else:
                end = year.strip()
            bullets['education'].append({
                'id': _slug(degree)[:24], 'school': school, 'degree': degree,
                'location': '', 'start': start, 'end': end, 'detail': detail,
                'source_doc': 'master-resume.md',
            })
            continue
        # Writing line → publications_activity (one entry, rendered whole at
        # normal weight by the engine's build_publications_inner).
        wm = re.match(r'^\*\*(Writing):\*\*\s+(.+)$', l)
        if wm:
            bullets['publications_activity'].append(_strip_md(wm.group(2)))


def _section_for_summaries(md: str) -> str:
    """Return the body of '## Summary (by target)' (split_sections keys on the
    full heading text)."""
    return split_sections(md).get('Summary (by target)', '')


def _parse_summaries(body: str, bullets: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Each `### <heading>` block: **bold tagline**, then summary paragraph.
    Ignore the `*Leads with:*` note."""
    plans: dict[str, dict[str, Any]] = {}
    blocks = re.split(r'^###\s+', body, flags=re.MULTILINE)
    for raw in blocks:
        raw = raw.strip()
        if not raw:
            continue
        blines = raw.splitlines()
        heading = blines[0].strip()
        # Heading may carry a trailing "*(primary)*" annotation.
        heading_clean = re.sub(r'\s*\*\(.*?\)\*\s*$', '', heading).strip()
        target = TARGET_HEADINGS.get(heading_clean)
        if not target:
            continue
        tagline = ''
        summary = ''
        for l in blines[1:]:
            ls = l.strip()
            if not ls:
                continue
            bm = re.match(r'^\*\*(.+?)\*\*$', ls)
            if bm and not tagline:
                tagline = bm.group(1).strip()
                continue
            if ls.startswith('*Leads with:'):
                continue
            if tagline and not summary:
                summary = ls
        # Bare-URL convention: the rendered résumé shows the site without the
        # scheme (the contact line does the same via meta.site).
        summary = re.sub(r'https?://(www\.)', r'\1', summary)
        plans[target] = _make_plan(target, tagline, summary, bullets)
    return plans


def _make_plan(target: str, tagline: str, summary: str,
               bullets: dict[str, Any]) -> dict[str, Any]:
    # All roles, all their bullets, in document order — tailoring would subset
    # this, but the three full résumés use every entry.
    bullets_by_role: dict[str, list[str]] = {}
    for r in bullets['roles']:
        rid = r['id']
        ids = [b['id'] for b in bullets['bullets'] if b['role_id'] == rid]
        if ids:
            bullets_by_role[rid] = ids
    return {
        'target_role_family': None,
        'tagline': tagline,
        'summary_text': summary,
        'summary_id': None,
        'skill_order': SKILL_ORDER[target],
        'bullets_by_role': bullets_by_role,
        'show_publications': True,
        'show_community': False,
    }


# -----------------------------------------------------------------------------
# parse a tailored résumé (single summary, custom order, free-form skill labels)
# -----------------------------------------------------------------------------

def _parse_skills_relaxed(body: str, bullets: dict[str, Any]) -> None:
    """Like _parse_skills but accepts any label. A tailored résumé renames and
    reorders skill blocks (e.g. 'APIs & developer content'); key = slug(label),
    display label = the label verbatim, order = document order."""
    for l in body.splitlines():
        l = l.strip()
        m = re.match(r'^-\s+\*\*(.+?):\*\*\s+(.+)$', l)
        if not m:
            continue
        label_raw, content = m.group(1).strip(), m.group(2).strip()
        bullets['skills_menu'][_slug(label_raw)] = {
            'label': label_raw, 'content': content, 'source_doc': 'tailored',
        }


def _parse_preamble_summary(lines: list[str]) -> tuple[str, str]:
    """A tailored résumé carries one summary in the preamble: a **bold tagline**
    line, then the summary paragraph, before the first `## ` / `---`."""
    tagline = summary = ''
    for l in lines[3:]:
        if l.startswith('## ') or l.strip() == '---':
            if tagline and summary:
                break
            continue
        ls = l.strip()
        if not ls:
            continue
        bm = re.match(r'^\*\*(.+?)\*\*$', ls)
        if bm and not tagline:
            tagline = bm.group(1).strip()
            continue
        if tagline and not summary:
            summary = ls
    return tagline, summary


def parse_tailored(md: str) -> tuple[dict[str, Any], dict[str, Any]]:
    lines = md.splitlines()
    name = lines[0].lstrip('#').strip()
    contact_line = lines[2].strip()
    parts = [p.strip() for p in contact_line.split('·')]
    if len(parts) != 4:
        sys.exit(f"render_resume: expected 4 '·'-separated contact fields, got {len(parts)}: {contact_line!r}")
    city, email, site_url, linkedin_url = parts
    site = re.sub(r'^https?://', '', site_url).rstrip('/')
    linkedin = re.sub(r'^https?://', '', linkedin_url).rstrip('/')

    sections = split_sections(md)
    bullets: dict[str, Any] = {
        'meta': {
            'canonical_name': name,
            'contact': {'city': city, 'email': email, 'site': site, 'linkedin': linkedin},
        },
        'roles': [], 'bullets': [], 'summaries': {}, 'skills_menu': {},
        'education': [], 'publications_activity': [], 'community': [],
    }
    _parse_experience(sections.get('Experience', ''), bullets)
    _parse_skills_relaxed(sections.get('Skills', ''), bullets)
    _parse_education(sections.get('Education', ''), bullets)
    _build_indexes(bullets)

    tagline, summary = _parse_preamble_summary(lines)
    summary = re.sub(r'https?://(www\.)', r'\1', summary)

    bullets_by_role: dict[str, list[str]] = {}
    for r in bullets['roles']:
        ids = [b['id'] for b in bullets['bullets'] if b['role_id'] == r['id']]
        if ids:
            bullets_by_role[r['id']] = ids

    plan = {
        'target_role_family': None,
        'tagline': tagline,
        'summary_text': summary,
        'summary_id': None,
        'skill_order': list(bullets['skills_menu'].keys()),
        'bullets_by_role': bullets_by_role,
        'show_publications': True,
        'show_community': False,
    }
    return bullets, plan


# -----------------------------------------------------------------------------
# render
# -----------------------------------------------------------------------------

def _docx_to_pdf(docx: Path, outdir: Path) -> Path:
    subprocess.run(
        ['soffice', '--headless', '--convert-to', 'pdf', '--outdir',
         str(outdir), str(docx)],
        check=True, capture_output=True,
    )
    return outdir / (docx.stem + '.pdf')


def render_target(target: str, out: Path, bullets: dict, plan: dict,
                  docx_only: bool = False) -> None:
    """Render into the template and write `out`. With docx_only, emit the .docx
    and skip the internal soffice PDF step (so a batch can convert every docx in
    ONE soffice invocation via docx_to_pdf.py — soffice is single-instance)."""
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        work = Path(td) / 'work'
        docx = Path(td) / f'{target}.docx'
        engine.unpack_docx(TEMPLATE, work)
        engine.render(work, plan, bullets)
        engine.pack_docx(work, docx)
        if docx_only:
            out.write_bytes(docx.read_bytes())
        else:
            pdf = _docx_to_pdf(docx, Path(td))
            out.write_bytes(pdf.read_bytes())
    kind = 'docx' if docx_only else 'pdf'
    print(f"{target} → {out}  ({out.stat().st_size:,} bytes, {kind})")


def emit_base(bullets: dict, plan: dict) -> str:
    """Serialize a parsed (bullets, plan) back into the tailored `--input`
    markdown format, so a master target can be materialized as a reusable base
    résumé (per SPEC.md §4 Targets & bases)."""
    m = bullets['meta']
    c = m['contact']
    out: list[str] = [
        f"# {m['canonical_name']}",
        "",
        f"{c['city']} · {c['email']} · https://{c['site']} · https://{c['linkedin']}",
        "",
        f"**{plan['tagline']}**",
        "",
        plan['summary_text'],
        "",
        "---",
        "",
        "## Experience",
    ]
    for r in bullets['roles']:
        rids = plan['bullets_by_role'].get(r['id'], [])
        if not rids:
            continue
        out.append("")
        if r['id'] == 'earlier' or r['employer'] == 'Earlier Experience':
            out.append("### Previous Experience")
            out.append("")
            text = bullets['_bullets_by_id'][rids[0]]['text'].rstrip('.')
            for item in (i.strip() for i in text.split(';')):
                out.append(f"- {item}")
            continue
        out.append(f"### {r['title_default']}")
        yr = (f"{r['start']}–{r['end']}"
              if r['start'] and r['end'] and r['start'] != r['end']
              else (r['start'] or r['end']))
        out.append(f"{r['employer']} · {yr} · {r['location']}")
        out.append("")
        for bid in rids:
            out.append(f"- {bullets['_bullets_by_id'][bid]['text']}")

    out += ["", "## Skills"]
    order = plan.get('skill_order') or list(bullets['skills_menu'].keys())
    for key in order:
        s = bullets['skills_menu'].get(key)
        if s:
            out.append(f"- **{s['label']}:** {s['content']}")

    out += ["", "## Education"]
    for e in bullets['education']:
        yr = f"{e['start']}–{e['end']}" if e['start'] and e['end'] else (e['end'] or e['start'])
        tail = f"{yr}. {e['detail']}" if e['detail'] else yr
        out.append(f"- **{e['degree']}** · {e['school']} · {tail}")

    for line in bullets.get('publications_activity', []):
        out += ["", f"**Writing:** {line}"]

    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--target', choices=sorted(TARGET_HEADINGS.values()))
    ap.add_argument('--out', type=Path, help='output PDF path (single target)')
    ap.add_argument('--all', action='store_true', help='render all three targets')
    ap.add_argument('--outdir', type=Path, default=Path.cwd(),
                    help='output dir for --all (default: cwd)')
    ap.add_argument('--input', type=Path,
                    help='render a tailored résumé markdown (single summary, '
                         'custom order/skills) instead of a master-resume.md target')
    ap.add_argument('--emit-base', action='store_true',
                    help='with --target: write the target as a reusable base '
                         'résumé markdown (--input format) to --out, no render')
    ap.add_argument('--docx-only', action='store_true',
                    help='write .docx and skip the internal soffice PDF step '
                         '(convert later in one batched docx_to_pdf.py call)')
    args = ap.parse_args()

    if not TEMPLATE.exists() and not args.emit_base:
        sys.exit(f"template not found: {TEMPLATE}")

    if args.input:
        if not args.out:
            ap.error("--input requires --out")
        if not args.input.exists():
            sys.exit(f"input not found: {args.input}")
        bullets, plan = parse_tailored(args.input.read_text(encoding='utf-8'))
        render_target('tailored', args.out, bullets, plan, docx_only=args.docx_only)
        return 0

    if not MASTER.exists():
        sys.exit(f"master-resume.md not found: {MASTER}")

    bullets, plans = parse_master(MASTER.read_text(encoding='utf-8'))

    if args.emit_base:
        if not args.target or not args.out:
            ap.error("--emit-base requires --target <name> --out <file.md>")
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(emit_base(bullets, plans[args.target]), encoding='utf-8')
        print(f"{args.target} base → {args.out}")
        return 0

    if args.all:
        for target in sorted(plans):
            out = args.outdir / f'{date.today().isoformat()}-wsgong-resume-{target}.pdf'
            render_target(target, out, bullets, plans[target], docx_only=args.docx_only)
        return 0

    if not args.target:
        ap.error("supply --target <name> --out <path> or --all")
    if not args.out:
        ap.error("--target requires --out")
    render_target(args.target, args.out, bullets, plans[args.target],
                  docx_only=args.docx_only)
    return 0


if __name__ == '__main__':
    sys.exit(main())
