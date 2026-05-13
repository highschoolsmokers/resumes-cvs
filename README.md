# Job Search Playbook

A provenance-enforced pipeline for running a job search with a coding agent
(Claude Code). Turns a listing URL into a tailored resume + cover letter
where every concrete claim traces back to a source file — no hallucinated
bullets, no invented company facts, no guessed personal details.

## What's in the box

- **`build_resume.py`** — renders a Swiss-typography resume from a plan
  YAML plus your `bullets.yaml`. Embeds Inter into the DOCX so the PDF
  renders identically across machines.
- **`build_cover_letter.py`** — renders a 300–400-word cover letter with
  the same Inter / #D44500 letterhead as the resume. Refuses to render
  if `cover-letter.provenance.yaml` has unsourced claims.
- **`agents/`** — prompt files: `search-agent`, `fit-scorer`,
  `jd-analyzer`, `resume-tailor`, `cover-letter-writer`, `tracker-agent`,
  `reply-drafter`, `scheduler`. (Archiver is in the spec; not yet implemented.)
- **`scripts/`** — 18 deterministic drivers. Highlights:
  - `url_ingest.py` — URL → listing.json + auto-committed branch.
  - `docx_to_pdf.py` — headless LibreOffice (batch input supported).
  - `check_provenance.py` — provenance gate; wired into the pre-commit hook.
  - `lint_resume.py` / `lint_bullets.py` — whole-document Swiss consistency
    + bullets.yaml schema lint. Both called from the pre-commit hook.
  - `build_index.py` / `retrieve.py` — local `sentence-transformers`
    semantic index over bullets + voice-corpus. Top-K narrows the tailor's
    bullet pool.
  - `queue_add.py` / `apply_queue.py` / `queue_status.py` — async apply
    queue, drained every 30 min via `claude -p '/apply <url>'`.
  - `bullet_outcomes.py` — joins provenance × tracker; surfaces a
    leaderboard section in `dashboard.md`.
  - `sweep.py` — Apple Mail tracker sweep.
- **`.githooks/pre-commit`** — provenance gate that blocks commits with
  unsourced claims in any staged sidecar. Install once via
  `bash scripts/install_provenance_hook.sh`.
- **`job-search-agent-spec.md`** — the architecture (what's being built
  and why); see also `docs/spec.md` for the brief six-bucket summary.
- **`CLAUDE.md`** — the operating playbook (how to build and run it).

## Design principles

1. **Every concrete claim is cited.** Resume bullets cite `bullets.yaml`;
   company facts in cover letters cite `company-facts.md` with a URL;
   recruiter-reply answers cite `config/personal-facts.yaml`.
   Unsourced → build fails → commit blocked.
2. **Swiss typography, enforced.** Inter single family, 25/75 column
   grid, baseline rhythm on a 60 DXA lattice, uniform cell padding, no
   inline em-dashes mixing weights. `scripts/lint_resume.py` fails the
   build on any drift.
3. **The agent does not submit.** Three manual checkpoints:
   - Submitting a portal application (agent produces the PDFs; you upload).
   - Sending email (agent drafts in Apple Mail; you send).
   - Confirming a calendar event (agent holds tentative; you confirm).

## Getting started

Prerequisites (macOS — adapt for Linux):

```bash
brew install --cask libreoffice font-inter
brew install gh
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
bash scripts/install_provenance_hook.sh   # wire .githooks/pre-commit
```

The last line is **required** — without it, the hallucination guard
(`scripts/check_provenance.py --staged --block`) isn't enforced on commit.

Fork + clone + rename the repo, then fill in the personal files:

1. **`bullets.yaml`** — your career accomplishment database. Start from
   the example structure; the `bullets_lookup.py` / `lint_bullets.py`
   scripts help inventory your past resumes.
2. **`config/criteria.yaml`** — role families, title keywords, comp
   floor, company excludes. Copy from `config/criteria.example.yaml`.
3. **`config/voice.yaml`** — cover letter tone knobs + scheduling
   preferences. Copy from `config/voice.example.yaml`.
4. **`config/personal-facts.yaml`** — visa status, comp expectations,
   start date, relocation willingness, etc. Copy from
   `config/personal-facts.example.yaml`. **Gitignored** by default — do
   not commit.
5. **`resume-template.docx`** — swap in your own contact block (name,
   city, email, website, github).
6. Once `bullets.yaml` and `voice-corpus/` are populated, build the
   semantic retrieval index: `python3 scripts/build_index.py`.

Then:

```bash
python3 build_resume.py   # regenerate your generalized resume
```

From there, the typical flow is:

```
Listing URL
  ↓
search/run.py  (daily cron)   OR   scripts/url_ingest.py <url>
                                   OR   scripts/queue_add.py <url>  (async)
  ↓
agents/fit-scorer               → score against criteria.yaml
  ↓
agents/jd-analyzer              → jd-analysis.md (must-haves, etc.)
  ↓
agents/resume-tailor       ║    → plan + resume.docx + provenance
agents/cover-letter-writer ║    → company-facts.md + letter + provenance
                           (parallel fan-out)
  ↓
.githooks/pre-commit            → provenance gate; commit blocks if unsourced
  ↓
YOU review, YOU submit
  ↓
agents/tracker-agent            (every 2h) → tracker.yaml, dashboard.md
  ↓
agents/reply-drafter            → drafts in Apple Mail for recruiter Qs
agents/scheduler                → tentative Google Calendar holds
```

Read `job-search-agent-spec.md` for the full architecture, `docs/spec.md`
for the brief six-bucket summary, and `CLAUDE.md` for the operating
playbook.

## Project layout

```
build_resume.py              resume renderer (Swiss, Inter-embedded)
build_cover_letter.py        cover letter renderer (same letterhead)
.githooks/pre-commit         provenance gate (install via script)
scripts/                     18 deterministic helpers
  url_ingest.py              URL → listing + branch
  build_index.py / retrieve.py   local semantic index
  queue_add.py / apply_queue.py / queue_status.py   async apply queue
  bullet_outcomes.py         provenance × tracker → leaderboard
  sweep.py / dashboard.py    tracker sweep + dashboard regen
  check_provenance.py / lint_bullets.py / lint_resume.py   gates
  docx_to_pdf.py / merge_pdfs.py / extract_bullets.py / …
  install_provenance_hook.sh / install_apply_skill.sh / …
agents/                      prompt files (search-agent, fit-scorer,
                             jd-analyzer, resume-tailor, cover-letter-writer,
                             tracker-agent, reply-drafter, scheduler)
config/
  criteria.example.yaml      role targeting
  voice.example.yaml         cover-letter tone + scheduling prefs
  personal-facts.example.yaml  recruiter-reply fact base
  sites.yaml                 public job-board URLs
docs/
  spec.md                    brief six-bucket spec
  resume-style-spec.md       typographic constraints
search/                      top-of-funnel driver + runs (runs/ gitignored)
state/                       derived semantic index + bullet-outcomes (gitignored)
applications/_template/      skeleton for a new application folder
resume-template.docx         pristine resume template (Inter, Swiss grid)
job-search-agent-spec.md     architecture
CLAUDE.md                    operating playbook
```

## Status

Extracted from a live, in-use job search. Phases 1–4 of the original spec
plus Phases 6–12 of post-spec sharpening (orchestration, jd-analyzer,
caches, semantic retrieval, apply queue, bullet outcomes, pre-commit
provenance gate) are shipped. Phase 5 (`archiver` agent) is deferred —
archiving is currently a manual `git mv`. Expect edges. Issues + PRs welcome.

## License

MIT. See `LICENSE`.
