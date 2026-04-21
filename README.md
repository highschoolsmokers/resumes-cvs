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
  the same letterhead as the resume. Refuses to run if
  `cover-letter.provenance.yaml` has unsourced claims.
- **`scripts/lint_resume.py`** — whole-document consistency gate
  (font, size scale, spacing on a 60-DXA baseline lattice, uniform cell
  padding). `build_resume.py` calls it and refuses to write on drift.
- **`scripts/check_provenance.py`** — pre-commit hook that blocks commits
  with unsourced claims in resume or cover-letter provenance sidecars.
- **`agents/`** — prompt files for `search-agent`, `fit-scorer`,
  `resume-tailor`, `cover-letter-writer`, `tracker-agent`,
  `reply-drafter`, `scheduler`.
- **`job-search-agent-spec.md`** — the architecture (what's being built
  and why).
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
python3 -m pip install -r requirements.txt
```

Fork + clone + rename the repo, then fill in the personal files:

1. **`bullets.yaml`** — your career accomplishment database. Start from
   the example structure; the `bullets-lookup` / `lint-bullets` scripts
   help inventory your past resumes.
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

Then:

```bash
python3 build_resume.py   # regenerate your generalized resume
```

From there, the typical flow is:

```
Listing URL
  ↓
search/run.py  (daily cron)   OR   scripts/url_ingest.py <url>
  ↓
agents/fit-scorer               → score against criteria.yaml
  ↓
agents/resume-tailor            → plan + resume.docx + provenance
  ↓
agents/cover-letter-writer      → company-facts.md + letter + provenance
  ↓
YOU review, YOU submit
  ↓
agents/tracker-agent            (every 2h) → tracker.yaml, dashboard.md
  ↓
agents/reply-drafter            → drafts in Apple Mail for recruiter Qs
agents/scheduler                → tentative Google Calendar holds
```

Read `job-search-agent-spec.md` for the full architecture and `CLAUDE.md`
for the operating playbook.

## Project layout

```
build_resume.py              resume renderer (Swiss, Inter-embedded)
build_cover_letter.py        cover letter renderer (same letterhead)
scripts/                     deterministic helpers (lint, check, ingest, …)
agents/                      prompt files for each agent
config/
  criteria.example.yaml      role targeting
  voice.example.yaml         cover-letter tone + scheduling prefs
  personal-facts.example.yaml  recruiter-reply fact base
  sites.yaml                 public job-board URLs
docs/
  resume-style-spec.md       typographic constraints
applications/_template/      skeleton for a new application folder
resume-template.docx         pristine resume template (Inter, Swiss grid)
job-search-agent-spec.md     architecture
CLAUDE.md                    operating playbook
```

## Status

Extracted from a live, in-use job search. Phase 4 (tracker + replies +
scheduling) is implemented; Phase 5 (archive + legacy migration) is
partial. Expect edges. Issues + PRs welcome.

## License

MIT. See `LICENSE`.
