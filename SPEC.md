# SPEC — Job Search System

Single source of truth for the generic system. User-specific inputs (goal,
positioning, targeting, résumé style, voice, channel) live in `profile.md`;
source material in `master-resume.md` and `voice/`. Sections 1–8 are the rules;
section 9 is the implementation. Read this before operating.

---

## 1. What the system does

Input: job descriptions, plus the user's source material — `master-resume.md`, the
bases derived from it, the `voice/` letter corpus, and `profile.md`.

Output per JD: a résumé tailored from the matching base (§4); a cover letter the
user writes, the system supplying facts, structure, and a draft; on request, a
referral message. Nothing invented, nothing auto-submitted (§3).

Truthful limitations are positioned as credentials, not hidden or apologized for:
a gap, a career change, a non-traditional path, stated plainly (reframes in
`profile.md`). Success is responses, not documents: tailoring is fast so the user
applies at volume, and positioning and channel outweigh document polish.

The system also keeps the user's LinkedIn profile in step with the master résumé (§8).

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

- **Plain text until render.** Artifacts stay editable text until the final PDF step.
- **Grounded, not invented.** Every claim traces to real material; anything unsourced is `[NEEDS SOURCE]`, never fabricated (§3).
- **Tailor by reuse.** Start from the matching base and tune to the listing (§4); never rewrite from scratch.
- **Voice by example.** Calibrate the cover letter on the letter samples, not on a list of banned phrases (§7).

Batch or single listing, the same rules hold (§9).

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
3. **Close (optional).** One short paragraph on how the user works, as plain fact. Allowed only when it states a settled temperament and looks backward. A forward-looking plan-close, proposing unrequested work, is banned: it reads junior and formulaic. A letter may instead end on the fit paragraph; both are correct.

**Never** (beyond the voice rules in `profile.md`): quote the company's own words
(marketing, mission, press); use time-sensitive company news as a hook, since
facts must stay durable; open with a marketing-copy warmup. The specific opener
phrases are enforced literally in `profile.md`.

**Grounding.** Voice from the sample corpus, fit claims from the chosen base,
company facts from the listing or durable knowledge; the letter works on listing
detail alone.

To write a letter: classify its **register** (`profile.md` → Cover-letter
registers); shortlist that register's known-goods with `voice_index.py --register
<key>`; calibrate voice and structure on the nearest opener/close variant, and
against the **Trained criteria** below.

A letter joins the corpus as a **known-good** only if the user approved it at
every step; it is saved with frontmatter tagging its register, opener, and close.
Canonizing is also when the criteria train: score the new letter against the
Trained criteria; when it (or a bad example) teaches something they do not yet
hold, propose the change, get approval, then edit them below and commit it — one
commit per change, naming the sample. A criteria edit is always committed; that
commit history is the training log.

The letterhead, length, and forbidden phrases live in `profile.md` and are
enforced at render (see Implementation).

### Trained criteria

The judgment layer between `profile.md`'s hard rules (mechanically enforced by
`voice_lint.py`) and the raw `voice/` samples (routed by `voice_index.py`). Each
criterion cites the sample that trained it. User-approved; every change is one
commit naming its source example (`rubric: <change> (from <sample-id>)`).

**Global — every letter**
- Strongest matches only. Map the two or three real overlaps; let honest gaps stand rather than paper over them. [everlaw]
- The opener earns its place: state what the candidate is and the strongest proof, or the two spans that make the fit — never a thesis or warm-up. [adobe, vercel]
- Offer no claim the candidate can't stand behind: a dated, past-tense-only skill is left out, not implied current, against a current-proficiency ask. [adobe]
- Every clause is a fact; nothing explains its own relevance to the reader.
- Fit maps real work to the listing's actual asks, in the candidate's words.

**Per register**
- **qa-sdet** — opener leads with the QA span, or fuses QA + AI-verification (both-halves) for AI-augmented roles; close is ends-on-fit or a disposition about how things break / test-signal quality. [qa, pinterest, adobe]
- **fde-customer-success / fde-internal-tooling** — "I am a…" opener leading with production work on the target stack; disposition close ending on a concrete object. [vercel, everlaw]
- **docs-dx** — opener leads with the docs identity and the Slack docs; fit names the doc artifacts plus the Anthropic-stack tools. [dev-docs, salesforce]
- **dev-education** — Developer Advocate/educator calibrated on docs-dx: docs-identity opener plus the Slack platform docs; fit maps the advocacy asks (own the docs, guide the community through API changes) to the Slack docs, DevRel partnering, and published open-source work; let the events/hackathon and social-channel DevRel gap stand, never claim it. [notion-developer-advocate]

**Anti-patterns** (shapes; `profile.md` enforces the exact phrases)
- Plan-close — forward-looking unrequested work ("the first thing I'd do…").
- Fronted "What has [verb] me…" pseudo-cleft — announces a disposition instead of stating it. [retired 2026-07-03]
- Windups ("Now I", "Lately"); marketing-copy openers ("what excites me about").

Prune as it trains: merge a covered criterion, cut one that never fires (also a
commit). Keep it shorter than the corpus it generalizes.

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
resume-editorial.md       # Editorial / Standards base (hand-maintained)
profile.md                # user-specific: goal, positioning, targeting, résumé style, voice, cover-letter registers
linkedin-profile.md       # generated LinkedIn copy (tracked deliverable)
linkedin-profile.json     # machine-readable LinkedIn source for the driver (gitignored)
voice/                    # real letter samples, for voice matching (gitignored)
applications/             # one folder per job: listing + outputs (gitignored)
scripts/                  # tooling, grouped by area:
  resume/                 #   build_resume, render_resume, lint_resume
  letter/                 #   build_cover_letter, voice_lint, voice_index
  ingest/                 #   url_ingest, batch_ingest, fetch_metacareers
  pdf/                    #   docx_to_pdf, merge_pdfs
  linkedin/               #   linkedin_export, linkedin_apply, linkedin_selectors, linkedin_browser_probe
resume-template.docx      # the Swiss/Inter template the engine renders into
SPEC.md                   # this file
CLAUDE.md                 # thin session-loaded pointer to this file
README.md                 # repo front door
plugin/                   # vendored job-search Cowork plugin (canonical source; installed copy is built from it)
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
- `voice_index.py --register <key> | --list | --lint` — route a letter to its calibration samples from `voice/` frontmatter; validate the tags against `profile.md`'s register set. System `python3`.

**`ingest/`**
- `url_ingest.py <URL> --no-commit` — detect source; fetch Greenhouse/Lever/Ashby via ATS JSON APIs; LinkedIn/generic emit a stub `listing.json` flagged `requires_chrome_mcp` / `requires_user_fill`. Every stub carries a `fetch_recipe` block (from the registry below) and the printed next-steps name the working method.
- `fetch_recipes.py` / `fetch_recipes.json` — **domain → fetch-recipe registry ("training fetches").** Keyed by hostname suffix; each recipe records the method that works for a JS-rendered / bot-walled site (`ats_json` / `json_endpoint` / `dedicated_script` / `curl_browser_ua` / `reader_proxy` / `chrome_mcp` / `user_fill`) plus the exact command and extraction hints, so the *next* listing from that domain skips the trial GETs. `fetch_recipes.py <URL>` prints the recipe (exit 3 = unknown domain, falls back to the proxy-first default); `fetch_recipes.py record --domain … --method … --note …` trains a newly-solved domain; `--list` dumps all. `url_ingest` and `batch_ingest` consult it automatically for stubs.
- `batch_ingest.py <URL…>` — ingest a list; print a JSON manifest (folder, company, title, source, stub flags, `fetch_recipe`).
- `fetch_metacareers.py <URL>` — fetch a JS-rendered Meta careers JD via the Jina reader proxy into the listing schema (the `metacareers.com` recipe points here).

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
- **Commits:** `<area>: <verb> <object>`, one logical change each; end messages with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`. Commit only when asked — except a §7 Trained-criteria edit, which is committed as part of the change that made it (`rubric: <change> (from <sample-id>)`).
- **Git identity:** local to this repo (no `--global`), `W.S. Gong <billygong@me.com>`.
- **Gitignore:** `applications/*`, `voice/`, `.venv/`, `.DS_Store`, `linkedin-profile.json`, and the LinkedIn session artifacts (`.linkedin-chrome-profile/` holds cookies — treat as a credential; `linkedin-runs/`). To track something under an ignored path, refactor the path; do not add an exception.
- **Shell:** zsh-friendly commands only.
- **Style changes:** do not change the résumé font, accent, or template without explicit sign-off.
