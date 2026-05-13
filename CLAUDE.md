# CLAUDE.md — Job Search Repo Build Playbook

**Audience:** Claude Code (or any coding agent) working in the `Resumes/` repo.
**Purpose:** How to build, operate, and extend the job-search agent system.
**Canonical spec:** `job-search-agent-spec.md`. Read it first. This file is the execution plan; the spec is the source of truth for *what* to build.

---

## 0. Start-of-session checklist

Before touching anything, in this order:

1. Read `job-search-agent-spec.md` end-to-end. Every design decision routes back to it.
2. Read `docs/resume-style-spec.md` — non-negotiable style constraints for the resume. (Cowork sessions will also see the same content auto-loaded from `/.auto-memory/resume_style_spec.md`; local Claude Code sessions see only the in-repo copy.)
3. `git status` and `git log --oneline -20` — know where the repo is before making changes.
4. Check the current phase (see §2) by looking at which directories exist: `config/`, `search/`, `voice-corpus/`, `applications/`, `archive/`. Absent directories are work not yet done.
5. Confirm the user is looped in on whatever change you're about to make if it crosses the trust boundary in §5.

## 1. Repo conventions

These are enforced rules, not suggestions. Violations should be caught in review.

### 1.1 Naming

- Files and folders: lowercase kebab, ISO dates where relevant — `developer-advocate-sf-2026-04-20/`, never `DevRel_SF.docx`.
- Legacy company folders (`NVIDIA/`, `Vercel/`, `Handshake/`, `APublicSpace/`, `MarineLayer/`, `SFMOMA/`) are grandfathered as-is; migrate them per spec §10 Phase 5. Do not rename them ad hoc.
- Branches: `app/<company>-<role-slug>-<yyyy-mm-dd>` for per-application work. `main` is always submittable.

### 1.2 Commits

- Format: `<agent-or-area>: <verb> <object>` — e.g. `resume-tailor: rewrite summary for Vercel DX role`, `search-agent: add Lever adapter`.
- One logical change per commit. A resume tailor run is one commit. A spec edit is a separate commit.
- Never amend a commit the user has already seen (use `--amend` only on your own unpushed work within the current session).
- Never `git push --force` to `main`. Force-push to `app/*` branches is fine if you haven't merged yet.

### 1.3 Identity

- Git identity is **local to this repo only** — set via `git config user.name` / `user.email` (no `--global`). Confirm with `git config --local --list | grep user`.
- Default identity: `W.S. Gong <billygong@me.com>`. Ask the user before changing.

### 1.4 .gitignore guarantees

Nothing under these patterns may ever be committed:

- `config/secrets.env*`, `.env`, `.env.local`
- `.DS_Store` (anywhere)
- `search/runs/*/raw/` — raw HTML/JSON dumps stay local
- `__pycache__/`, `*.pyc`, `.venv/`, `~$*.docx`

If you need to track a file under a path like the above, refactor the path — don't add an exception.

### 1.5 DOCX handling

Binary `.docx` diffs are unreadable. For any generated resume or cover letter:

1. Write the `.docx` to its final location.
2. Also unpack it (zip → OOXML XML) to a sibling `*.unpacked/` folder, pretty-printed.
3. Commit both. `git log -- applications/<…>/resume.unpacked/` becomes the real audit trail.
4. Never edit the OOXML in the unpacked dir directly — it's output, not source.

### 1.6 Canonical resume style

Every resume goes through `build_resume.py` operating on `resume-template.docx`. The style spec at `docs/resume-style-spec.md` is authoritative for typography. Do **not** introduce a second resume template, rewrite `build_resume.py` from scratch, or switch fonts without explicit user sign-off.

## 2. Phased build plan

Execute phases in order. Each phase has a self-contained definition of done. Don't start Phase N+1 until the user has signed off on Phase N.

### Phase 1 — Top-of-funnel search (est. 1 week)

Goal: pull listings from Greenhouse/Lever/Ashby public APIs into a normalised, de-duped stream with a fit score. No resume tailoring yet.

Create:

- `config/criteria.yaml` — copy the draft from spec §3.2; ask the user to review the title include/exclude lists, comp floor, and company excludes before first run.
- `config/sites.yaml` — start with Greenhouse + Lever + Ashby + HN Who's Hiring. Skip LinkedIn in Phase 1 (it needs Chrome MCP and is brittle).
- `agents/search-agent.md` — prompt per spec §9.1.
- `agents/fit-scorer.md` — prompt per spec §3.5.
- `search/` directory tree and `search/seen.db` (SQLite, single `seen(hash TEXT PRIMARY KEY, seen_at TEXT)` table).
- `search/run.py` — thin Python driver that invokes adapters, writes `search/runs/<ts>/listings.jsonl`, calls the fit-scorer agent, emits `summary.md`.

Acceptance:

- One `search/run.py` invocation from empty state produces ≥ 30 normalised listings across the configured sources.
- Rerun within 24h adds zero duplicates.
- `summary.md` groups `recommend: yes` listings by company with source URLs and one-line rationales.

Commit boundary: one commit per adapter added, one for the driver, one for the scorer prompt. Keep `search/runs/<ts>/` out of git except for `summary.md` and `scored.jsonl`.

### Phase 2 — Resume tailoring (est. 1 week)

Goal: a listing in, a tailored `.docx` + `.pdf` out, with every claim traceable.

Create:

- `bullets.yaml` — enumerate every usable accomplishment from the existing `resume-template.docx` and the tailored resumes under `NVIDIA/`, `Vercel/`, `Handshake/`, etc. Tag each per spec §4.4. Built collaboratively with the user — the initial extraction runs through `scripts/extract_bullets.py`, then the user verifies every line. No auto-fabrication.
- `build_resume.py` refactor: accepts `--plan <path>` and `--out <path>` flags. Plan YAML has `target_role_family`, `summary_id` / `summary_text`, `skill_order`, `bullets_by_role`, `show_projects` / `show_publications` / `show_community`, and a free-form `picked_because` block for per-bullet rationale. Without `--plan`, produces the generalised resume byte-for-byte (acceptance check).
- `agents/resume-tailor.md` — prompt per spec §9.2. Includes dry-run mode, `fit-report.md` sibling artifact, and an explicit refusal protocol (`[NEEDS SOURCE]`).
- `scripts/extract_bullets.py` — helper to dump every DOCX bullet before hand-curation.
- `scripts/docx_to_pdf.py` — LibreOffice-headless wrapper (decision committed in spec §8.6; do not swap to `docx2pdf`).
- `scripts/check_provenance.py` — resume-side provenance checker per spec §8.8. Supports `--warn` (Phase 2 default) and `--block` (Phase 3+); `--all` and `--staged` selectors for repo-wide vs. pre-commit scans.
- `scripts/lint_bullets.py` — structural linter over `bullets.yaml`: unique ids, resolved role refs, known role families, summary `built_from` resolution, coverage warnings. Exit-nonzero on errors; `--strict` to treat warnings as errors.
- `scripts/bullets_lookup.py` — human-facing grep (`--tag`, `--family`, `--role`, `--keyword`, `--ids`, `--list-*`). Intended to be run by hand during planning; never wired into the build.
- `scripts/url_ingest.py` — single-listing entry point per spec §3.8 (LinkedIn / Greenhouse / Lever / Ashby / generic URL). Lives here in Phase 2 because it's the on-ramp into tailoring from outside the bulk search. LinkedIn and generic fallbacks emit a stub listing with `requires_chrome_mcp` / `requires_user_fill` flags; downstream tailoring refuses to run until cleared.
- `scripts/backprop_edits.py` — prompted back-propagation of user hand-edits on a rendered `resume.docx` into `bullets.yaml`. Prompts per-bullet: update / new-id / skip / quit. NEVER writes silently.
- `applications/_template/` — scaffolding for new application folders (tracker skeleton, listing placeholders).

Acceptance:

- `resume-tailor` against a sample listing produces a `resume.docx` whose every bullet appears verbatim in `bullets.yaml`.
- `resume.provenance.yaml` is emitted alongside, with an entry for every bullet/skill/summary sentence and `unsourced_claims: []`.
- Output passes the style-spec checks (font, accent color, layout).
- Rerun with identical inputs → byte-identical `.docx` and byte-identical provenance. (`python3 build_resume.py` from a clean checkout reproduces `2026-04-17-wsgong-resume-generalized.docx` content exactly.)
- The corresponding `resume.unpacked/` is committed alongside.
- `scripts/url_ingest.py <linkedin-url>` creates a well-formed application folder and branch without touching `seen.db`.
- `scripts/lint_bullets.py` exits 0 on the committed `bullets.yaml`.
- `fit-report.md` is written alongside every tailor run, naming every gap explicitly.

### Phase 3 — Cover letter writer (est. 1 week)

Goal: cover letters in the user's voice, grounded in real projects.

Create:

- `voice-corpus/` seeded with: `NVIDIA/nvidia-application-answers.md`, any prior cover letters the user can dig up, and 2–3 long-form samples (README excerpts, blog posts). Ask the user to drop samples here — don't invent.
- `config/voice.yaml` per spec §5.2 (includes `scheduling_preferences` for §6.8 once Phase 4 lands).
- `agents/cover-letter-writer.md` — prompt per spec §9.3. The agent must run a research pass that populates `applications/<…>/company-facts.md` BEFORE drafting (spec §5.3 step 1).
- `build_cover_letter.py` — renders `cover-letter.md` → `cover-letter.pdf` with the same Inter/#D44500 letterhead as the resume. Goes through `scripts/docx_to_pdf.py`.
- `scripts/check_provenance.py` already knows how to validate `cover-letter.md` / `cover-letter.provenance.yaml` (Phase 2 laid the infrastructure). The Phase 3 work is installing the pre-commit hook in `--block` mode so unsourced cover-letter commits are rejected, not merely warned.
- Extend `applications/_template/` with `company-facts.md`, `cover-letter.md`, and `cover-letter.provenance.yaml` skeletons (already present from Phase 3 kickoff — reference when starting a new application by hand).

Acceptance:

- Every generated letter names the company and at least one specific product/customer/announcement — every such mention is cited in `company-facts.md`.
- No `forbidden_phrases` appear.
- Length 300–400 words (hard fail > 500).
- Every concrete claim traces to `bullets.yaml`, `company-facts.md`, or `voice-corpus/`; `cover-letter.provenance.yaml` has `unsourced_claims: []`.
- `scripts/check_provenance.py` passes, and the pre-commit hook blocks unsourced commits.

### Phase 4 — Application tracking, follow-ups, and scheduling (est. 1 week)

Goal: `tracker.yaml` stays in sync with Apple Mail without pestering the user; recruiter questions and scheduling requests auto-draft replies that the user sends.

Status: **in progress** (2026-04-18). All agent prompts, deterministic scripts, and template skeletons are landed; the scheduled task + the user filling out `config/personal-facts.yaml` are the two remaining bits of setup. Pre-commit hook should already be in `--block` mode from Phase 3 — it covers `replies/*.provenance.yaml` without change.

Create:

- `tracker.yaml` schema per spec §6.2 and a template at `applications/_template/tracker.yaml`.
- `agents/tracker-agent.md` per spec §9.4. Uses `mcp__Control_your_Mac__osascript` against Apple Mail — NOT Gmail.
- `scripts/sweep.py` — runs the tracker agent across all open applications, regenerates `dashboard.md`.
- Scheduled task: every 2h via `mcp__scheduled-tasks__create_scheduled_task`.
- Apple Mail mailbox `JobSearch/<Company>` created on first tracked message per app (nested iCloud mailbox — Apple Mail has no Gmail-style labels).
- `config/personal-facts.yaml` (gitignored; spec §8.7) + `config/personal-facts.example.yaml` (committed template). Ask the user to fill out `personal-facts.yaml` before the reply-drafter can run.
- `agents/reply-drafter.md` per spec §9.6 — handles recruiter question threads. Drafts are staged in Mail.app's Drafts mailbox, never sent.
- `agents/scheduler.md` per spec §9.7 — handles scheduling threads. Uses the Google Calendar MCP (`mcp__8cb1832e-5c3e-45d7-a416-7920a5827a02__*`). Creates `[TENTATIVE]` calendar events only; confirmed events require explicit user acknowledgment.
- Extend `scripts/check_provenance.py` to cover `replies/*.md` / `replies/*.provenance.yaml`.

Acceptance:

- New recruiter email from a tracked company surfaces in the right `tracker.yaml` within 2h (verified via `mail_message_ids`).
- No outbound email is ever sent by the agent — only Apple Mail drafts, visible in Mail.app → Drafts.
- `dashboard.md` lists all non-archived applications grouped by status with next-action dates.
- Recruiter question threads produce a draft where every personal claim cites `personal-facts.yaml`; un-answerable questions become `[USER TO ANSWER]` placeholders, never guesses.
- Scheduling threads produce up to three candidate slots with quoted source phrases, a tentative Google Calendar event, and a draft reply. No confirmed event is ever auto-created.

### Phase 5 — Archiving + legacy migration (est. 1 week)

Goal: closed applications move out of the active tree; old company folders come into the new format.

Create:

- `agents/archiver.md` per spec §9.5.
- `archive/<year>/index.md` as rolling index.
- `scripts/migrate_legacy.py` — for each of `NVIDIA/`, `Vercel/`, `Handshake/`, `APublicSpace/`, `MarineLayer/`, `SFMOMA/`, prompt the user for final status (rejected/withdrawn/etc.) and move into `archive/2025/` or `archive/2026/`. Preserve file contents; regenerate `tracker.yaml` retroactively from what's known.

Acceptance:

- No application is deleted. Every archive move is reversible by `git mv`.
- `archive/<year>/index.md` stays under 200 lines per year.
- The retro in `archive/<year>/retro.md` writes config suggestions as a `.diff` — never auto-applies.

## 3. The daily loop (post-Phase-4)

Once the system is live, a typical day looks like:

1. Morning: scheduled `search/run.py` completes at 07:00 PT. Claude Code opens `search/runs/<today>/summary.md` and lists `yes` recommendations.
2. User picks one: "Let's apply to the Anthropic FDE role." (Or: user drops a LinkedIn URL into chat — `scripts/url_ingest.py <url>` bypasses the bulk search and jumps straight to step 3.)
3. Agent creates `applications/Anthropic/forward-deployed-engineer-2026-04-20/` on branch `app/Anthropic-forward-deployed-engineer-2026-04-20`, drops `listing.json` + `listing.md`, generates `resume-plan.yaml`, `resume.docx` + `resume.pdf` + `resume.provenance.yaml`, writes `company-facts.md`, then `cover-letter.md` + `.pdf` + `cover-letter.provenance.yaml`. The two PDFs are the deliverables — they ship as separate files. Pre-commit hook passes only if every concrete claim is sourced.
4. User reviews. Edits by hand if needed. Says "merge" → fast-forward into `main`.
5. User applies via the portal themselves (uploading `resume.pdf` and `cover-letter.pdf` separately), then tells the agent "applied to Anthropic". Agent writes `tracker.yaml` with `status: applied`.
6. Tracker sweep runs every 2h; promotes status as Apple Mail messages arrive. Question threads get auto-drafted replies (user opens Mail.app → Drafts, reviews, sends). Scheduling threads get candidate slots + a tentative Google Calendar event.
7. When the application closes, the archiver moves it to `archive/<year>/` and renames the mailbox to `JobSearch-Archive/<Company>`.

## 4. Environment and dependencies

Record any install decisions here so the next session doesn't reinvestigate.

- **Python**: 3.11+. Use a local `.venv` (gitignored). Deps pinned in `requirements.txt` at repo root once Phase 1 lands.
- **Node**: only if an adapter requires it (currently none do).
- **System tools**: `git`, `gh` (auth'd), `libreoffice` (installed via `brew install libreoffice` — decision committed in spec §8.6, do not swap to `docx2pdf`).
- **Python deps added in later phases**: `python-dateutil` (Phase 4, for scheduler time parsing).
- **MCP servers expected to be connected**:
  - `mcp__Control_your_Mac__osascript` — Apple Mail (iCloud) read + draft, plus any AppleScript the tracker or scheduler needs. **Required from Phase 4.**
  - Google Calendar MCP (`mcp__8cb1832e-5c3e-45d7-a416-7920a5827a02__*`) — scheduler. Required from Phase 4.
  - Chrome MCP (`mcp__Claude_in_Chrome__*`) — LinkedIn URL ingest. Required from Phase 2 when `scripts/url_ingest.py` hits a LinkedIn URL.
  - Google Drive — optional.
  - Notion — optional (Phase 4+ dashboard mirror, see spec §11.1).
  - `mcp__scheduled-tasks__*` — daily search run + every-2h tracker sweep.

## 5. Trust boundary — human-in-the-loop checkpoints

Two moments where the agent ALWAYS stops and asks the user. Non-negotiable.

1. **Before a job application is submitted.** The agent produces artifacts; the user uploads them to the portal. Never auto-submit, never fill portal forms, never click "Submit".
2. **Before any email leaves the outbox.** Recruiter replies are staged in Apple Mail.app's Drafts mailbox. The user opens and sends. Never call `send mail` via AppleScript — only `make new outgoing message` (which lands the message in Drafts).
3. **Before a calendar event is marked confirmed.** The scheduler creates `[TENTATIVE]` events only. Promoting to confirmed requires the user saying "confirmed" after the recruiter locks a slot.

Everything else — searching, scoring, tailoring, drafting, committing, archiving — runs without asking, because it's local, reversible, and in git.

## 6. What not to do

- Don't set global git config. Local only.
- Don't run `git push --force` against `main`. Ever.
- Don't skip pre-commit hooks (`--no-verify`) unless the user asks. The provenance hook (§8.8) in particular must never be bypassed — it's the hallucination guard.
- Don't modify `resume-template.docx` (the pristine master) except to fix a genuine bug in the master itself — and then ask first.
- Don't introduce a second resume font, second accent color, or second template layout without user sign-off.
- Don't `git add .DS_Store` even once — it'll live forever in history.
- **Don't invent resume bullets.** Every claim must trace to `bullets.yaml` or the template. If you're about to write a sentence you can't cite, write `[NEEDS SOURCE: <claim>]` and stop — never fill the gap with a plausible guess.
- **Don't invent company facts.** Every concrete noun in a cover letter (product, customer, announcement, dollar figure) must be cited in `company-facts.md` with a URL. If your research pass came back empty, fall back to a JD-specific detail from `listing.md` — don't make something up.
- **Don't invent personal facts.** Every answer to a recruiter question about the user must cite a key in `config/personal-facts.yaml`. If the answer isn't there, insert `[USER TO ANSWER: <question>]` in the draft — never guess at visa status, comp expectations, start date, or relocation willingness.
- **Don't write buzzy cover-letter openings.** This is a repeat correction. The first sentence of P1 must state W.S.'s interest in the position itself, expressed concretely (e.g. `"I'd like this role because <specific reason from JD or company facts>."`). Never quote the company's marketing copy back at them, never lead with a famous-customer/stat-then-meta-pivot ("that's the precedent in the room"), never use "what excites me about" / "what pulled me to" / "what drew me to". Authoritative rule: `config/voice.yaml → opening`.
- **NEVER open a cover letter with timely news about the company.** Repeat correction (Cognition Partner-DE letter, 2026-04-22: "DO NOT start with timely news. I find it corny and that it is trying too hard."). No recent product launches, acquisitions, market expansions, partnerships, blog posts, customer wins, funding rounds, conference appearances, or anything framed as "news." No "today" / "this morning" / "last week" / "recently" / "just announced." No name-drops of a freshly announced customer or partner as the hook. Open with W.S.'s own work or framing. Company facts in the body must be DURABLE context (what the product does, who the team serves), not news. Authoritative rule: `config/voice.yaml → opening` (HARD-BANNED OPENING PATTERNS).
- **Don't use em-dashes (—) in W.S.'s voice.** Anywhere prose is rendered as W.S.: cover letters, reply drafts, `[USER TO ANSWER]` placeholders, anywhere. He's a colons / semicolons / parens / period person and never uses em-dashes in this context. Replace any em-dash with one of those. En-dashes (–) for date and number ranges (e.g. 2017–2020, 20–45) are fine. Authoritative rule: `config/voice.yaml → style_notes`.
- Don't send email. Only stage drafts in Mail.app's Drafts mailbox via AppleScript's `make new outgoing message`. Never use `send`.
- Don't create confirmed calendar events. `[TENTATIVE]` only, until the user explicitly confirms a slot.
- Don't commit `config/personal-facts.yaml` — it's gitignored. If the user pastes contents in chat, update the file on disk (locally); do not stage it.
- Don't auto-apply the archive-review retro's config suggestions. The retro emits a `.diff`; the user merges by hand.
- Don't commit anything under `config/secrets.env*`, even if the user pastes a token. Redirect them to the gitignored file.
- Don't try to use the Gmail MCP. The user uses iCloud Mail; the tracker talks to Apple Mail via `mcp__Control_your_Mac__osascript`.

## 7. Files of record

When landing fresh in this repo, read in this order:

1. `job-search-agent-spec.md` — what we're building and why.
2. `CLAUDE.md` (this file) — how to build and operate it.
3. `config/criteria.yaml` — current targeting rules (exists from Phase 1 onward).
4. `bullets.yaml` — the ground truth for resume experience claims (exists from Phase 2 onward).
5. `config/voice.yaml` + `voice-corpus/` — tone for cover letters (exists from Phase 3 onward).
6. `config/personal-facts.yaml` — closed universe for recruiter-reply personal claims (exists from Phase 4 onward; gitignored — read it, don't commit changes to it).
7. `dashboard.md` at repo root (generated, not committed) — what's in flight right now.

## 8. Open questions from the spec (resolve before/during each phase)

Copy from spec §11 for convenience — any of these unblocked yet?

1. ~~Phase 4+: Notion read-only dashboard mirror, yes/no?~~ **Resolved 2026-04-18: no — `dashboard.md` only.** Revisit if the markdown file stops feeling sufficient.
2. Phase 1: keep `comp_floor_usd` at $180k or leave unset initially?
3. Phase 2+: LinkedIn Easy Apply flow (URL-ingest produces the listing either way; the open question is the apply path).
4. Phase 3: cover letter letterhead — full resume letterhead or slimmer?
5. `search/runs/` retention — forever or 30-day broom?
6. ~~Phase 4: `config/personal-facts.yaml` — user fills in which fields, leaves which as placeholders?~~ **Resolved 2026-04-18: scaffold only — `config/personal-facts.example.yaml` is committed with every field null; the user fills out `config/personal-facts.yaml` (gitignored) locally before the reply-drafter runs.** Any unfilled field renders in a draft as `[USER TO ANSWER: …]` — never as a guess.
7. ~~Phase 4: scheduling defaults — 9am–6pm PT, next 10 business days. Override in `config/voice.yaml`?~~ **Resolved 2026-04-18: yes, defaults live in `config/voice.yaml → scheduling_preferences`.** Per-application overrides via the scheduler agent's inputs if a specific role needs them.
8. Phase 3: company research depth — homepage + /products + /customers + 6mo /blog. Adjust?
9. Phase 2/3: combined-PDF ordering — resume first, cover letter second. Flip for any employers?
10. Phase 2→3: provenance hook ships warning-only in Phase 2, blocking before Phase 3. OK with that ramp or blocking from day one?

---

*End of playbook. Edit this file as conventions evolve — it's the first thing any future Claude Code session reads.*
