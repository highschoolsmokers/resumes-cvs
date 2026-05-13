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

### 1. Ingest the listing

Run:

```
python3 scripts/url_ingest.py <URL> [--company "<Name>"] [--title "<Role Title>"]
```

This creates `applications/<Company>/<role-slug>-<YYYY-MM-DD>/listing.json` + `listing.md`, and prints the git commands to create the application branch (it cannot touch `.git/` from inside the sandbox).

Inspect the resulting `listing.json` before continuing:

- If `requires_chrome_mcp: true` (LinkedIn URLs) — use `mcp__Claude_in_Chrome__*` to fetch the JD body, then replace the stub listing fields with the real ones. If the Chrome extension isn't connected, stop and ask the user to install it.
- If `requires_user_fill: true` (generic URLs where no adapter matched) — ask the user to paste the JD text, then populate `listing.md` / `listing.json` accordingly.
- Otherwise proceed.

### 2. Create the application branch on the user's machine

`url_ingest.py` printed the git commands. Surface them to the user verbatim so they can run them locally (the sandbox can't write to `.git/`):

```
git checkout -b app/<Company>-<role-slug>-<YYYY-MM-DD>
git add applications/<Company>/<role-slug>-<YYYY-MM-DD>/
git commit -m "url-ingest: <Company> <Role Title> listing"
```

Do not proceed further until the user confirms they're on the app branch (or says "I'll do the git part later, keep going").

### 3. Tailor the resume

Invoke `agents/resume-tailor.md`. It:

1. Reads `bullets.yaml` (closed universe) and the listing.
2. Writes `resume-plan.yaml` with `target_role_family`, `summary_id`, `skill_order`, `bullets_by_role`, `picked_because`.
3. Runs `build_resume.py --plan <plan> --out <resume.docx>`.
4. Runs `scripts/docx_to_pdf.py` to produce `resume.pdf`.
5. Writes `resume.provenance.yaml` with one entry per bullet / skill / summary sentence and `unsourced_claims: []`.
6. Writes `fit-report.md` naming every gap explicitly (no glossing over missing skills).

Guardrails (hard fails — re-plan, don't paper over):

- Every bullet on the rendered resume must appear verbatim in `bullets.yaml`. If a gap would require a bullet you don't have, leave it out — never invent.
- `scripts/check_provenance.py applications/<…>/resume.provenance.yaml --block` must exit 0.
- `scripts/lint_bullets.py` must exit 0 on the committed `bullets.yaml`.

### 4. Write the cover letter

Invoke `agents/cover-letter-writer.md`. It runs a research pass FIRST (homepage / products / customers / 6mo of blog) and writes `company-facts.md` with anchor-tagged sections. Every concrete noun in the letter body must cite an anchor.

Outputs in the application folder:

- `company-facts.md` — research artefact.
- `cover-letter.md` — markdown source.
- `cover-letter.docx` via `build_cover_letter.py`, then `cover-letter.pdf` via `scripts/docx_to_pdf.py`.
- `cover-letter.provenance.yaml` — every concrete claim sourced; `unsourced_claims: []`.

Length target: 300–400 words. Hard fail > 500. No `config/voice.yaml → forbidden_phrases`.

### 5. Hand off to the user

Present `resume.pdf` and `cover-letter.pdf` as separate file links (using `computer://` links to the workspace folder) — do NOT merge them. Include a short summary:

- Title + company + role family classification.
- Three-line fit summary pulled from `fit-report.md`.
- Any `[NEEDS SOURCE:…]` placeholders left in the plan (should be zero for ship-ready output; surface if not).
- Any gaps flagged in `fit-report.md` that the user should decide whether to address.
- The git commit commands for `resume*`, `company-facts.md`, and `cover-letter*` — per `CLAUDE.md §1.2` one logical unit per commit, which for this flow typically means:

  ```
  resume-tailor: build resume.docx + plan + provenance for <Company> <Role>
  cover-letter-writer: draft cover letter + company-facts.md for <Company> <Role>
  ```

Then STOP. The user reviews the two PDFs, decides whether to submit, and tells you "submitted" afterward — at which point you'll lay down a `tracker.yaml` with `status: applied` and the tracker-agent takes over from there.

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
