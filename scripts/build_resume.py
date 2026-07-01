#!/usr/bin/env python3
"""Swiss/Inter OOXML rendering engine for W.S. Gong's resume.

This module is the rendering engine only. It exposes three entry points used by
`scripts/render_resume.py`:

    unpack_docx(docx_path, dst)   — explode resume-template.docx into OOXML parts
    render(work, plan, bullets)   — mutate the OOXML in place from plan + bullets dicts
    pack_docx(src, docx_path)     — re-zip the OOXML parts into a .docx

`render()` takes a `plan` dict (summary text, skill order, bullets-by-role,
section toggles) and a `bullets` dict (roles, bullets, skills, education,
publications, community — with `_*_by_id` lookup indexes). Both dicts are built
by the caller (`render_resume.py` parses `master-resume.md` into them); this
module does no file parsing of its own beyond the template DOCX.
"""
from __future__ import annotations

import re
import shutil
import sys
import zipfile
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent  # scripts/build_resume.py → repo root
TEMPLATE = REPO / 'resume-template.docx'


# -----------------------------------------------------------------------------
# docx packing / unpacking
# -----------------------------------------------------------------------------

def _pretty_print_xml(path: Path) -> None:
    """Reformat an OOXML part into pretty-printed form.

    The source template keeps `word/document.xml` on a single line; the
    regex-based transformations in this script expect pretty-printed input
    with `      <w:tr>\\n` separators. We normalise once on unpack.

    lxml is a hard requirement — without it, the downstream regexes silently
    fail to match and you get a confusing "expected 5 rows in template, got 0"
    assertion deep in render(). Fail loudly here instead.
    """
    try:
        from lxml import etree as ET  # type: ignore
    except ImportError as exc:
        raise SystemExit(
            "build_resume.py: lxml is required for OOXML pretty-printing.\n"
            "  Install it:  python3 -m pip install 'lxml>=5,<6' --break-system-packages\n"
            "  Or install all deps:  python3 -m pip install -r requirements.txt --break-system-packages"
        ) from exc
    parser = ET.XMLParser(remove_blank_text=True)
    tree = ET.parse(str(path), parser)
    # `pretty_print=True` uses 2-space indentation which matches the legacy layout.
    xml = ET.tostring(tree, pretty_print=True, xml_declaration=True, encoding='UTF-8',
                      standalone=True)
    path.write_bytes(xml)


def unpack_docx(docx_path: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True)
    with zipfile.ZipFile(docx_path) as zf:
        zf.extractall(dst)
    # Pretty-print the XML parts our regexes touch.
    for sub in ('word/document.xml',
                'word/_rels/document.xml.rels',
                'word/header1.xml'):
        part = dst / sub
        if part.exists():
            _pretty_print_xml(part)


def pack_docx(src: Path, docx_path: Path) -> None:
    if docx_path.exists():
        docx_path.unlink()
    with zipfile.ZipFile(docx_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(src.rglob('*')):
            if path.is_file():
                zf.write(path, path.relative_to(src))


def copy_unpacked_sibling(work: Path, out_docx: Path) -> Path:
    """Copy the unpacked working tree next to the output .docx for legible diffs."""
    sibling = out_docx.with_name(out_docx.stem + '.unpacked')
    if sibling.exists():
        shutil.rmtree(sibling)
    shutil.copytree(work, sibling)
    return sibling


# -----------------------------------------------------------------------------
# XML building blocks — extracted verbatim from the previous in-place script
# -----------------------------------------------------------------------------

# Swiss-correct: a hairline rule between sections IS structural — it marks the
# division so the grid stops "running together." Müller-Brockmann's grid
# systems use exactly this. sz=4 = 0.5pt, color #333333 — quiet but legible.
RULE_ROW = '''      <w:tr>
        <w:trPr>
          <w:cantSplit w:val="1"/>
        </w:trPr>
        <w:tc>
          <w:tcPr>
            <w:tcW w:w="10080" w:type="dxa"/>
            <w:gridSpan w:val="2"/>
            <w:tcBorders>
              <w:top w:color="000000" w:space="0" w:sz="0" w:val="nil"/>
              <w:left w:color="000000" w:space="0" w:sz="0" w:val="nil"/>
              <w:bottom w:color="333333" w:space="0" w:sz="4" w:val="single"/>
              <w:right w:color="000000" w:space="0" w:sz="0" w:val="nil"/>
            </w:tcBorders>
            <w:tcMar>
              <w:top w:w="0" w:type="dxa"/>
              <w:left w:w="0" w:type="dxa"/>
              <w:bottom w:w="0" w:type="dxa"/>
              <w:right w:w="0" w:type="dxa"/>
            </w:tcMar>
            <w:vAlign w:val="top"/>
          </w:tcPr>
          <w:p>
            <w:pPr>
              <w:spacing w:before="0" w:after="0" w:line="20" w:lineRule="auto"/>
              <w:rPr><w:sz w:val="2"/><w:szCs w:val="2"/></w:rPr>
            </w:pPr>
          </w:p>
        </w:tc>
      </w:tr>
'''


def xml_escape(text: str) -> str:
    """Minimal XML escaping for body text."""
    return (text.replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;'))


def para_body(text: str, before: int = 120) -> str:
    return f'''          <w:p>
            <w:pPr>
              <w:spacing w:before="{before}" w:line="240" w:lineRule="auto"/>
              <w:rPr><w:rFonts w:ascii="Inter" w:cs="Inter" w:eastAsia="Inter" w:hAnsi="Inter"/><w:sz w:val="20"/><w:szCs w:val="20"/></w:rPr>
            </w:pPr>
            <w:r>
              <w:rPr><w:rFonts w:ascii="Inter" w:cs="Inter" w:eastAsia="Inter" w:hAnsi="Inter"/><w:sz w:val="20"/><w:szCs w:val="20"/><w:rtl w:val="0"/></w:rPr>
              <w:t xml:space="preserve">{text}</w:t>
            </w:r>
          </w:p>
'''


def para_label_then_value(label: str, value: str, before: int = 120) -> str:
    """Render label and value as two stacked paragraphs — bold label on its
    own line, plain value on the next. Used in Publications & Activity /
    Community lists where a dash-continued single line was too dense.

    `before` governs the gap ABOVE the label (separation from the previous
    item). The value paragraph sits tight under the label with before=0.
    """
    return f'''          <w:p>
            <w:pPr>
              <w:spacing w:before="{before}" w:line="240" w:lineRule="auto"/>
              <w:rPr><w:rFonts w:ascii="Inter" w:cs="Inter" w:eastAsia="Inter" w:hAnsi="Inter"/><w:b w:val="1"/><w:bCs w:val="1"/><w:sz w:val="20"/><w:szCs w:val="20"/></w:rPr>
            </w:pPr>
            <w:r>
              <w:rPr><w:rFonts w:ascii="Inter" w:cs="Inter" w:eastAsia="Inter" w:hAnsi="Inter"/><w:b w:val="1"/><w:bCs w:val="1"/><w:sz w:val="20"/><w:szCs w:val="20"/><w:rtl w:val="0"/></w:rPr>
              <w:t xml:space="preserve">{label}</w:t>
            </w:r>
          </w:p>
          <w:p>
            <w:pPr>
              <w:spacing w:before="0" w:line="240" w:lineRule="auto"/>
              <w:rPr><w:rFonts w:ascii="Inter" w:cs="Inter" w:eastAsia="Inter" w:hAnsi="Inter"/><w:sz w:val="20"/><w:szCs w:val="20"/></w:rPr>
            </w:pPr>
            <w:r>
              <w:rPr><w:rFonts w:ascii="Inter" w:cs="Inter" w:eastAsia="Inter" w:hAnsi="Inter"/><w:sz w:val="20"/><w:szCs w:val="20"/><w:rtl w:val="0"/></w:rPr>
              <w:t xml:space="preserve">{value}</w:t>
            </w:r>
          </w:p>
'''


INTER = '<w:rFonts w:ascii="Inter" w:cs="Inter" w:eastAsia="Inter" w:hAnsi="Inter"/>'


def entry_row(date_line: str, loc_line: str, company: str, title: str, desc: str,
              section_label: str = "") -> str:
    """One experience/education entry as a full <w:tr>.

    Swiss layout:
      LEFT  (2520 DXA, ≈25%): section label (first entry only), date, location.
      RIGHT (7560 DXA, ≈75%): role title on line 1 (bold), company on line 2
        (secondary grey), description paragraph on line 3.
    Hierarchy comes from weight and size on a baseline of 120 DXA, never from
    inline em-dashes or mixed-weight runs in the same line.
    """
    left_paras: list[str] = []
    if section_label:
        # Section label sized to match template Heading1 (sz=24, 12pt) so
        # Skills / Projects / Experience / Education / Publications / Community
        # all read at the same level. before=0 so it sits flush at tcMar.top
        # (matching the right-cell title which also has before=0); after=160
        # gives the date paragraph beneath ~8pt of breathing room.
        left_paras.append(
            f'<w:p><w:pPr><w:spacing w:before="0" w:after="160" w:line="240" w:lineRule="auto"/>'
            f'<w:rPr>{INTER}<w:b w:val="1"/><w:bCs w:val="1"/><w:sz w:val="24"/><w:szCs w:val="24"/></w:rPr></w:pPr>'
            f'<w:r><w:rPr>{INTER}<w:b w:val="1"/><w:bCs w:val="1"/><w:sz w:val="24"/><w:szCs w:val="24"/><w:rtl w:val="0"/></w:rPr>'
            f'<w:t xml:space="preserve">{section_label}</w:t></w:r></w:p>'
        )
    left_paras.append(
        f'<w:p><w:pPr><w:spacing w:before="0" w:after="0" w:line="240" w:lineRule="auto"/>'
        f'<w:rPr>{INTER}<w:color w:val="666666"/><w:sz w:val="18"/><w:szCs w:val="18"/></w:rPr></w:pPr>'
        f'<w:r><w:rPr>{INTER}<w:color w:val="666666"/><w:sz w:val="18"/><w:szCs w:val="18"/><w:rtl w:val="0"/></w:rPr>'
        f'<w:t xml:space="preserve">{date_line}</w:t></w:r></w:p>'
    )
    if loc_line:
        left_paras.append(
            f'<w:p><w:pPr><w:spacing w:before="0" w:after="0" w:line="240" w:lineRule="auto"/>'
            f'<w:rPr>{INTER}<w:color w:val="666666"/><w:sz w:val="18"/><w:szCs w:val="18"/></w:rPr></w:pPr>'
            f'<w:r><w:rPr>{INTER}<w:color w:val="666666"/><w:sz w:val="18"/><w:szCs w:val="18"/><w:rtl w:val="0"/></w:rPr>'
            f'<w:t xml:space="preserve">{loc_line}</w:t></w:r></w:p>'
        )
    left_content = "".join(left_paras)

    # Right column: three stacked paragraphs, typographic hierarchy by weight+size.
    # Line 1 — role title (bold, body+1pt). When the caller passes no title
    # (sparse entries like Earlier Roles), the company takes the bold slot.
    role_title = title if title else company
    role_para = (
        f'<w:p><w:pPr><w:spacing w:before="0" w:after="0" w:line="240" w:lineRule="auto"/>'
        f'<w:rPr>{INTER}<w:b w:val="1"/><w:bCs w:val="1"/><w:sz w:val="22"/><w:szCs w:val="22"/></w:rPr></w:pPr>'
        f'<w:r><w:rPr>{INTER}<w:b w:val="1"/><w:bCs w:val="1"/><w:sz w:val="22"/><w:szCs w:val="22"/><w:rtl w:val="0"/></w:rPr>'
        f'<w:t xml:space="preserve">{role_title}</w:t></w:r></w:p>'
    )
    # Line 2 — company (regular, secondary). Suppressed when it's already the
    # bold line (title-less entry).
    if title:
        company_para = (
            f'<w:p><w:pPr><w:spacing w:before="60" w:after="0" w:line="240" w:lineRule="auto"/>'
            f'<w:rPr>{INTER}<w:color w:val="666666"/><w:sz w:val="20"/><w:szCs w:val="20"/></w:rPr></w:pPr>'
            f'<w:r><w:rPr>{INTER}<w:color w:val="666666"/><w:sz w:val="20"/><w:szCs w:val="20"/><w:rtl w:val="0"/></w:rPr>'
            f'<w:t xml:space="preserve">{company}</w:t></w:r></w:p>'
        )
    else:
        company_para = ""
    # Line 3+ — description paragraph (body). Empty desc is allowed (some
    # education entries have no detail).
    if desc:
        desc_para = (
            f'<w:p><w:pPr><w:spacing w:before="120" w:after="0" w:line="240" w:lineRule="auto"/>'
            f'<w:rPr>{INTER}<w:sz w:val="20"/><w:szCs w:val="20"/></w:rPr></w:pPr>'
            f'<w:r><w:rPr>{INTER}<w:sz w:val="20"/><w:szCs w:val="20"/><w:rtl w:val="0"/></w:rPr>'
            f'<w:t xml:space="preserve">{desc}</w:t></w:r></w:p>'
        )
    else:
        desc_para = ""
    right_content = role_para + company_para + desc_para

    # Uniform 200 DXA top/bottom on every row (matches _swiss_normalize's
    # substitution for template-derived rows). Combined with stripped trHeight,
    # this produces a single consistent vertical rhythm across every row in
    # the document — Skills, Projects, every Experience entry, every Education
    # entry, Publications, Community.
    nil_borders = (
        '<w:tcBorders>'
        '<w:top w:color="000000" w:space="0" w:sz="0" w:val="nil"/>'
        '<w:left w:color="000000" w:space="0" w:sz="0" w:val="nil"/>'
        '<w:bottom w:color="000000" w:space="0" w:sz="0" w:val="nil"/>'
        '<w:right w:color="000000" w:space="0" w:sz="0" w:val="nil"/>'
        '</w:tcBorders>'
    )
    return f'''      <w:tr>
        <w:trPr>
          <w:cantSplit w:val="0"/>
        </w:trPr>
        <w:tc>
          <w:tcPr>
            <w:tcW w:w="2520" w:type="dxa"/>
            {nil_borders}
            <w:tcMar>
              <w:top w:w="120" w:type="dxa"/>
              <w:left w:w="72" w:type="dxa"/>
              <w:bottom w:w="120" w:type="dxa"/>
              <w:right w:w="240" w:type="dxa"/>
            </w:tcMar>
            <w:vAlign w:val="top"/>
          </w:tcPr>
          {left_content}
        </w:tc>
        <w:tc>
          <w:tcPr>
            <w:tcW w:w="7560" w:type="dxa"/>
            {nil_borders}
            <w:tcMar>
              <w:top w:w="120" w:type="dxa"/>
              <w:left w:w="0" w:type="dxa"/>
              <w:bottom w:w="120" w:type="dxa"/>
              <w:right w:w="100" w:type="dxa"/>
            </w:tcMar>
            <w:vAlign w:val="top"/>
          </w:tcPr>
          {right_content}
        </w:tc>
      </w:tr>
'''


# -----------------------------------------------------------------------------
# section body constructors — from plan + bullets into XML chunks
# -----------------------------------------------------------------------------

def build_summary_xml(plan: dict, bullets: dict) -> str:
    if plan.get('summary_text'):
        text = plan['summary_text']
    else:
        text = bullets['_summaries_by_id'][plan['summary_id']]['text']
    return f'''          <w:p>
            <w:pPr>
              <w:spacing w:before="280" w:line="240" w:lineRule="auto"/>
              <w:rPr><w:rFonts w:ascii="Inter" w:cs="Inter" w:eastAsia="Inter" w:hAnsi="Inter"/><w:sz w:val="20"/><w:szCs w:val="20"/></w:rPr>
            </w:pPr>
            <w:r>
              <w:rPr><w:rFonts w:ascii="Inter" w:cs="Inter" w:eastAsia="Inter" w:hAnsi="Inter"/><w:sz w:val="20"/><w:szCs w:val="20"/><w:rtl w:val="0"/></w:rPr>
              <w:t xml:space="preserve">{xml_escape(text)}</w:t>
            </w:r>
          </w:p>
'''


def build_skills_inner(plan: dict, bullets: dict) -> str:
    """Render Skills as label/value stacks — group label on its own line
    (bold), skill list on the next. Matches publications/community styling."""
    chunks: list[str] = []
    for i, key in enumerate(plan['skill_order']):
        entry = bullets['_skills_by_id'][key]
        chunks.append(para_label_then_value(
            xml_escape(entry['label']),
            xml_escape(entry['content']),
            before=0 if i == 0 else 240,
        ))
    return "".join(chunks)


def build_experience_entries(plan: dict, bullets: dict) -> list[tuple]:
    """Produce entry_row tuples for each role the plan references, in plan order.

    Output tuple: (date_line, loc_line, company, title, desc)
    """
    entries: list[tuple] = []
    target_family = plan.get('target_role_family')

    # Roles appear in the order they're declared in the source markdown.
    role_order = [r['id'] for r in bullets['roles']]
    plan_roles = plan.get('bullets_by_role') or {}

    for role_id in role_order:
        if role_id not in plan_roles:
            continue
        role = bullets['_roles_by_id'][role_id]
        bullet_ids = plan_roles[role_id]
        if not bullet_ids:
            continue

        start = role.get('start', '')
        end = role.get('end', '')
        if start and end and start != end:
            date_line = f"{start}–{end}".upper()
        else:
            date_line = (start or end).upper()
        loc_line = (role.get('location') or '').upper()
        company = xml_escape(role.get('employer', ''))
        title_alts = role.get('title_alternates') or {}
        title = title_alts.get(target_family) or role.get('title_default', '')
        title = xml_escape(title)

        bullet_texts = [
            xml_escape(bullets['_bullets_by_id'][bid]['text'])
            for bid in bullet_ids
        ]
        desc = " ".join(bullet_texts)
        entries.append((date_line, loc_line, company, title, desc))

    return entries


def _education_entries_static(bullets: dict) -> list[tuple]:
    out: list[tuple] = []
    for edu in bullets.get('education', []):
        date_line = f"{edu.get('start', '')}–{edu.get('end', '')}".upper().strip(' –')
        if edu.get('start') == edu.get('end'):
            date_line = (edu.get('start') or '').upper()
        loc_line = (edu.get('location') or '').upper()
        out.append((
            date_line, loc_line,
            xml_escape(edu['school']),
            xml_escape(edu['degree']),
            xml_escape(edu.get('detail', '')),
        ))
    return out


def build_publications_inner(bullets: dict) -> str:
    """Render publications_activity entries at normal body weight — only section
    labels/titles are bold. Each entry is one plain paragraph."""
    items = bullets.get('publications_activity', [])
    chunks: list[str] = []
    for i, item in enumerate(items):
        chunks.append(para_body(
            xml_escape(item),
            before=0 if i == 0 else 240,
        ))
    return "".join(chunks)


def build_community_inner(bullets: dict) -> str:
    """Render community as label/value stacks — label on its own line (bold),
    value on the next."""
    items = bullets.get('community', [])
    chunks: list[str] = []
    for i, item in enumerate(items):
        if ' — ' in item:
            label, value = item.split(' — ', 1)
        else:
            label, value = item, ''
        chunks.append(para_label_then_value(
            xml_escape(label),
            xml_escape(value),
            before=0 if i == 0 else 240,
        ))
    return "".join(chunks)


# -----------------------------------------------------------------------------
# OOXML mutation pass (unchanged, factored)
# -----------------------------------------------------------------------------

INTER_SYSTEM_PATHS = (
    Path.home() / 'Library' / 'Fonts',          # macOS user fonts
    Path('/Library/Fonts'),                     # macOS system fonts
    Path('/usr/share/fonts'),                   # Linux
    Path('/usr/local/share/fonts'),             # Linux
    Path.home() / '.fonts',                     # Linux user fonts
)


def _find_inter_file(weight_style: str) -> Path:
    """Locate an Inter OTF on the system. Fail loud if missing — Swiss design
    without Inter is not Swiss design.
    """
    candidates = [f'Inter-{weight_style}.otf', f'Inter-{weight_style}.ttf']
    for base in INTER_SYSTEM_PATHS:
        for c in candidates:
            p = base / c
            if p.exists():
                return p
    raise SystemExit(
        f"Inter-{weight_style}.otf not found in ~/Library/Fonts or /Library/Fonts.\n"
        f"  Install it:  brew install --cask font-inter"
    )


def _embed_inter_fonts(work: Path) -> None:
    """Overwrite the template's embedded Raleway / Lato font binaries with
    Inter's OTF bytes. Keeps filenames (and thus relationship IDs) stable."""
    font_dir = work / 'word' / 'fonts'
    if not font_dir.exists():
        return
    # Map template-filename → Inter weight/style. Raleway + Lato both map onto
    # Inter (single family does all four styles).
    mapping = {
        'Raleway-regular.ttf':    'Regular',
        'Raleway-bold.ttf':       'Bold',
        'Raleway-italic.ttf':     'Italic',
        'Raleway-boldItalic.ttf': 'BoldItalic',
        'Lato-regular.ttf':       'Regular',
        'Lato-bold.ttf':          'Bold',
        'Lato-italic.ttf':        'Italic',
        'Lato-boldItalic.ttf':    'BoldItalic',
    }
    for fname, weight_style in mapping.items():
        dst = font_dir / fname
        if not dst.exists():
            continue
        src = _find_inter_file(weight_style)
        dst.write_bytes(src.read_bytes())


def _swiss_normalize(s: str) -> str:
    """Apply the Swiss redesign to any template-inherited XML fragment.

    - Collapse legacy Raleway / Lato font names to Inter (the unified grotesque).
    - Rewrite old 2-column grid widths (3525 / 6555 DXA) to the new 25/75 split
      (2520 / 7560 DXA).
    Safe to run on document.xml, styles.xml, fontTable.xml, header1.xml.
    """
    s = re.sub(r'\b(?:Raleway|Lato)\b', 'Inter', s)
    s = s.replace('w:w="3525.12"',           'w:w="2520"')
    s = s.replace('w:w="6554.879999999999"', 'w:w="7560"')
    s = re.sub(r'<w:tcW w:w="3525" w:type="dxa"/>', '<w:tcW w:w="2520" w:type="dxa"/>', s)
    s = re.sub(r'<w:tcW w:w="6555" w:type="dxa"/>', '<w:tcW w:w="7560" w:type="dxa"/>', s)
    # Right-cell left-margin alignment: the template's Skills / Projects /
    # Publications / Community rows have tcMar.left=100 on the right cell,
    # while my entry_row (Experience / Education) uses tcMar.left=0. The 100
    # DXA gap visibly indents Projects items relative to Experience titles.
    # Collapse the right-cell left margin to 0 so column 2 has a single
    # baseline. Other directions (top/bottom/right) keep their 100.
    s = s.replace('<w:left w:w="100.0" w:type="dxa"/>', '<w:left w:w="0" w:type="dxa"/>')
    # Uniform vertical cell padding across every row in the table — no row
    # gets more breathing room than another. This is the foundation of the
    # vertical rhythm; combined with stripping trHeight (below), every row's
    # height is purely a function of its content.
    s = s.replace('<w:top w:w="100.0" w:type="dxa"/>',    '<w:top w:w="120" w:type="dxa"/>')
    s = s.replace('<w:bottom w:w="100.0" w:type="dxa"/>', '<w:bottom w:w="120" w:type="dxa"/>')
    s = s.replace('<w:top w:w="72.0" w:type="dxa"/>',     '<w:top w:w="120" w:type="dxa"/>')
    s = s.replace('<w:bottom w:w="72.0" w:type="dxa"/>',  '<w:bottom w:w="120" w:type="dxa"/>')
    # The Heading1 style adds w:before="80" to its paragraph spacing — that's
    # what makes the "Skills" / "Projects" / "Publications" / "Community" labels
    # sit slightly lower than the section label in entry_row sections. Strip
    # it so the heading sits flush with tcMar.top.
    s = re.sub(r'<w:spacing w:before="80" w:lineRule="auto"/>',
               '<w:spacing w:before="0" w:lineRule="auto"/>', s)
    # Drop fixed minimum row heights inherited from the template (1440 / 2400
    # DXA). They pad short rows to 1+ inch and produce the unpredictable
    # vertical-spacing artifact: rows with little content read as enormous,
    # rows with lots read as tight. Letting content drive height restores
    # rhythm.
    s = re.sub(r'\s*<w:trHeight w:val="\d+" w:hRule="atLeast"/>', '', s)
    return s


def render(work: Path, plan: dict, bullets: dict) -> None:
    doc_path  = work / 'word' / 'document.xml'
    rels_path = work / 'word' / '_rels' / 'document.xml.rels'
    h1_path   = work / 'word' / 'header1.xml'
    styles_path = work / 'word' / 'styles.xml'
    fonts_path  = work / 'word' / 'fontTable.xml'

    # Clear template instruction banner
    h1_path.write_text(_swiss_normalize(h1_path.read_text().replace(
        'To add your own information, go to File &gt; Make a copy. Then delete these instructions!',
        ''
    )))

    # Swiss normalization on the parts whose style inheritance flows into the
    # document body but which we don't touch otherwise.
    if styles_path.exists():
        styles_path.write_text(_swiss_normalize(styles_path.read_text()))
    if fonts_path.exists():
        # The template embeds Raleway / Lato binaries under those names. After
        # _swiss_normalize rewrites the *names* to "Inter", the embed elements
        # still point at the old font bytes — LibreOffice fails to resolve and
        # falls back to Liberation Serif. Fix by swapping the actual OTF bytes
        # for Inter's, keeping the relationship IDs and filenames stable so no
        # other machinery has to care.
        _embed_inter_fonts(work)
        fonts_xml = _swiss_normalize(fonts_path.read_text())
        # The rename collapses Raleway + Lato into two identical <w:font
        # w:name="Inter"> entries. Deduplicate so fontTable.xml is valid.
        fonts_xml = re.sub(
            r'(<w:font w:name="Inter"><w:embed[^>]*>(?:<w:embed[^>]*>)*</w:font>)(\s*<w:font w:name="Inter">.*?</w:font>)+',
            r'\1',
            fonts_xml, flags=re.DOTALL,
        )
        fonts_path.write_text(fonts_xml)

    content = _swiss_normalize(doc_path.read_text())
    rels_content = rels_path.read_text()

    # Step 2: hyperlink relationships
    hyperlinks = {
        'rIdEmail':  f"mailto:{bullets['meta']['contact']['email']}",
        'rIdSite':   f"https://{bullets['meta']['contact']['site']}",
        'rIdGithub': f"https://{bullets['meta']['contact']['linkedin']}",
    }
    new_rels = ''.join(
        f'  <Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" Target="{target}" TargetMode="External"/>\n'
        for rid, target in hyperlinks.items()
    )
    rels_content = rels_content.replace('</Relationships>', new_rels + '</Relationships>')
    rels_path.write_text(rels_content)

    # Step 3: row structure sanity check
    row_starts = [m.start() for m in re.finditer(r'      <w:tr>\n', content)]
    row_ends   = [m.end()   for m in re.finditer(r'      </w:tr>\n', content)]
    assert len(row_starts) == len(row_ends) == 5, \
        f"expected 5 rows in template, got {len(row_starts)}"

    # Step 4: name / tagline / contact
    name = bullets['meta']['canonical_name']
    first, last = (name.split(' ', 1) + [''])[:2]
    tagline = plan.get('tagline') or 'Engineer, Editor, Writer'
    header_replacements = [
        ('<w:t xml:space="preserve">Your</w:t>', f'<w:t xml:space="preserve">{xml_escape(first)}</w:t>'),
        ('<w:t xml:space="preserve">Name</w:t>', f'<w:t xml:space="preserve">{xml_escape(last)}</w:t>'),
        ('<w:t xml:space="preserve">Creative Director</w:t>', f'<w:t xml:space="preserve">{xml_escape(tagline)}</w:t>'),
        ('<w:t xml:space="preserve">123 Your Street</w:t>',
         f'<w:t xml:space="preserve">{xml_escape(bullets["meta"]["contact"]["city"])}</w:t>'),
    ]
    for old, new in header_replacements:
        assert old in content, f"header replacement miss: {old!r}"
        content = content.replace(old, new, 1)

    # Strip the duplicate "Your Name" paragraph in the contact block.
    content, n = re.subn(
        r'<w:p[^>]*w14:paraId="00000005">.*?</w:p>',
        '', content, count=1, flags=re.DOTALL,
    )
    assert n == 1, "failed to remove redundant name paragraph in contact block"

    # Drop the decorative horizontal-rule drawing paragraphs from the top row.
    drawing_para_pattern = re.compile(
        r'<w:p[^>]*>(?:(?!</w:p>).)*?<w:drawing>.*?</w:drawing>.*?</w:p>',
        re.DOTALL,
    )
    content, _ = drawing_para_pattern.subn('', content)

    # Linkify website / linkedin (the rIdGithub relationship is the template's;
    # the contact field holds the LinkedIn URL).
    site_text   = bullets['meta']['contact']['site']
    github_text = bullets['meta']['contact']['linkedin']
    city_run_pattern = re.compile(
        r'(<w:p[^>]*w14:paraId="00000007"[^>]*>.*?)'
        r'<w:r\b[^>]*>\s*<w:rPr>.*?</w:rPr>\s*'
        r'<w:t xml:space="preserve">Your City, ST 12345</w:t>\s*</w:r>'
        r'(.*?</w:p>)',
        re.DOTALL,
    )
    site_hyperlinks = (
        f'<w:hyperlink r:id="rIdSite" w:history="1">'
        '<w:r><w:rPr><w:rFonts w:ascii="Inter" w:cs="Inter" w:eastAsia="Inter" w:hAnsi="Inter"/>'
        '<w:color w:val="d44500"/><w:sz w:val="20"/><w:szCs w:val="20"/><w:rtl w:val="0"/></w:rPr>'
        f'<w:t xml:space="preserve">{xml_escape(site_text)}</w:t></w:r></w:hyperlink>'
        '<w:r><w:rPr><w:rFonts w:ascii="Inter" w:cs="Inter" w:eastAsia="Inter" w:hAnsi="Inter"/>'
        '<w:sz w:val="20"/><w:szCs w:val="20"/><w:rtl w:val="0"/></w:rPr>'
        '<w:t xml:space="preserve">  |  </w:t></w:r>'
        '<w:hyperlink r:id="rIdGithub" w:history="1">'
        '<w:r><w:rPr><w:rFonts w:ascii="Inter" w:cs="Inter" w:eastAsia="Inter" w:hAnsi="Inter"/>'
        '<w:color w:val="d44500"/><w:sz w:val="20"/><w:szCs w:val="20"/><w:rtl w:val="0"/></w:rPr>'
        f'<w:t xml:space="preserve">{xml_escape(github_text)}</w:t></w:r></w:hyperlink>'
    )
    m = city_run_pattern.search(content)
    assert m, "could not locate contact line 2 (Your City) paragraph"
    content = content[:m.start()] + m.group(1) + site_hyperlinks + m.group(2) + content[m.end():]

    # Remove phone paragraph
    content, n = re.subn(
        r'<w:p[^>]*w14:paraId="00000008">.*?123\.456\.7890.*?</w:p>\s*',
        '', content, count=1, flags=re.DOTALL,
    )
    assert n == 1, "failed to remove phone paragraph"

    # Linkify email
    email_text = bullets['meta']['contact']['email']
    # Anchor inside the email paragraph (paraId 00000009) so regex backtracking
    # cannot eat rows. Replace the inner run that holds the placeholder email.
    email_hyperlink = (
        '<w:hyperlink r:id="rIdEmail" w:history="1">'
        '<w:r><w:rPr><w:rFonts w:ascii="Inter" w:cs="Inter" w:eastAsia="Inter" w:hAnsi="Inter"/>'
        '<w:color w:val="d44500"/><w:sz w:val="20"/><w:szCs w:val="20"/><w:rtl w:val="0"/></w:rPr>'
        f'<w:t xml:space="preserve">{xml_escape(email_text)}</w:t></w:r></w:hyperlink>'
    )
    email_para_pattern = re.compile(
        r'(<w:p[^>]*w14:paraId="00000009"[^>]*>)(.*?)(</w:p>)',
        re.DOTALL,
    )
    def _replace_email(m: re.Match) -> str:
        # Strip any pre-existing <w:r>…no_reply…</w:r> runs and drop the
        # hyperlink in. The template only carries the placeholder email, so we
        # replace the entire paragraph body.
        return m.group(1) + email_hyperlink + m.group(3)
    content, n = email_para_pattern.subn(_replace_email, content, count=1)
    assert n == 1, "failed to linkify email"

    # Step 5: capture the Skills row as a template for other make_row() calls
    row_starts = [m.start() for m in re.finditer(r'      <w:tr>\n', content)]
    row_ends   = [m.end()   for m in re.finditer(r'      </w:tr>\n', content)]
    row_template = content[row_starts[1]:row_ends[1]]
    row_template = re.sub(r'<w:bookmarkStart[^/]*/>', '', row_template)
    row_template = re.sub(r'<w:bookmarkEnd[^/]*/>', '', row_template)
    row_template, n = re.subn(
        r'<w:p[^>]*w14:paraId="0000000A">.*?</w:p>',
        '', row_template, count=1, flags=re.DOTALL,
    )
    assert n == 1, "could not locate ㅡ marker paragraph"

    def make_row(label: str, inner_content_xml: str) -> str:
        row = row_template.replace(
            '<w:t xml:space="preserve">Skills</w:t>',
            f'<w:t xml:space="preserve">{label}</w:t>',
            1,
        )
        lorem_para = re.search(
            r'<w:p[^>]*w14:paraId="0000000D">.*?</w:p>',
            row, re.DOTALL,
        )
        assert lorem_para, "could not locate Lorem paragraph in template row"
        row = row[:lorem_para.start()] + inner_content_xml + row[lorem_para.end():]
        return RULE_ROW + row

    # Step 6: build section rows from the plan
    skills_inner = build_skills_inner(plan, bullets)

    experience_entries = build_experience_entries(plan, bullets)
    education_entries  = _education_entries_static(bullets)

    def section_with_entries(section_label: str, entries: list[tuple]) -> str:
        rows: list[str] = [RULE_ROW]
        for i, (date_line, loc_line, company, title, desc) in enumerate(entries):
            rows.append(entry_row(
                date_line=date_line, loc_line=loc_line,
                company=company, title=title, desc=desc,
                section_label=section_label if i == 0 else "",
            ))
        return "".join(rows)

    chunks: list[str] = [make_row("Skills", skills_inner)]
    chunks.append(section_with_entries("Experience", experience_entries))
    chunks.append(section_with_entries("Education", education_entries))
    if plan.get('show_publications', True):
        chunks.append(make_row("Publications &amp; Activity", build_publications_inner(bullets)))
    if plan.get('show_community', True):
        chunks.append(make_row("Community", build_community_inner(bullets)))

    new_rows_xml = "".join(chunks)

    # Step 7: inject summary paragraph under the email link
    summary_xml = build_summary_xml(plan, bullets)
    content, n = re.subn(
        r'(<w:p[^>]*w14:paraId="00000009">.*?</w:p>)',
        lambda m: m.group(1) + summary_xml,
        content, count=1, flags=re.DOTALL,
    )
    assert n == 1, "could not locate email paragraph to insert summary after"

    # Step 8: splice generated rows in for rows 1..4
    row_starts = [m.start() for m in re.finditer(r'      <w:tr>\n', content)]
    row_ends   = [m.end()   for m in re.finditer(r'      </w:tr>\n', content)]
    content = content[:row_starts[1]] + new_rows_xml + content[row_ends[4]:]

    doc_path.write_text(content)
