---
description: Prep an application from a job-listing URL — ingest, tailor resume, write cover letter, merge PDFs. Does NOT submit (per CLAUDE.md §5 trust boundary).
argument-hint: "<listing-url> [--company <Name>] [--title <Role Title>]"
---

# /apply — prepare application materials from a job URL

The user invoked `/apply $ARGUMENTS`.

End-to-end pipeline: URL → normalised listing → tailored resume → company research → cover letter → combined PDF. The user reviews and applies via the portal themselves — **you do NOT submit** (CLAUDE.md §5, trust boundary #1).

## Setup

Read these before running any tool:

- `CLAUDE.md` §§2 Phase 2–3, §5 (trust boundaries), §6 (what not to do).
- `job-search-agent-spec.md` §§3.4, 3.8, 4, 5, 8.6, 8.8.
- `agents/resume-tailor.md` and `agents/cover-letter-writer.md` — the two agents you'll drive.

If any of those files is missing, stop and tell the user — the repo isn't set up for this workflow.

## Steps

### 1. Ingest the listing (auto-commits on the app branch)

Run:

```
python3 scripts/url_ingest.py $ARGUMENTS
```

The default `--commit` flag creates `app/<Company>-<role-slug>-<YYYY-MM-DD>` and commits `listing.json` + `listing.md` in one step.

Inspect the resulting `listing.json`:

- `requires_chrome_mcp: true` (LinkedIn) — use `mcp__Claude_in_Chrome__*` to fetch the JD; replace the stub fields. If the Chrome extension isn't connected, stop and ask the user to install it.
- `requires_user_fill: true` (generic) — ask the user to paste the JD text.
- Otherwise proceed.

### 2. JD analysis (shared pre-step)

Invoke `agents/jd-analyzer.md`. Writes `applications/<…>/jd-analysis.md` (~1 KB, ~5–10s) — must-haves / nice-to-haves / cultural signals / jargon / red flags. Both downstream agents consume it.

### 3. Fan out resume and cover letter in parallel

Invoke `agents/resume-tailor.md` AND `agents/cover-letter-writer.md` as **two subagents in one message**. Both read `jd-analysis.md` + `bullets.yaml` + the listing.

The resume-tailor produces:
- `resume-plan.yaml`, `resume.docx` (via `build_resume.py --plan <plan> --out <resume.docx> --no-unpacked`), `resume.provenance.yaml`.
- `fit-report.md` — **only if** there are gaps or unsourced claims; otherwise skip.

The cover-letter writer produces:
- `company-facts.md`, `cover-letter.md` (300–400 words), `cover-letter.docx`, `cover-letter.provenance.yaml`.

Guardrails: every bullet verbatim in `bullets.yaml`; no `voice.yaml → forbidden_phrases`; both provenance sidecars pass `check_provenance.py`; `lint_bullets.py` exits 0.

### 4. Render both PDFs in one LibreOffice batch

```
python3 scripts/docx_to_pdf.py applications/<…>/resume.docx applications/<…>/cover-letter.docx
```

Single `soffice` invocation produces both PDFs.

### 5. Single commit + terse handoff

```
git add applications/<…>/
git commit -m "apply: <Company> <Role>"
```

Hand off: one-line fit headline, two PDF links, gap flags only if `fit-report.md` exists, surface any `[NEEDS SOURCE:…]` that remained. Then STOP — the user submits via the portal and tells you "submitted" afterward.

## What this command does NOT do

- **Does not submit the application.** You hand the user artifacts; they upload to the portal.
- **Does not fill portal forms.** Trust boundary (CLAUDE.md §5).
- **Does not create a tracker.yaml yet.** That waits until the user confirms the application was actually submitted.
- **Does not touch `search/seen.db`.** URL ingest is a deliberate manual path (`"ingest": "manual"` in the listing record).
- **Does not run the tracker sweep.** That's the scheduled task.

## When to stop and ask

- `bullets.yaml` has no summary matching the detected `target_role_family` — ask the user whether to broaden the family, write a new summary (with their input), or skip a generic summary entirely.
- The listing would require a skill that genuinely isn't in `bullets.yaml` and matters enough that the JD calls it out as "required" — surface to the user; don't try to finesse it in the cover letter.
- Company research came back thin (fewer than three usable anchors for `company-facts.md`) — ask the user to supply a fact or two, rather than leaning on generic phrasing.
- Any provenance check fails — stop, show the errors, fix before proceeding.
