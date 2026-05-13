---
name: apply
description: "Prep a job application from a listing URL — ingest, tailor resume, write cover letter, merge PDFs. Triggers on requests like 'apply to <url>', 'prep this job', 'tailor my resume for <url>'. Does NOT submit the application (per CLAUDE.md §5 trust boundary — the user submits via the portal themselves)."
---

# apply — prepare application materials from a job URL

End-to-end pipeline: URL → normalised listing → tailored resume → company research → cover letter → combined PDF. The user reviews and applies via the portal themselves — **never submit, never fill portal forms** (CLAUDE.md §5, trust boundary #1).

The URL (and any optional `--company "Name"` / `--title "Role Title"` flags) will be in the user's message. If the user did not supply a URL, ask for one before doing anything.

## Setup

Read these before running any tool:

- `CLAUDE.md` §§2 Phase 2–3, §5 (trust boundaries), §6 (what not to do).
- `job-search-agent-spec.md` §§3.4, 3.8, 4, 5, 8.6, 8.8.
- `agents/resume-tailor.md` and `agents/cover-letter-writer.md` — the two agents you'll drive.

If any of those files is missing, stop and tell the user — the repo isn't set up for this workflow.

## Steps

### 1. Ingest the listing (auto-commits the listing on the app branch)

Run:

```
python3 scripts/url_ingest.py <URL> [--company "<Name>"] [--title "<Role Title>"]
```

The default `--commit` flag creates the `app/<Company>-<role-slug>-<YYYY-MM-DD>` branch and commits `listing.json` + `listing.md` in one step. (Pass `--no-commit` only if you're in a sandbox without a writable `.git/`.)

Inspect the resulting `listing.json` before continuing:

- `requires_chrome_mcp: true` (LinkedIn) — use `mcp__Claude_in_Chrome__*` to fetch the JD body, then replace the stub listing fields. If the Chrome extension isn't connected, stop and ask the user to install it.
- `requires_user_fill: true` (generic, no adapter) — ask the user to paste the JD text, then populate `listing.md` / `listing.json`.
- Otherwise proceed.

### 2. JD analysis (shared pre-step)

Invoke `agents/jd-analyzer.md`. It reads `listing.json` + `listing.md` and writes `applications/<…>/jd-analysis.md` with must-haves / nice-to-haves / cultural signals / jargon / red flags. Tiny output (~1 KB), ~5–10 seconds. Both downstream agents consume it so they don't each re-derive the same signals.

### 3. Fan out resume and cover letter in parallel

Invoke `agents/resume-tailor.md` AND `agents/cover-letter-writer.md` as **two subagents in one message** (single Agent tool call with both invocations). Both read `jd-analysis.md` + `bullets.yaml` + the listing. The cover-letter agent runs its own research pass; neither agent waits on the other.

The resume-tailor produces, in the application folder:
- `resume-plan.yaml` — `target_role_family`, `summary_id`, `skill_order`, `bullets_by_role`, `picked_because`.
- `resume.docx` via `build_resume.py --plan <plan> --out <resume.docx> --no-unpacked` (skip the audit sibling during /apply for speed).
- `resume.provenance.yaml` — `unsourced_claims: []`.
- `fit-report.md` — **only if** there are gaps to flag or unsourced claims. If everything resolves cleanly, skip the file.

The cover-letter writer produces:
- `company-facts.md` — research artefact with anchor-tagged facts.
- `cover-letter.md` — 300–400 words, three paragraphs.
- `cover-letter.docx` via `build_cover_letter.py`.
- `cover-letter.provenance.yaml` — `unsourced_claims: []`.

Guardrails (hard fails — re-plan, don't paper over):

- Every bullet on the resume must appear verbatim in `bullets.yaml`. Gap → leave it out; never invent.
- No `config/voice.yaml → forbidden_phrases` in the cover letter.
- `scripts/check_provenance.py` must exit 0 against both sidecars.
- `scripts/lint_bullets.py` must exit 0 on `bullets.yaml`.

### 4. Render both PDFs in one LibreOffice batch

Run:

```
python3 scripts/docx_to_pdf.py applications/<…>/resume.docx applications/<…>/cover-letter.docx
```

A single `soffice` invocation produces both PDFs — saves the ~3s cold-start cost of running it twice.

### 5. Single commit and hand off

One commit covering the listing + resume + cover-letter artefacts:

```
git add applications/<…>/
git commit -m "apply: <Company> <Role>"
```

Present `resume.pdf` and `cover-letter.pdf` as separate file links. Keep the handoff terse:
- One-line fit headline (role + family + the strongest match).
- Links to the two PDFs.
- If `fit-report.md` exists, flag the gaps — otherwise skip.
- If any `[NEEDS SOURCE:…]` placeholder remains, surface it (should be zero for ship-ready output).

Then STOP. The user reviews and submits via the portal; they'll tell you "submitted" afterward — at which point you'll lay down a `tracker.yaml` and the tracker-agent takes over.

## What this skill does NOT do

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
