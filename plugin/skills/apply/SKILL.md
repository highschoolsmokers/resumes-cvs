---
name: apply
description: >
  Prepare a job application from a listing URL: ingest the listing, tailor the résumé, write the cover letter, and merge into a combined PDF.
  Use when the user says "apply to" followed by a URL, "prep this job", "tailor my resume for" a URL, or pastes a job-listing link and asks for application materials.
  Does NOT submit the application — the user submits via the portal themselves.
---

# apply — prepare application materials from a job URL

End-to-end pipeline for one listing: URL → normalised listing → tailored résumé →
cover letter (the user writes it) → combined PDF. The user reviews and uploads via
the portal themselves — **never submit, never fill portal forms** (SPEC.md §3 trust
boundary; CLAUDE.md).

The URL (and any optional `--company "Name"` / `--title "Role Title"`) will be in
the user's message. If no URL was supplied, ask for one before doing anything.

## Setup

Read these first — they are the source of truth for the system:

- `SPEC.md` — §2 (workflow), §3 (trust boundary), §4 (targets & bases), §7 (cover letters), §9 (implementation: files, scripts, commands).
- `profile.md` — goal, positioning, targeting, target families & bases, résumé style, voice, letterhead, length, forbidden phrases.
- `master-resume.md` and the matching base (`resume-devdocs.md`, `resume-education.md`, `resume-fde.md`, `resume-qa.md`).
- `voice/` — real cover-letter samples, tagged with register/opener/close frontmatter; routed by `scripts/letter/voice_index.py`.
- `RUBRIC.md` — trained cover-letter judgment criteria (SPEC.md §7).

If `SPEC.md` or `profile.md` is missing, stop and tell the user — the repo isn't
set up for this workflow.

Scripts live under `scripts/<area>/` and are run by path. Python scripts that need
`python-docx`/`PyYAML` (`build_cover_letter.py`, `render_resume.py`, `merge_pdfs.py`)
run via `.venv/bin/python`; the rest run on system `python3`. Commands are zsh-friendly.

## Steps

### 1. Ingest the listing

```bash
python3 scripts/ingest/url_ingest.py <URL> --no-commit [--company "<Name>"] [--title "<Role Title>"]
```

This writes `applications/<Company>/<role-slug>-<YYYY-MM-DD>/listing.json` +
`listing.md` and prints the proposed branch and git commands. Inspect the
`listing.json` before continuing:

- `requires_chrome_mcp: true` (LinkedIn) — fetch the JD body with the browser
  tools, then fill the real fields into `listing.md` / `listing.json` and clear
  the flag.
- `requires_user_fill: true` (generic URL, no adapter matched) — the stub carries
  a **`fetch_recipe`** block, and `url_ingest` prints it. It is the domain's
  known-working fetch method (`scripts/ingest/fetch_recipes.json`) — **go straight
  to it; skip the trial GETs.** Meta → run `fetch_metacareers.py`; amazon.jobs →
  curl the HTML with a browser UA and extract per the recipe; unknown domain →
  the recipe defaults to the reader-proxy-first rule. Fill `listing.md` and clear
  the flag. If the domain was unknown and you found a route that works, **train
  the index** so the next listing skips the tests:
  ```bash
  python3 scripts/ingest/fetch_recipes.py record --domain <host> --method <m> --note "…" [--command "… '{url}'"] [--extract "…"]
  ```
  (`python3 scripts/ingest/fetch_recipes.py <URL>` prints the recipe for any URL.)
- Otherwise (Greenhouse / Lever / Ashby fetched via ATS JSON) proceed.

Commit only when the user asks (CLAUDE.md); surface the printed git commands so
they can branch locally if they want.

### 2. Tailor the résumé (§4 — tailor by reuse)

Classify the listing into a target family (`profile.md` → **Target families &
bases**) and start from that base — never blend, never rewrite from scratch. Copy
the base into the application folder as `resume.md`, then tune it to the JD by
**subtracting and reordering only**: drop bullets the role doesn't need, lead with
the ones it does. Every line must already exist in the base / `master-resume.md`;
if the JD wants something you don't have, leave it out — never invent (SPEC.md §3).
Name real gaps to the user rather than papering over them.

Render:

```bash
python3 scripts/resume/render_resume.py --input <folder>/resume.md --out <folder>/resume.pdf
```

### 3. Write the cover letter (§7 — the user writes it)

**The user writes the prose. Never draft-and-render before approval** (CLAUDE.md).
The flow:

1. Read the listing and the chosen base. Pick the two or three strongest matches
   between real work and what the listing asks for.
2. Propose a draft **inline in chat**, paragraph by paragraph — opening (name role
   + company, why it fits), fit (real work → listing asks: what was done, what
   happened), optional disposition close (settled temperament, backward-looking
   only; never a "first thing I'd do" plan-close).
3. Iterate until the user approves the words. Calibrate on the register's
   known-goods and the trained rubric: classify the register (`profile.md` →
   **Cover-letter registers**), run `python3 scripts/letter/voice_index.py
   --register <key>` for the shortlist, and check the draft against `RUBRIC.md`
   (SPEC.md §7).
4. **Only after approval**, write `<folder>/cover-letter.md`, then build + lint:

```bash
.venv/bin/python scripts/letter/build_cover_letter.py --input <folder>/cover-letter.md --out <folder>/cover-letter.docx
python3 scripts/pdf/docx_to_pdf.py <folder>/cover-letter.docx
```

`build_cover_letter.py` enforces the **Letterhead / Length / Forbidden phrases**
from `profile.md` and aborts on `[NEEDS SOURCE]`. Length: 180–300 words. Don't
quote the company's own marketing, don't use company news as a hook, don't open
with "what excites me about" (SPEC.md §7).

### 4. Merge the PDFs

```bash
.venv/bin/python scripts/pdf/merge_pdfs.py <folder>/combined.pdf <folder>/resume.pdf <folder>/cover-letter.pdf
```

Output path **first**, then résumé, then cover letter.

### 5. Hand off to the user

Return the **clickable absolute path to the application folder** (not one file),
plus a short summary:

- Company + role + target-family classification.
- A two- or three-line fit summary, and any real gaps the user should decide on.
- Any `[NEEDS SOURCE: …]` left anywhere (should be zero for ship-ready output;
  surface if not).

Then STOP. The user reviews `combined.pdf`, decides whether to submit, and uploads
it themselves. Commit only if the user asks; if they do, one logical unit per
commit (`<area>: <verb> <object>`, ending with the Co-Authored-By line — SPEC.md §9).

### 6. Canonize a known-good (only when the user asks)

When the user approves a letter **and** asks to add it to the corpus: save it to
`voice/<slug>.md` with frontmatter (`register`, `opener`, `close`, `establishes`,
`approved`) plus the prose annotation. Then train the rubric — score the letter
against `RUBRIC.md`; if it (or a bad example) teaches something the rubric does not
yet hold, propose the change, get approval, edit `RUBRIC.md`, and commit it:
`rubric: <change> (from <sample-id>)`. A rubric edit is always committed (SPEC.md
§7). Run `python3 scripts/letter/voice_index.py --lint` to confirm the new tags.

## What this skill does NOT do

- **Does not submit or fill portal forms.** You hand over PDFs; the user uploads (SPEC.md §3).
- **Does not send email or outreach.** Draft only.
- **Does not invent.** Every résumé line traces to a base / `master-resume.md`; every cover-letter fact to the listing or durable knowledge. Unsourced → `[NEEDS SOURCE]` and stop.
- **Does not render or save the cover letter before the user approves the prose.**
- **Does not commit unless asked.**

## When to stop and ask

- No base matches the detected target family — ask whether to broaden the family or which base to lean on; don't blend.
- The listing calls out a "required" skill genuinely absent from the base — surface it; don't finesse it in the letter.
- Company facts are thin — ask the user for a fact or two rather than leaning on generic phrasing or the company's marketing copy.
- A render/lint step fails (`build_cover_letter.py` abort, forbidden phrase, over length) — stop, show the error, fix before proceeding.

For many listings at once, use `/batch-apply` instead (SPEC.md §9 batch flow).
