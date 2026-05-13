# Job-search system — spec

Six buckets. The first three build; the last three preserve trust.

One constraint stated three ways:
- Outputs cite a source.
- State changes through the inbox, not by guessing.
- Irreversible actions belong to the human.

---

## 1 — Find: feeds → recommendation

Pull configured feeds, dedupe, score against criteria, recommend.

- **Inputs**: `config/sites.yaml`, `config/criteria.yaml`, `search/seen.db`.
- **Outputs**: `search/runs/<ts>/{listings,scored}.jsonl`, `summary.md`.
- **Driver**: `search/run.py`. **Agents**: `search-agent`, `fit-scorer` (deterministic rubric in `search/run.py`; LLM qualitative pass via `agents/fit-scorer.md` is opt-in, capped at +15).
- **Invariant**: a rerun within 24h adds zero rows; every recommendation cites the criterion that matched.

## 2 — Frame: URL → canonical record

One URL becomes one normalised listing plus a per-app folder and a branch. A `jd-analysis.md` pre-step distils the listing into must-haves / nice-to-haves / cultural signals / jargon / red flags, consumed by every downstream tailoring agent.

- **Input**: a listing URL (Greenhouse, Lever, Ashby, LinkedIn, or generic). Either entered live or drained from `queue.jsonl`.
- **Outputs**: `applications/<Co>/<role-slug>-<date>/listing.{json,md}` on branch `app/<slug>`; `applications/<…>/jd-analysis.md`.
- **Drivers**: `scripts/url_ingest.py` (auto-commits the branch via `--commit`); `agents/jd-analyzer.md` (the pre-step). LinkedIn routes through the Chrome MCP; generic URLs stub with `requires_user_fill`.
- **Async on-ramp**: `scripts/queue_add.py` appends to `queue.jsonl`; `scripts/apply_queue.py --once` drains by invoking `claude -p '/apply <url>'` in headless mode. The scheduled-tasks MCP can fire that every 30 min.
- **Invariant**: downstream stages refuse to run until the stub is filled.

## 3 — Cite: closed-universe inputs → sourced output

Every concrete claim emitted by the system traces to an id in a fixed inventory. Retrieval (vector index) narrows attention; the YAML files remain the source of truth for verbatim text and provenance lookup.

- **Inventories**:
  - `bullets.yaml` — every usable resume claim, role-tagged.
  - `voice-corpus/` — sentence rhythm for cover letters.
  - `company-facts.md` (per app) — researched facts with URLs; cached across applications at the same company (14-day TTL by default).
  - `config/personal-facts.yaml` — answers to recruiter "personal" questions.
  - `resume-template.docx` — letterhead anchor (Inter single family, #D44500).
- **Attention narrowing**: `scripts/build_index.py` builds a local `all-MiniLM-L6-v2` index over bullets + voice paragraphs into `state/embeddings.npz`. `scripts/retrieve.py --query-file <jd-analysis.md> --k 25 --source bullets` returns the focus pool the tailor consumes.
- **Seed**: `applications/_plans/<role-family>.yaml` holds the most recent successful plan per family — the next tailor seeds from it and adjusts deltas only.
- **Outputs (per app)**: `resume-plan.yaml`, `resume.docx`, `cover-letter.md`, `replies/<thread>.md` — each with a `.provenance.yaml` sidecar. `fit-report.md` only when there are gaps or unsourced claims.
- **Drivers**: `build_resume.py`, `build_cover_letter.py`. **Agents**: `resume-tailor`, `cover-letter-writer`, `reply-drafter`, `scheduler`. The tailor pair fans out in parallel from the skill.
- **Guardrail**: `scripts/check_provenance.py` runs as `.githooks/pre-commit` in `--block` mode. Unsourced output writes `[NEEDS SOURCE: …]` or `[USER TO ANSWER: …]` literally instead of guessing. One-time install: `bash scripts/install_provenance_hook.sh`.

## 4 — Render: markup → distributable

DOCX becomes PDF; the deliverables are `resume.pdf` and `cover-letter.pdf` as separate files. The `/apply` skill batches them through a single `soffice` invocation.

- **Drivers**: `scripts/docx_to_pdf.py` (headless LibreOffice, accepts multiple inputs in one batch), `scripts/merge_pdfs.py` (available but unused by `/apply`).
- **Style** enforced inline by `scripts/lint_resume.py` (called by `build_resume.py`); the pre-commit hook also runs it on any staged `resume.docx`.
- **Invariant**: Swiss typography asserted at build time. Drift — wrong family, off-grid spacing, mixed em-dash weights — fails the build.

## 5 — Watch: side channel → tracked state

The agent learns about every status change through Apple Mail, not by asking. Bullet outcomes feed back into the closed universe as a leaderboard.

- **Inputs**: Apple Mail.app (iCloud), every open `tracker.yaml`, every `resume.provenance.yaml`.
- **Outputs**: updated `tracker.yaml`, regenerated `dashboard.md` (with queue status + bullet leaderboard sections), Mail.app drafts, `[TENTATIVE]` Google Calendar events, `state/bullet_outcomes.{csv,md}`.
- **Drivers**: `scripts/sweep.py` (every 2h cron), `scripts/dashboard.py`, `scripts/bullet_outcomes.py`, `scripts/queue_status.py`. **Agent**: `tracker-agent`, routing `questions` → `reply-drafter` and `scheduling` → `scheduler`.
- **Invariant**: status transitions are promote-only; the dashboard is generated, never edited by hand; bullet outcomes are pure derivations from existing artifacts (no schema change).

## 6 — Hold: human-only side effects

Three irreversible verbs belong to the human. The agent never crosses these.

| Verb        | Where it happens                                                           |
| ----------- | -------------------------------------------------------------------------- |
| **Submit**  | Agent produces PDFs; user uploads via the portal.                          |
| **Send**    | Drafts land in Mail.app/Drafts via `make new outgoing message`; user sends. |
| **Confirm** | Calendar events stay `[TENTATIVE]` until the user says "confirmed".        |

Everything else — searching, scoring, tailoring, drafting, committing, archiving — runs unattended.
