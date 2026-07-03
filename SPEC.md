# SPEC — Job Search System

Single source of truth for the generic system. User-specific inputs (goal,
positioning, targeting, résumé style, voice, channel) live in `profile.md`;
source material in `master-resume.md` and `voice/`. Sections 1–8 are the rules;
section 9 is the implementation. Read this before operating.

---

## 1. What the system does

Input: one or more job descriptions, plus the user's source material — the master
résumé, the bases derived from it, a corpus of real cover letters, and
`profile.md` (goal, positioning, targeting, résumé style, voice, channel).

Output per JD:

- a résumé tailored from the matching base (§4);
- a cover letter the user writes, the system supplying facts, structure, and a draft;
- on request, a short referral message.

Every claim traces to real material; nothing invented, nothing auto-submitted.
Success is responses and interviews, not documents produced: tailoring is fast so
the user applies at volume, and positioning and channel matter more than document
quality.

The system positions truthful limitations as credentials: an employment gap, a
career change, or a non-traditional path stated plainly and framed as a strength,
not hidden or apologized for. The user's limitations and reframings are in
`profile.md`.

The system also keeps the user's LinkedIn profile in step with the master résumé
(§8).

---

## 2. Workflow

Per JD, in order:

1. Read the JD, `profile.md`, the matching résumé base, and the voice samples (`voice/`).
2. Tailor the résumé from the matching base (§4).
3. Draft the cover letter. The user writes it (see Cover letters); the agent supplies facts and structure and proposes inline.
4. Render to PDF; hand the application folder to the user.

On request, a short referral message (see Channel). The user reviews and uploads;
nothing is auto-submitted.

Principles:

- **Plain text until render.** All artifacts stay editable text until the final PDF step.
- **Grounded, not invented.** Every claim traces to real material; anything unsourced is flagged `[NEEDS SOURCE]`, never fabricated.
- **Tailor by reuse.** Start from the matching base and tune it to the listing (§4); never rewrite from scratch.
- **Voice by example.** Calibrate the cover letter on the real letter samples, not on a list of banned phrases.

One listing at a time, or many in a batch: résumé tailoring runs in parallel, and
cover letters come out as drafts the user must rewrite.

---

## 3. Trust boundary

The agent produces artifacts; the user uploads them. Never submit an
application, never fill a portal form, never send an email or outreach message.
Never invent: every résumé line traces to the master résumé or a base, every
cover-letter fact to the listing or durable knowledge. If a claim cannot be
sourced, write `[NEEDS SOURCE: …]` and stop. These hold in the batch flow too.

The one live change is the LinkedIn sync (§8), to the user's own profile only:
dry-run by default, confirmed per save. Never toward an employer.

---

## 4. Targets & bases

One base résumé per target family, each a distinct identity and emphasis.
Tailoring picks the matching base and tunes it to the JD by subtracting and
reordering, never inventing. Never send one blended résumé. The families and
bases are in `profile.md`.

Where a base differs from the master résumé only in identity and summary,
generate it from the master and regenerate whenever the master changes. Where a
base needs a reordered or reframed body, maintain it by hand.

---

## 5. Voice

The voice rules — how prose written as the user must sound, and the letterhead,
length, and forbidden phrases — are user-specific and defined in `profile.md`.

---

## 6. Résumé

The résumé's register, structure, and visual style are user-specific and defined
in `profile.md`. The template and linter enforce the style (see Implementation).

---

## 7. Cover letters

**Purpose.** Show, in the user's restrained voice, that the listing was read and
the background fits. Not a sales pitch: the reader should conclude the user can do
the work, not that they want the job.

**Who writes it.** The user. The agent reads the listing and the chosen base,
supplies facts and structure, and proposes a draft inline to approve or rewrite.
Only after approval is it saved, grammar-passed, voice-checked, and rendered.
Never generate the final prose from scratch; never save or render before approval.

**Shape.** 180–300 words, signed: an opening paragraph, a fit paragraph, optionally a short close.

1. **Opening.** Why the role fits, in a sentence or two. Name the role and company so it is plainly not a form letter. No warm-up.
2. **Fit.** Map real work to the two or three things the listing asks for: what was done, what happened. Strongest matches only; do not answer every requirement.
3. **Close (optional).** One short paragraph on how the user works, as plain fact: curiosity, finding defects, fixing the process that let one through. Allowed only when it states settled temperament and looks backward. Looking forward with unrequested work ("the first thing I'd do…") is a plan-close, banned: it reads junior, formulaic, AI-written. A letter may end on the fit paragraph; both are correct.

**Never** (beyond the voice rules in `profile.md`): quote the company's own words
(press releases, marketing, mission language); use company news as a hook (facts
must be durable); open with marketing copy ("what excites me about," "what drew me
to," "what pulled me to").

**Grounding.** Voice from the sample corpus, fit claims from the chosen base,
company facts from the listing or durable knowledge; the letter works on listing
detail alone. A letter joins the corpus as a **known-good** only if the user
approved it at every step. Canonical known-goods: the QA cover letter (ends on the
fit paragraph), the Pinterest SDET cover letter (disposition close), and the Vercel
Developer Success cover letter (forward-deployed / customer-success register,
disposition close ending on a concrete object). Calibrate against all three.

The letterhead, length, and forbidden phrases live in `profile.md` and are
enforced at render (see Implementation).

---

## 8. LinkedIn sync

Keeps the user's LinkedIn profile in step with the master résumé, under the same
grounding rule: the copy is generated from `master-resume.md`, never
hand-invented, so it cannot drift.

- **Generate.** Map the master résumé onto LinkedIn's fields (headline, About, experience descriptions) within its character limits and the voice rules. One target drives headline and About; the rest is shared.
- **Apply (optional).** Push headline, About, and experience descriptions onto the live profile through a supervised browser session. The one place the system changes something live, so it is fenced: dry-run by default, the user confirms every save, edits idempotent and verified, own profile only. Titles and dates untouched.

Automating profile edits crosses LinkedIn's terms; built for one-time, supervised,
self-owned use, risk accepted by the user.

---

## 9. Implementation

Every technical detail and commitment. The rules above don't depend on it; this
is how the current system fulfills them.

### Files

```text
master-resume.md          # real résumé superset, source of truth
resume-devdocs.md         # Dev Docs / DX base (primary)   ┐ generated from the master
resume-education.md       # Developer Education base        │ (render_resume.py --emit-base)
resume-fde.md             # Forward-Deployed Eng base       ┘
resume-qa.md              # QA / SDET base (hand-maintained)
profile.md                # user-specific: goal, positioning, targeting, résumé style, voice
linkedin-profile.md       # generated LinkedIn copy (tracked deliverable)
linkedin-profile.json     # machine-readable LinkedIn source for the driver (gitignored)
voice/                    # real letter samples, for voice matching (gitignored)
applications/             # one folder per job: listing + outputs (gitignored)
scripts/                  # tooling, grouped by area:
  resume/                 #   build_resume, render_resume, lint_resume
  letter/                 #   build_cover_letter, voice_lint
  ingest/                 #   url_ingest, batch_ingest, fetch_metacareers
  pdf/                    #   docx_to_pdf, merge_pdfs
  linkedin/               #   linkedin_export, linkedin_apply, linkedin_selectors, linkedin_browser_probe
resume-template.docx      # the Swiss/Inter template the engine renders into
SPEC.md                   # this file
CLAUDE.md                 # thin session-loaded pointer to this file
README.md                 # repo front door
```

### Environment

```bash
brew install --cask libreoffice font-inter          # PDF render + embedded font
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

`requirements.txt` is the single source for pip deps. The scripts that need one
(`build_cover_letter.py`, `render_resume.py`/`build_resume.py`, `merge_pdfs.py`,
the LinkedIn scripts) run via `.venv/bin/python`; the rest run on system `python3` (3.11+).

### Scripts

Grouped under `scripts/<area>/`; run each by its path.

**`resume/`**
- `render_resume.py --input <resume.md> --out <pdf>` — render a tailored résumé. `--target <t>` renders a base directly; `--emit-base --target <t> --out <md>` regenerates a base; `--docx-only` stops at `.docx`.
- `build_resume.py` — the Swiss/Inter OOXML engine `render_resume.py` drives (not run directly).
- `lint_resume.py <docx>` — Swiss-style résumé linter.

**`letter/`**
- `build_cover_letter.py --input <cover-letter.md> --out <docx>` — enforces the Letterhead, Length, and Forbidden phrases from `profile.md`; aborts on `[NEEDS SOURCE]`. Run via `.venv/bin/python`.
- `voice_lint.py <letter.md>` — cover-letter voice linter (checks the Forbidden phrases).

**`ingest/`**
- `url_ingest.py <URL> --no-commit` — detect source; fetch Greenhouse/Lever/Ashby via ATS JSON APIs; LinkedIn/generic emit a stub `listing.json` flagged `requires_chrome_mcp` / `requires_user_fill`.
- `batch_ingest.py <URL…>` — ingest a list; print a JSON manifest (folder, company, title, source, stub flags).
- `fetch_metacareers.py <URL>` — fetch a JS-rendered Meta careers JD via the Jina reader proxy into the listing schema.

**`pdf/`**
- `docx_to_pdf.py <docx…>` — convert many docx to PDF in one LibreOffice pass (a private profile per run; never run two soffice at once).
- `merge_pdfs.py <out.pdf> <résumé.pdf> <cover-letter.pdf>` — combine into one upload (output path first, résumé before letter).

**`linkedin/`**
- `linkedin_export.py --target <t> [--out linkedin-profile.md] [--json linkedin-profile.json]` — map `master-resume.md` onto LinkedIn fields at LinkedIn's char limits (headline 220, About 2600, exp desc 2000); warns, never truncates. Reuses `render_resume.parse_master`, so the copy can't drift.
- `linkedin_apply.py [--commit] [--yes] [--experience]` — push `linkedin-profile.json` (Headline, About, experience descriptions) onto the live profile via real Chrome (Playwright). Dry-run unless `--commit`; asks before each save unless `--yes`; idempotent; verifies after save; logs to `linkedin-runs/<ts>/`.
- `linkedin_selectors.py` — the one selector map to edit when LinkedIn's DOM shifts. `linkedin_browser_probe.py` — re-runnable launch-stability diagnostic.

### Parsing contract

`build_cover_letter.py` and `voice_lint.py` read `profile.md` and split it on
`##` headings, looking up **Letterhead**, **Length**, and **Forbidden phrases**
by exact name. Keep those three headings at `##` level with those exact names.
`master-resume.md` is parsed the same way by `render_resume.py`.

### Commands

Single listing — ingest, tailor `resume.md`, propose and approve the cover letter, then:

```bash
python3 scripts/resume/render_resume.py --input <folder>/resume.md --out <folder>/resume.pdf
.venv/bin/python scripts/letter/build_cover_letter.py --input <folder>/cover-letter.md --out <folder>/cover-letter.docx
python3 scripts/pdf/docx_to_pdf.py <folder>/cover-letter.docx
.venv/bin/python scripts/pdf/merge_pdfs.py <folder>/combined.pdf <folder>/resume.pdf <folder>/cover-letter.pdf
```

Return the path to the application folder when done, not one file.

Batch (`/batch-apply`) — `batch_ingest.py` produces a manifest; partition
tailorable vs. stub (surface stubs as "needs a browser fetch or a pasted JD");
fan out one `batch-apply-worker` per tailorable folder, concurrent, ~5 per wave,
each writing `resume.md` and a cover-letter draft; build every `.docx`, then one
`docx_to_pdf.py` pass; print a review table. The user uploads each.

Regenerate the generated bases when `master-resume.md` changes:

```bash
python3 scripts/resume/render_resume.py --emit-base --target devdocs   --out resume-devdocs.md
python3 scripts/resume/render_resume.py --emit-base --target education --out resume-education.md
python3 scripts/resume/render_resume.py --emit-base --target fde       --out resume-fde.md
```

LinkedIn sync — regenerate the copy from the master, review it, then apply under supervision:

```bash
python3 scripts/linkedin/linkedin_export.py --target education --out linkedin-profile.md --json linkedin-profile.json
python3 scripts/linkedin/linkedin_apply.py                 # dry-run: shows every change, saves nothing
python3 scripts/linkedin/linkedin_apply.py --commit --experience   # applies, confirming before each save
```

### Conventions

- **Naming:** lowercase kebab, ISO dates — `senior-dx-engineer-2026-07-01/`.
- **Branches:** `main` is always submittable. Feature work on a branch; fast-forward and push when done. Never force-push `main`.
- **Commits:** `<area>: <verb> <object>`, one logical change each; end messages with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`. Commit only when asked.
- **Git identity:** local to this repo (no `--global`), `W.S. Gong <billygong@me.com>`.
- **Gitignore:** `applications/*`, `voice/`, `.venv/`, `.DS_Store`, `linkedin-profile.json`, and the LinkedIn session artifacts (`.linkedin-chrome-profile/` holds cookies — treat as a credential; `linkedin-runs/`). To track something under an ignored path, refactor the path; do not add an exception.
- **Shell:** zsh-friendly commands only.
- **Style changes:** do not change the résumé font, accent, or template without explicit sign-off.
