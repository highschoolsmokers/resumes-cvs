# Resume style spec — W.S. Gong template

This is the canonical style for W.S. Gong's resumes. The user prefers to be referred to as **W.S. Gong** (not Billy) in all resume/CV contexts. A blank template .docx with this styling preserved lives at `resume-template.docx` in this repo — prefer copying and editing that file over rebuilding from scratch, since faithful reproduction via docx-js is fiddly.

> **Note on scope.** The typography and layout values below describe an earlier Arial / single-column style that is preserved here for historical reference. The current canonical style is the **Swiss redesign (2026-04-20)** — see "Current canonical style (Swiss, 2026-04-20)" near the end of this doc for the authoritative settings. The fields in the middle of this doc (font, sizes for the legacy Arial master) are reference only; the layout, section order, voice, and content rules remain authoritative.

All sizes below are in **DXA** (1440 DXA = 1 inch) or **half-points** (20 = 10pt), matching the raw OOXML. The docx skill uses these same units.

## Page

- **Size:** US Letter — 12240 × 15840 DXA
- **Margins:** top 900, right 1080, bottom 720, left 1080 (≈ 0.625" / 0.75" / 0.5" / 0.75")
- **Content width:** 10080 DXA. Tab stops for right-aligned dates are set at **9360** (not full width — leaves a small right-gutter for visual balance).

## Default font (legacy reference)

- **Arial** for everything — ascii, cs, eastAsia, hAnsi all set to Arial
- **Default body size:** 10pt (sz=20)

## Built-in heading styles (in styles.xml)

These are defined but mostly **unused** in the document body — the resume overrides headings via direct run formatting instead. Keep the definitions in place for portability.

| Style | Size | Color | Notes |
|-------|------|-------|-------|
| Title | 28pt | default | bold via run |
| Heading 1 | 16pt | #2E74B5 | |
| Heading 2 | 13pt | #2E74B5 | |
| Heading 3 | 12pt | #1F4D78 | |
| Heading 4 | 10pt | #2E74B5 | italic |
| Hyperlink | 10pt | #0563C1 | underlined (but **overridden inline** to #666666 in contact block) |

## Name line (top of document)

- Arial **bold**, **14pt** (sz=28), color `#000000`
- **Letter spacing: 80** (= 4pt expanded tracking) via `<w:spacing w:val="80"/>` — this is the signature visual touch on the name
- Paragraph spacing: after 40
- Content is all-caps with periods: `W.S. GONG`

## Contact block (two lines under name)

- Arial **9pt** (sz=18), color `#666666` (medium grey)
- Separator between items: `"  |  "` (two spaces, pipe, two spaces)
- Hyperlinks in this block are **color-overridden to #666666** (not the default blue) and carry no underline beyond the style default — the look is plain grey text. Keep underline off visually by using the grey run color on hyperlink text.
- Line 1: City, State  |  phone  |  email
- Line 2: website  |  linkedin.com/in/…  |  github.com/…
- Paragraph spacing after each line: 20

## Section divider (horizontal rule)

An empty paragraph carrying only a bottom border:

- Border: single line, color `#333333`, size 4 (= 0.5pt), space 1
- Spacing: before 60, after 60

Rules appear **between every major section** (under contact block, after summary, after skills, after experience). Never use table rows or unicode box-drawing characters as dividers.

## Section heading (e.g., `RELEVANT SKILLS`, `EXPERIENCE`, `EDUCATION`)

- Arial **bold**, **9pt** (sz=18), color `#000000`
- **Letter spacing: 60** (= 3pt expanded tracking) — less than the name, more than default
- Content is **ALL CAPS**
- Paragraph spacing: before 80, after 20

## Summary paragraph

- Arial regular, 9pt, color `#000000`
- Paragraph spacing: before 60, after 80
- Flows as a single dense paragraph. No bold or italic within.

## Skills block

Each skill category is its own paragraph with **inline** formatting (no separate label line):

- Category label: Arial **bold**, 9pt, color default — ends with `": "` (colon + space)
- Items: Arial regular, 9pt, comma-separated
- Paragraph spacing after each skill line: 40
- Typical categories used: `LLM & AI Systems`, `Security & Adversarial Testing`, `Documentation & Communication`, `Languages & Tools` — adapt per role

## Job entry (repeat for each position)

**Line 1 — Title + Date (same paragraph, tab-separated):**

- Tab stop: right-aligned at position **9360**
- Title: Arial **bold**, **10pt** (sz=20), color `#000000`
- Tab character (`\t`) — plain Arial run, no size
- Date: Arial regular, **9pt** (sz=18), color `#666666`
- Paragraph spacing: before 120, after 20

**Line 2 — Company + Location:**

- Company: Arial **italic**, 9pt, color `#666666`
- Separator: `"  |  "` in plain Arial 9pt #666666
- Location: same as separator run (not italic)
- Paragraph spacing after: 60

**Bullets — accomplishments under each role:**

- Use `pStyle="ListParagraph"` + `numId=2` (defined in numbering.xml — bullet "•", indent left 360, hanging 180)
- Run: Arial 9pt, color `#000000`
- Paragraph spacing after: 20
- **Never** type a bullet character manually — always reference the numbering config.

## Compressed "Earlier Roles" block

For older jobs that don't justify full entries:

- Single paragraph, Arial **8.5pt** (sz=17), color `#666666`, left indent 360
- Format: `Title, Company (YYYY–YYYY)  |  Title, Company (YYYY–YYYY)  |  …`
- En-dash (`–`) for year ranges, not hyphen
- Appears as the last entry in the EXPERIENCE section

## Education entries

Each degree is one paragraph with inline formatting:

- Degree: Arial **bold**, 9pt, color default
- Separator + school: `"  —  "` (two spaces, em-dash, two spaces) + Arial 9pt #666666
- School line continues with `", YEAR"` — no comma before the dash
- Paragraph spacing after: 30
- Typical entries: degree, undergrad, certificates — most recent first

## Numbering config (reproduce in any new template)

```xml
<!-- numId=2: the bullet style used for all accomplishments -->
<w:abstractNum w:abstractNumId="2">
  <w:multiLevelType w:val="hybridMultilevel"/>
  <w:lvl w:ilvl="0">
    <w:start w:val="1"/>
    <w:numFmt w:val="bullet"/>
    <w:lvlText w:val="•"/>
    <w:lvlJc w:val="left"/>
    <w:pPr><w:ind w:left="360" w:hanging="180"/></w:pPr>
  </w:lvl>
</w:abstractNum>
```

## Section order (top to bottom)

1. Name
2. Contact (two lines)
3. Rule
4. Summary paragraph
5. Rule
6. RELEVANT SKILLS (4 categories)
7. Rule
8. EXPERIENCE (newest first, each with title/date line, company/location line, 2–4 bullets)
9. Earlier Roles (compressed one-liner)
10. Rule
11. EDUCATION (newest first)

No photo, no objective statement, no references line, no page numbers. Single column. One page preferred but not enforced.

## Color palette (hex)

- Body / headings: `#000000`
- Secondary text (dates, company, contact): `#666666`
- Section rule: `#333333`
- (Built-in heading blue `#2E74B5` defined but unused in body)

## Current canonical style (Swiss, 2026-04-20)

The resume follows five non-negotiable Swiss principles:

1. **Clarity is the goal. Remove before you add.**
2. **Objectivity over expression. Justify with structure.**
3. **The grid is the foundation of every layout.**
4. **Typography carries hierarchy, rhythm, and tone.**
5. **Asymmetric balance on a rigorous grid.**

### Type family

- **Inter** for everything — one family, hierarchy by weight and size. No second face. Raleway and Lato are gone.
- Inter OTF binaries are **embedded into the DOCX** at build time so the PDF renders identically on any machine (LibreOffice, Word, macOS Preview). `build_resume.py` resolves Inter from `~/Library/Fonts` or `/Library/Fonts`; install with `brew install --cask font-inter` if missing.

### Accent

- `#D44500` (orange). Applied to the name line, tagline, and hyperlinks. Never on body text, section labels, or secondary metadata.

### Grid

- 2-column table, widths **2520 | 7560 DXA** (≈ 25 % | 75 %). Left column is a metadata gutter; right column is the reading column.
- No horizontal rules. The grid + vertical rhythm divide sections — no ink spent on decoration.
- Baseline unit: **120 DXA** (6pt). All `w:before` / `w:after` values are 0, 60, 120, 240, 360, or 480 — never a random intermediate.

### Typographic hierarchy

| Role | Size | Weight | Color |
|------|------|--------|-------|
| Name | 24pt (sz=48) | Bold | `#000000` |
| Tagline | 16pt (sz=32) | Bold | `#D44500` (accent) |
| Contact line | 10pt (sz=20) | Regular | `#000000` / links `#D44500` |
| Section label (Skills, Experience, …) | 12pt (sz=24) | Bold | `#000000` |
| Role title | 11pt (sz=22) | Bold | `#000000` |
| Company / employer | 10pt (sz=20) | Regular | `#666666` |
| Body paragraph | 10pt (sz=20) | Regular | `#000000` |
| Date / location (left gutter) | 9pt (sz=18), uppercase | Regular | `#666666` |

### Per-entry structure (Experience, Education)

- **Left cell (2520 DXA):** section label (first entry of the section only, sz=24 bold) → date range (sz=18 uppercase) → optional location (sz=18 uppercase).
- **Right cell (7560 DXA):** role title on line 1 (sz=22 bold) → company on line 2 (sz=20 `#666666`) → paragraph description on line 3+ (sz=20). No inline em-dashes joining title and company; hierarchy comes from the stack.
- **Vertical padding is uniform:** every content row has `tcMar.top = tcMar.bottom = 120 DXA`. Combined with the rule rows (zero-padded so the rule sits flush) this gives a single ~240 DXA between-block gap that matches both *between entries* and *between sections* in feel — the document reads as one rhythm, not "section ↔ section ↔ section".

### Skills, Projects, Publications, Community (list sections)

- Each item is its own paragraph — that IS the list. No bullet characters.
- Format: `**Label** — value` in a single line, bold label then em-dash then regular value.
- Spacing: first item `before=0`, subsequent items `before=240` (matches the entry-to-entry gap in Experience / Education).

### Whole-document consistency is a *build-time assertion*

The consistency rules above are not aspirational — they are enforced. `build_resume.py` calls `scripts/lint_resume.py` at the end of every render and exits non-zero if any of the following diverge across the document (not per-section — **whole-document**):

- Fixed row heights (`<w:trHeight>`) — must not appear anywhere.
- `tcMar.top` / `tcMar.bottom` — one value used across every content row.
- Font family — `Inter` only in body runs.
- Font sizes — must come from the approved scale (18, 20, 22, 24, 28, 32, 48 half-points for content; 2 and 12 reserved for structural spacer paragraphs).
- Paragraph `w:before` — must come from the 60 DXA baseline lattice (0, 60, 80, 120, 160, 240, 280, 360, 480).

Run manually with `python3 scripts/lint_resume.py <resume.docx>`. A failing resume never gets written.

### What Swiss forbids for this template

- Second type family (including Lato reappearing, Raleway, Helvetica Neue, Arial).
- Inline mixed-weight headers like `**Company** — Title` on one line.
- Accent color anywhere except name / tagline / hyperlinks.
- Bullet characters in the list sections (Skills, Projects, etc.).
- Random spacing values not on the 60 DXA lattice.
- Fixed `<w:trHeight>` on any row — height must be content-driven.
- Divergent `tcMar.top` / `tcMar.bottom` across content rows.

Hairline `#333333` 0.5pt rules between major sections are *kept* — they are structural Swiss elements per Müller-Brockmann, not decoration. Rule rows are zero-padded by design and excluded from the `tcMar` uniformity check in `scripts/lint_resume.py`.

Any other deviation requires explicit user sign-off — see CLAUDE.md §6.

## When creating or editing a resume

**Preferred:** copy `resume-template.docx` and replace text content via the docx skill's unpack → Edit → pack flow. This preserves every style above exactly.

**From scratch (docx-js):** explicitly set page size to US Letter, override the docDefaults, and apply all run properties inline per the specs above — docx-js does not read an existing styles.xml.

**Do not:** use tables as dividers, use unicode bullets (`•` typed manually), switch the body font, add blue hyperlink styling in the contact block, or introduce second-tier fonts for emphasis.
