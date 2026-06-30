# Job Search Playbook

Give it a job listing URL. Get back a tailored resume PDF, a cover letter
PDF, and a tracker that watches your inbox for replies. Every claim on the
page traces to a file you control — no hallucinated bullets, no invented
company facts, no guessed personal details. You still submit the
application, send the emails, and confirm the meetings.

## Make a tailored resume + cover letter

Once the repo is set up (see below), the day-to-day flow is one command
plus a review pass:

```bash
# 1. Hand the agent a listing URL.
python3 scripts/url_ingest.py "https://boards.greenhouse.io/acme/jobs/12345"
```

This normalises the listing, creates
`applications/<Company>/<role-slug>-<YYYY-MM-DD>/`, and auto-commits
`listing.json` + `listing.md` on a new `app/<…>` branch.

```bash
# 2. In Claude Code, run the /apply skill on the same URL.
/apply https://boards.greenhouse.io/acme/jobs/12345
```

`/apply` orchestrates the rest:

1. Analyses the JD (must-haves, nice-to-haves, cultural signals, red flags).
2. Fans out two agents in parallel:
   - **resume-tailor** picks bullets from `bullets.yaml`, writes
     `resume-plan.yaml`, renders `resume.docx` → `resume.pdf`, and emits a
     `resume.provenance.yaml` sidecar mapping every bullet to its source id.
   - **cover-letter-writer** researches the company, writes
     `company-facts.md` (every claim with a URL), drafts a 300–400-word
     letter, renders `cover-letter.pdf`, and emits
     `cover-letter.provenance.yaml`.
3. Commits the app folder. The pre-commit hook
   (`scripts/check_provenance.py --staged --block`) refuses the commit if
   any concrete claim in the resume or letter isn't sourced.

```bash
# 3. Review and submit.
open applications/Acme/forward-deployed-engineer-2026-05-14/resume.pdf
open applications/Acme/forward-deployed-engineer-2026-05-14/cover-letter.pdf
```

Edit by hand if you want; rerun `/apply` to regenerate; merge the branch
into `main` when you're happy. **You** upload the PDFs to the portal — the
agent never submits.

### Other on-ramps

- **Bulk:** `search/run.py` (daily cron) pulls Greenhouse / Lever / Ashby
  feeds, dedupes against `search/seen.db`, scores against
  `config/criteria.yaml`, writes `search/runs/<ts>/summary.md`.
- **Async queue:** `scripts/queue_add.py <url>` appends to `queue.jsonl`;
  `scripts/apply_queue.py --once` drains by invoking
  `claude -p '/apply <url>'` in headless mode. Wire it to the
  scheduled-tasks MCP to drain every 30 min.
- **LinkedIn:** `url_ingest.py` stubs the listing with
  `requires_chrome_mcp: true`; `/apply` fills it via the Chrome MCP.

## After you've applied

- **Tracker.** `scripts/sweep.py` runs every 2h via `tracker-agent`,
  reads Apple Mail (iCloud), and promotes statuses (`applied` → `screen` →
  `onsite` → `offer` / `rejected`) by matching message ids to open
  `tracker.yaml` files. `dashboard.md` regenerates from all open trackers
  with a bullet-outcome leaderboard at the bottom.
- **Recruiter replies.** Question threads route to `reply-drafter`, which
  drafts a reply citing `config/personal-facts.yaml` and stages it in
  Apple Mail.app's Drafts. You open Mail and send.
- **Scheduling.** Scheduling threads route to `scheduler`, which proposes
  up to three slots from `config/voice.yaml → scheduling_preferences`,
  holds a `[TENTATIVE]` Google Calendar event, and stages a reply draft.
  You confirm the slot; you mark the event confirmed.

## What's in the repo

- **`scripts/build_resume.py`** — renders a Swiss-typography resume from
  a plan YAML plus `bullets.yaml`. Embeds Inter into the DOCX so the PDF
  renders identically across machines.
- **`scripts/build_cover_letter.py`** — renders a cover letter with the
  same Inter / #D44500 letterhead. Refuses to render if
  `cover-letter.provenance.yaml` has unsourced claims.
- **`agents/`** — prompt files: `search-agent`, `fit-scorer`,
  `jd-analyzer`, `resume-tailor`, `cover-letter-writer`, `tracker-agent`,
  `reply-drafter`, `scheduler`. (Archiver is specced but not yet
  implemented — archiving is a manual `git mv` for now.)
- **`scripts/`** — 18 deterministic drivers. Highlights:
  - `url_ingest.py` — URL → listing.json + auto-committed branch.
  - `docx_to_pdf.py` — headless LibreOffice (batch input supported).
  - `check_provenance.py` — provenance gate; wired into pre-commit.
  - `lint_resume.py` / `lint_bullets.py` — Swiss consistency check on
    the whole document; bullets.yaml schema lint. Both pre-commit-wired.
  - `build_index.py` / `retrieve.py` — local `sentence-transformers`
    semantic index over bullets + voice-corpus. Top-K narrows the
    tailor's bullet pool.
  - `queue_add.py` / `apply_queue.py` / `queue_status.py` — async apply
    queue.
  - `bullet_outcomes.py` — joins provenance × tracker; surfaces a
    leaderboard section in `dashboard.md`.
  - `sweep.py` — Apple Mail tracker sweep.
- **`.githooks/pre-commit`** — provenance gate that blocks commits with
  unsourced claims in any staged sidecar. Install once via
  `bash scripts/install_provenance_hook.sh`.
- **`job-search-agent-spec.md`** — architecture (what's being built and
  why); `docs/spec.md` for the brief six-bucket summary.
- **`CLAUDE.md`** — operating playbook (how to build and run it).

## Three rules the agent never breaks

1. **Every concrete claim is cited.** Resume bullets cite `bullets.yaml`;
   company facts in cover letters cite `company-facts.md` with a URL;
   recruiter-reply answers cite `config/personal-facts.yaml`. Unsourced →
   build fails → commit blocked.
2. **Swiss typography, enforced.** Inter single family, 25/75 column
   grid, baseline rhythm on a 60 DXA lattice, uniform cell padding, no
   inline em-dashes mixing weights. `scripts/lint_resume.py` fails the
   build on any drift.
3. **Three verbs belong to you.** Submitting a portal application,
   sending an email, and confirming a calendar event are always manual.
   The agent stages drafts and tentatives; you cross the line.

## Setting it up

Prerequisites (macOS — adapt for Linux):

```bash
brew install --cask libreoffice font-inter
brew install gh
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
bash scripts/install_provenance_hook.sh   # wire .githooks/pre-commit
```

The last line is **required** — without it, the hallucination guard
isn't enforced on commit.

Fork + clone + rename the repo, then fill in the personal files:

1. **`bullets.yaml`** — your career accomplishment database. Start from
   the example structure; `bullets_lookup.py` / `lint_bullets.py` help
   inventory past resumes.
2. **`config/criteria.yaml`** — role families, title keywords, comp
   floor, company excludes. Copy from `config/criteria.example.yaml`.
3. **`config/voice.yaml`** — cover-letter tone + scheduling preferences.
   Copy from `config/voice.example.yaml`.
4. **`config/personal-facts.yaml`** — visa status, comp expectations,
   start date, relocation willingness. Copy from
   `config/personal-facts.example.yaml`. **Gitignored** by default — do
   not commit.
5. **`resume-template.docx`** — swap in your own contact block.
6. Build the semantic retrieval index once bullets + voice-corpus are
   populated: `python3 scripts/build_index.py`.

Sanity check:

```bash
python3 scripts/build_resume.py   # regenerates your generalised resume
```

Read `CLAUDE.md` for the operating playbook, `docs/spec.md` for the brief
six-bucket spec, and `job-search-agent-spec.md` for the full architecture.

## Project layout

```
scripts/build_resume.py              resume renderer (Swiss, Inter-embedded)
scripts/build_cover_letter.py        cover letter renderer (same letterhead)
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
