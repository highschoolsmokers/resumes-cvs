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
- **Driver**: `search/run.py`. **Agents**: `search-agent`, `fit-scorer`.
- **Invariant**: a rerun within 24h adds zero rows; every recommendation cites the criterion that matched.

## 2 — Frame: URL → canonical record

One URL becomes one normalised listing plus a per-app folder and a branch.

- **Input**: a listing URL (Greenhouse, Lever, Ashby, LinkedIn, or generic).
- **Output**: `applications/<Co>/<role-slug>-<date>/listing.{json,md}` on branch `app/<slug>`.
- **Driver**: `scripts/url_ingest.py`. LinkedIn routes through the Chrome MCP; generic URLs stub with `requires_user_fill`.
- **Invariant**: downstream stages refuse to run until the stub is filled.

## 3 — Cite: closed-universe inputs → sourced output

Every concrete claim emitted by the system traces to an id in a fixed inventory.

- **Inventories**:
  - `bullets.yaml` — every usable resume claim, role-tagged.
  - `voice-corpus/` — sentence rhythm for cover letters.
  - `company-facts.md` (per app) — researched facts with URLs.
  - `config/personal-facts.yaml` — answers to recruiter "personal" questions.
  - `resume-template.docx` — letterhead anchor.
- **Outputs (per app)**: `resume-plan.yaml`, `resume.docx`, `cover-letter.md`, `replies/<thread>.md` — each with a `.provenance.yaml` sidecar.
- **Drivers**: `build_resume.py`, `build_cover_letter.py`. **Agents**: `resume-tailor`, `cover-letter-writer`, `reply-drafter`, `scheduler`.
- **Guardrail**: `scripts/check_provenance.py` runs as a pre-commit hook in `--block`. Unsourced output writes `[NEEDS SOURCE: …]` or `[USER TO ANSWER: …]` literally instead of guessing.

## 4 — Render: markup → distributable

DOCX becomes PDF; the per-app deliverable is `combined.pdf`.

- **Drivers**: `scripts/docx_to_pdf.py` (headless LibreOffice), `scripts/merge_pdfs.py` (resume first, cover letter second).
- **Style** enforced inline by `scripts/lint_resume.py` (called by `build_resume.py`).
- **Invariant**: Swiss typography asserted at build time. Drift — wrong family, off-grid spacing, mixed em-dash weights — fails the build.

## 5 — Watch: side channel → tracked state

The agent learns about every status change through Apple Mail, not by asking.

- **Inputs**: Apple Mail.app (iCloud), every open `tracker.yaml`.
- **Outputs**: updated `tracker.yaml`, regenerated `dashboard.md`, Mail.app drafts, `[TENTATIVE]` Google Calendar events.
- **Driver**: `scripts/sweep.py` (every 2h cron). **Agent**: `tracker-agent`, routing `questions` → `reply-drafter` and `scheduling` → `scheduler`.
- **Invariant**: status transitions are promote-only; the dashboard is generated, never edited by hand.

## 6 — Hold: human-only side effects

Three irreversible verbs belong to the human. The agent never crosses these.

| Verb        | Where it happens                                                           |
| ----------- | -------------------------------------------------------------------------- |
| **Submit**  | Agent produces PDFs; user uploads via the portal.                          |
| **Send**    | Drafts land in Mail.app/Drafts via `make new outgoing message`; user sends. |
| **Confirm** | Calendar events stay `[TENTATIVE]` until the user says "confirmed".        |

Everything else — searching, scoring, tailoring, drafting, committing, archiving — runs unattended.
