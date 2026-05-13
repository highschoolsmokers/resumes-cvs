# Job Search Agent — Implementation Spec

**Author:** W.S. Gong
**Last updated:** 2026-04-18
**Status:** Draft v1 — ready for implementation

## 0. Goal

A local-first, git-versioned system of cooperating agents that (1) finds technical roles W.S. Gong is a strong fit for, (2) provisions and tailors a resume for each, (3) drafts a cover letter in his voice, (4) tracks every application through to outcome, and (5) archives past applications in a form that is easy to grep, diff, and learn from.

The design leans on tools already available: Apple Mail via AppleScript (for inbox monitoring and staging recruiter-reply drafts — the user is an iCloud Mail user, not Gmail), Google Calendar via its connected MCP (for interview scheduling), Chrome MCP (for DOM-aware browsing of LinkedIn and Greenhouse), Google Drive and Notion (optional), plus the existing `build_resume.py` pipeline and the `WSGong_Resume_Template.docx` master. State lives on disk under `Resumes/`. Versioning is plain `git` — every listing, resume revision, cover letter, and tracker change is a commit.

There is no persistent mail credential to store anywhere: the agents talk to the already-signed-in Mail.app (which holds the iCloud IMAP session) via the `mcp__Control_your_Mac__osascript` tool.

## 1. Architecture at a glance

Seven cooperating agents plus a URL-ingest utility, each with a narrow job and a shared on-disk contract. Two entry points converge on the same tailoring pipeline:

    ┌──────────────────────┐        ┌──────────────────────┐
    │  search-agent        │        │  url-ingest          │  single listing (LinkedIn, etc.)
    │  (bulk, scheduled)   │        │  (on-demand, 1 URL)  │
    └──────────┬───────────┘        └──────────┬───────────┘
               │                               │
    ┌──────────▼───────────┐                   │
    │  fit-scorer          │                   │
    └──────────┬───────────┘                   │
               │   top-N forwarded             │   always forwarded
               └───────────────┬───────────────┘
                               │
                    ┌──────────▼───────────┐          ┌──────────────────────┐
                    │  resume-tailor       │─────────▶│  cover-letter-writer │
                    └──────────┬───────────┘          └──────────┬───────────┘
                               │                                 │
                               └────────────┬────────────────────┘
                                            │
                                 ┌──────────▼───────────┐
                                 │  tracker-agent       │  Apple Mail watcher, updates tracker.yaml
                                 └──────┬───────┬───────┘
                          scheduling    │       │   question
                              ┌─────────┘       └─────────┐
                              ▼                           ▼
                    ┌──────────────────┐        ┌──────────────────┐
                    │  scheduler       │        │  reply-drafter   │
                    │  (calendar)      │        │  (follow-ups)    │
                    └──────────┬───────┘        └──────────┬───────┘
                               │                           │
                               └────────────┬──────────────┘
                                            ▼
                                 ┌──────────────────────┐
                                 │  archiver            │  moves closed apps → archive/<year>/
                                 └──────────────────────┘

All of them are invoked from Cowork conversations or from a single scheduled task. None runs continuously; each one is idempotent so a rerun produces the same output for the same inputs.

The two entry points are symmetric from `resume-tailor` onwards — the URL-ingest path is just a way for the user to say "skip the search, I already found this one" and drop directly into tailoring. Details in §3.8.

## 2. Repository layout

The `Resumes/` workspace folder becomes a git repo. Everything the agents produce or read lives in it.

```
Resumes/
├── .git/
├── job-search-agent-spec.md          ← this file
├── build_resume.py                   ← existing generator
├── WSGong_Resume_Template.docx       ← pristine master template
├── 2026-04-17-wsgong-resume-generalized.docx  ← latest generalized build
│
├── config/
│   ├── criteria.yaml                 ← role targeting rules (§3.2)
│   ├── sites.yaml                    ← search-site adapters (§3.3)
│   ├── voice.yaml                    ← cover-letter voice knobs
│   ├── personal-facts.yaml           ← gitignored; eligibility/comp/start date (§8.7)
│   ├── personal-facts.example.yaml   ← template, committed
│   └── secrets.env.example           ← placeholder (no real secrets in git)
│
├── voice-corpus/                     ← writing samples that inform tone
│   ├── nvidia-application-answers.md
│   ├── bindery-readme-excerpt.md
│   └── cover-letters-archive/
│
├── scripts/
│   ├── docx_to_pdf.py                ← LibreOffice-headless wrapper (§8.6)
│   └── url_ingest.py                 ← single-listing entry point (§3.8)
│
├── search/
│   ├── runs/<YYYY-MM-DD-HHMM>/
│   │   ├── raw/                      ← raw HTML/JSON from each site
│   │   ├── listings.jsonl            ← normalised listings (§3.4)
│   │   ├── scored.jsonl              ← after fit-scorer
│   │   └── summary.md                ← human-readable run report
│   └── seen.db                       ← SQLite de-dupe cache (sha256(listing_url))
│
├── applications/
│   └── <Company>/<Role-Slug>-<YYYY-MM-DD>/
│       ├── listing.json              ← canonical listing (immutable)
│       ├── listing.md                ← rendered job description
│       ├── fit-notes.md              ← why this one matched
│       ├── resume.docx               ← tailored
│       ├── resume.pdf                ← same, exported
│       ├── cover-letter.md           ← tailored
│       ├── cover-letter.pdf
│       ├── application-answers.md    ← supplemental Q&A (when asked)
│       ├── replies/                  ← recruiter follow-up drafts (§6.7)
│       │   └── <YYYY-MM-DD>-<topic>.md
│       ├── schedule/                 ← interview-scheduling artifacts (§6.8)
│       │   └── <YYYY-MM-DD>-<event>.yaml
│       ├── tracker.yaml              ← status timeline (§6.2)
│       └── notes.md                  ← freeform running log
│
└── archive/
    └── <year>/<Company>-<Role>-<YYYY-MM-DD>/   ← moved by archiver
```

Conventions: every folder and file name is lowercase-kebab, with an ISO date suffix when mutability matters. A role slug is `{title-lower-kebab}-{optional-location}`; e.g. `developer-advocate-sf`. The per-company folder already in use (`NVIDIA/`, `Vercel/`, `Handshake/`) remains valid — the agents treat any existing top-level company folder as a legacy application and migrate it on first touch.

### 2.1 Git strategy

- `main` is always in a working state — i.e. every committed application is at least submittable.
- Each new application starts on a branch `app/<Company>-<Role>-<YYYY-MM-DD>` so the tailoring agents can iterate without polluting `main`. Merging is a fast-forward once the user approves the final resume + cover letter.
- Resume diffs become legible because `build_resume.py` produces deterministic docx; the binary is committed alongside an **unpacked** view in `applications/<…>/resume.unpacked/` (OOXML, pretty-printed) so `git diff` shows meaningful line changes across revisions.
- Commit message convention: `<agent>: <verb> <object>` — e.g. `resume-tailor: rewrite summary for Vercel DX role`. Makes `git log --oneline` a usable audit trail.
- `.gitignore` excludes `config/secrets.env`, `search/runs/*/raw/`, `*.DS_Store`.

## 3. Component 1 — Agentic search

### 3.1 Goal

Discover listings for which W.S. Gong is plausibly a top-10% candidate, across LinkedIn, Greenhouse-hosted careers pages, and a configurable set of other sources. Produce a normalised, de-duplicated stream of listings for downstream scoring and tailoring.

### 3.2 Criteria (`config/criteria.yaml`)

This file is the contract between the user and the search agent. A concrete first draft, based on the existing resume and the role families the user named:

```yaml
role_families:
  - developer-relations        # DevRel engineer, developer advocate, docs lead
  - forward-deployed-engineer  # FDE, solutions engineer, applied engineer
  - agentic-programmer         # AI engineer, agent/LLM infra, MCP / Claude Code-adjacent
  - technical-writer           # staff technical writer, DX writer, API docs lead

title_keywords_include:
  - "developer advocate"
  - "developer relations"
  - "devrel"
  - "forward deployed"
  - "solutions engineer"
  - "applied engineer"
  - "ai engineer"
  - "agent engineer"
  - "technical writer"
  - "documentation engineer"
  - "developer experience"

title_keywords_exclude:
  - "intern"
  - "sales"            # unless "solutions engineer"
  - "manager"          # IC focus; flip to include once ready for mgmt
  - "director"
  - "staff engineer, security"   # example of a family mismatch

seniority: [mid, senior, staff]

location:
  base: "San Francisco Bay Area"
  remote_ok: true
  relocate_for:
    - "New York, NY"
    - "Remote (US)"
  on_site_only: exclude

comp_floor_usd: 180000           # total cash; used as a soft filter
equity_required: false
stage_preference: [series-b, series-c, public]     # not a hard gate

company_exclude:                 # regrettable or already-passed
  - "Example Inc."

tech_affinity_boost:             # +score when these appear in the JD
  - "MCP"
  - "Model Context Protocol"
  - "Next.js"
  - "Playwright"
  - "Sanity"
  - "docs as code"
  - "agent"
  - "LLM"
  - "developer experience"
```

### 3.3 Source adapters (`config/sites.yaml`)

Each source is an adapter with a name, a retrieval strategy, and a parser. Strategy is one of `chrome-mcp` (DOM-aware browsing — required for LinkedIn), `web-fetch` (plain HTTP fetch + parse — works for most Greenhouse boards), or `api` (where a structured endpoint exists, e.g. Greenhouse Job Board API: `https://boards-api.greenhouse.io/v1/boards/<token>/jobs`).

```yaml
- name: linkedin
  strategy: chrome-mcp
  queries:
    - "developer advocate Bay Area"
    - "forward deployed engineer"
    - "AI engineer agents remote"
  auth: session-cookie            # user is already signed in in Chrome
  rate_limit: 1 req / 3s

- name: greenhouse-aggregate
  strategy: api
  endpoint_template: "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
  tokens:
    - anthropic
    - vercel
    - stripe
    - openai
    - figma
    - notion
    - linear
    - supabase
    - retool

- name: lever-aggregate
  strategy: api
  endpoint_template: "https://api.lever.co/v0/postings/{token}?mode=json"
  tokens: [scaleai, mistral, replicate]

- name: ashby-aggregate
  strategy: api
  endpoint_template: "https://jobs.ashbyhq.com/api/non-user-graphql?op=ApiJobBoardWithTeams"
  tokens: [langchain, modal, braintrust]

- name: yc-jobs
  strategy: web-fetch
  url: "https://www.ycombinator.com/jobs"

- name: hn-whos-hiring
  strategy: web-fetch
  url: "https://news.ycombinator.com/submitted?id=whoishiring"
  parser: hn-monthly-thread
```

New adapters are additive — drop a block in `sites.yaml`, add a parser under `agents/search/parsers/<name>.md`, rerun.

### 3.4 Normalised listing schema

Every adapter outputs records shaped like:

```json
{
  "id": "greenhouse:anthropic:4321098",
  "source": "greenhouse-aggregate",
  "source_url": "https://job-boards.greenhouse.io/anthropic/jobs/4321098",
  "company": "Anthropic",
  "title": "Forward Deployed Engineer",
  "location": "San Francisco, CA",
  "remote": "hybrid",
  "seniority": "senior",
  "posted_at": "2026-04-14",
  "comp": { "min": 210000, "max": 310000, "currency": "USD", "equity": true },
  "description_md": "…full JD, markdown-converted…",
  "requirements": ["5+ years…", "Experience with …"],
  "tech_mentions": ["Python", "TypeScript", "MCP"],
  "fetched_at": "2026-04-18T10:22:00-07:00"
}
```

De-dupe key: `sha256(source + source_url)` stored in `search/seen.db`.

### 3.5 Fit scorer

A second sub-agent, not a separate service. Given a listing and `criteria.yaml`, it returns a score in [0, 100] with a short rationale. Rough rubric (tunable in `criteria.yaml`):

- +40 baseline if title matches `title_keywords_include`
- −∞ (hard reject) if any `title_keywords_exclude` or `company_exclude` hits
- +10 per `tech_affinity_boost` term present in JD (cap at +30)
- +10 for seniority match
- +10 for location or remote match
- +5 for comp within band; −10 if clearly below `comp_floor_usd`
- +0–15 qualitative adjustment from the LLM itself, with a one-sentence reason

Output is `scored.jsonl` — each row is the listing plus `score`, `rationale`, `recommend` (`yes` / `maybe` / `no`). The run summary (`summary.md`) lists the `yes`es first, grouped by company, linking to each source URL.

### 3.6 Scheduling

One scheduled task (via `mcp__scheduled-tasks__create_scheduled_task`) runs `search-agent` daily at 07:00 PT. It writes a run folder and opens a Cowork notification summarising the top hits. Ad-hoc runs are triggered from a conversation ("search this week").

### 3.7 Acceptance criteria

- First run from an empty `seen.db` produces ≥ 30 listings across the configured sources.
- Rerun within 24h produces 0 duplicates (verified against `seen.db`).
- Every `yes`-recommended listing has a non-empty `rationale`.
- No listing is written without `source_url`, `company`, `title`, and `posted_at`.

### 3.8 Single-listing entry point (`scripts/url_ingest.py`)

Not every application comes from the bulk search. The user will frequently stumble across a listing on LinkedIn, or a friend will send one over — and they want to drop straight into tailoring without waiting for the next scheduled run.

`scripts/url_ingest.py <URL>` is the on-ramp:

1. Detect the URL's source by host:
   - `linkedin.com/jobs/view/...` → `chrome-mcp` strategy (requires a signed-in session; falls back to prompting the user to open the tab and paste the JD text if the DOM scrape fails).
   - `boards.greenhouse.io/*/jobs/<id>` or `job-boards.greenhouse.io/*/jobs/<id>` → Greenhouse public job endpoint (`/v1/boards/<token>/jobs/<id>`).
   - `jobs.lever.co/<token>/<id>` → Lever postings endpoint.
   - `jobs.ashbyhq.com/<token>/<id>` → Ashby GraphQL.
   - Anything else → generic `web-fetch` + prompt-based JD extraction.
2. Parse the listing into the same normalised schema as §3.4. Same keys, same shape. If any required field is missing (company, title, or JD body), the script prompts the user to fill it in rather than writing a half-listing.
3. **Bypass `seen.db`.** This is a deliberate, user-initiated action — if the listing was already seen by the bulk search, ingest still proceeds. The ingest path appends `"ingest": "manual"` to the listing record so the downstream audit trail shows the entry point.
4. Write `listing.json` + `listing.md` into a fresh `applications/<Company>/<Role-Slug>-<YYYY-MM-DD>/` folder.
5. Create branch `app/<Company>-<Role-Slug>-<YYYY-MM-DD>` (identical convention to §2.1) and commit the raw listing as the first commit on the branch.
6. Hand off to `resume-tailor` — fit scoring is skipped because the user already decided to pursue this one.

LinkedIn specifics: we rely on the Chrome MCP to read the fully-rendered JD (LinkedIn's HTML is heavily client-rendered and the "See more" expand-on-click gates the full description). The user has to have the LinkedIn tab open and be signed in; the script does not log in or store session cookies. If Easy Apply is detected on the page, the ingest still produces `listing.json` — whether to use Easy Apply or route through the company ATS is a user decision per §11.3.

Acceptance criteria:

- `scripts/url_ingest.py <url>` for any supported source produces a folder whose `listing.json` conforms to the §3.4 schema.
- A LinkedIn URL that resolves to a Greenhouse/Lever/Ashby listing via its "apply" button rewrites the adapter choice to the underlying ATS so the structured data is richer than the LinkedIn summary.
- The script never requires editing `seen.db` to run again on the same URL.

## 4. Component 2 — Resume provisioning and tailoring

### 4.1 Goal

For each selected listing, produce a one-page `.docx` resume (+ `.pdf` export) that preserves the canonical W.S. Gong Swiss style (see `/.auto-memory/resume_style_spec.md`) and is tuned to the listing's specific language and stack — without inventing experience.

### 4.2 Inputs

- Generalised source: `WSGong_Resume_Template.docx` + the most recent `*-wsgong-resume-generalized.docx` build.
- The listing's `description_md`, `requirements`, `tech_mentions`.
- Optional: prior tailored resumes for the same company (reused as scaffolding — see §8).

### 4.3 Tailoring moves (what the agent is allowed to change)

- **Summary paragraph** — fully rewritten each time. Must stay ≤ 3 sentences and only claim experience already present in the master.
- **Skill categories** — the four Relevant Skills lines are reordered and items within each line reshuffled so the JD's most-mentioned terms come first. New items may be added *only if* the term appears somewhere in prior accomplishments or the voice corpus.
- **Bullet selection** — each job has a pool of 4–8 candidate bullets in a parallel `bullets.yaml` (maintained alongside the master). The agent picks the best 2–4 per role for this listing. Never writes new claims; never inflates.
- **Bullet wording** — verbs and order may change; numbers and outcomes may not.

Everything else (name, contact, section order, typography) is frozen and inherited from the template per the style spec.

### 4.4 `bullets.yaml` (new artifact)

A YAML file at the repo root enumerating every usable accomplishment bullet, plus a closed library of pre-written summaries, skill groups, and education entries. Shape (truncated — see `bullets.yaml` for the authoritative schema):

```yaml
meta:
  canonical_name: "W.S. Gong"
  contact: { city, phone, email, site, github, linkedin }

roles:
  - id: slack-2017
    employer: "Slack Technologies"
    title_default: "Technical Lead Manager / Staff Engineer"
    title_alternates:                 # keyed by role_family (criteria.yaml)
      developer-relations: "Technical Lead Manager and Staff Engineer — Slack Developer Platform"
    location: "San Francisco, CA"
    start: "2017"
    end:   "2020"

bullets:
  - id: slack-api-refs-adopted-externally
    role_id: slack-2017               # resolves to roles[].id
    text: "Produced API references, integration guides, SDK documentation..."
    role_family: [technical-writer, developer-relations]   # which families favour this bullet
    tags: [api-docs, block-kit, workflows]                 # topical tags for hand lookup
    source_doc: 2026-04-17-wsgong-resume-generalized.docx  # where the wording came from

summaries:                            # pre-written summary paragraphs, per family
  developer-relations:
    - id: devrel-summary-docs-platform
      text: "Developer-platform builder with 25+ years..."
      built_from: [slack-api-refs-adopted-externally, ...]  # provenance for the summary itself

skills_menu:                          # closed set of skill groups, no ad hoc additions
  agentic-programming:
    label: "Agentic Programming"
    content: "Anthropic SDK, Claude API, MCP server..."

education:                            # structural; never omitted
  - id: mfa-sfsu
    school: "San Francisco State University"
    degree: "MFA, Creative Writing (Fiction)"
    ...
```

`role_family` values come from `config/criteria.yaml` (currently: `developer-relations`, `forward-deployed-engineer`, `agentic-programmer`, `technical-writer`). The tailor prefers bullets whose family list contains the target family but may pull a neighbouring bullet if the JD signal is strong.

`scripts/bullets_lookup.py` is a human-facing grep over this file (by `--tag`, `--family`, `--role`, `--keyword`). `scripts/lint_bullets.py` enforces uniqueness, reference integrity, and coverage-per-family before build. Both are meant to be run by hand during tailoring; neither is wired into the pre-commit hook.

### 4.4.1 The plan YAML (`resume-plan.yaml`)

The tailor never edits the resume directly. It writes a plan, which `build_resume.py --plan` consumes:

```yaml
target_role_family: developer-relations
summary_id: devrel-summary-docs-platform     # one of bullets.yaml summaries
summary_text: null                           # OR inline override (still must be sourced)
skill_order: [agentic-programming, technical-writing, languages-platforms, editorial-teaching]
bullets_by_role:
  independent-2022: [independent-mcp-servers-paperless-colophon-litverity, ...]
  slack-2017:       [slack-api-refs-adopted-externally, slack-cypress-90-coverage]
show_projects:     true
show_publications: true
show_community:    true
picked_because:                              # per-bullet rationale — for the user's review
  - independent-mcp-servers-paperless-colophon-litverity: "JD: 'MCP server development'"
  - slack-api-refs-adopted-externally:       "JD: 'developer platform reference implementations'"
```

`build_resume.py` fails loud if any id in the plan doesn't resolve inside `bullets.yaml` — that is the anti-hallucination guard (see §8.8). `picked_because` is free-form and not validated; it's there so the user can diff "why these bullets for this role" six months later.

### 4.5 Build flow

1. `resume-tailor` reads the listing and `bullets.yaml`.
2. It writes `resume-plan.yaml` to the application folder (schema per §4.4.1) and `fit-report.md` (see §4.8).
3. **Optional dry-run.** If invoked with `--dry-run`, the tailor stops here. The user reviews `resume-plan.yaml` + `fit-report.md` before the actual render. Default mode proceeds to step 4.
4. `build_resume.py --plan <plan>.yaml --out resume.docx` consumes the plan and emits `resume.docx` into the application folder, preserving all OOXML styling via the unpack-edit-repack flow. It also writes `resume.unpacked/` as a sibling directory for legible git diffs (CLAUDE.md §1.5).
5. The docx is rendered to PDF via `scripts/docx_to_pdf.py` (LibreOffice headless — see §8.6 for why we picked it over `docx2pdf`).
6. Everything is committed on the application's branch. The plan YAML is also committed, so "why did we pick these bullets for Vercel?" is diffable six months later.
7. Emit `resume.provenance.yaml` per §8.8 — every bullet, skill item, and summary sentence maps to a `bullets.yaml` ID. The pre-commit hook (`scripts/check_provenance.py`) blocks the commit if anything in the docx is unsourced. Phase 2 runs in warn-only mode; the hook flips to blocking at the Phase 3 boundary (spec §11.10 / CLAUDE.md §2).
8. Deliverables are `resume.pdf` and `cover-letter.pdf` as separate files. The portal gets two attachments — we do not merge them into a combined PDF.

### 4.6 Git as versioning and back-propagation of edits

- Every tailor run is one commit, title `resume-tailor: <company> <role> v<n>`.
- `git log -- applications/<Company>/…/resume.unpacked/` is the audit trail of what shipped. The `.unpacked/` sibling is the one thing that makes OOXML diffs legible.
- If the user edits the rendered docx by hand after a run — sharpening phrasing, fixing a typo — those edits are first-class. The way they propagate back into the closed universe is **`scripts/backprop_edits.py applications/<…>/`**, which is *prompted, never silent*:
  1. The script reads `resume.provenance.yaml` to find out which `bullets.yaml` id each rendered bullet came from.
  2. It diffs the rendered Experience body against the source bullet's `text`.
  3. For each diverged bullet it asks: update-in-place (`[u]`), create a new bullet id (`[n]`), or skip (`[s]`).
  4. Nothing gets written without a keystroke. The only "write back" the system performs is one the user authorised one divergence at a time.
- The backprop script is what turns repeated tailoring into a self-improving bullet library, without the agent ever silently mutating `bullets.yaml` on the user's behalf.

### 4.7 Acceptance criteria

- Output docx passes the `resume_style_spec.md` checks: Raleway/Lato, #D44500 accent, 2-column, dates in left margin.
- Page count = 1 for every generated file.
- Every bullet in the output appears verbatim in `bullets.yaml`, and `resume.provenance.yaml` has a `claims[]` entry for every bullet, skill item, and summary sentence (§8.8). `unsourced_claims` is empty.
- `scripts/check_provenance.py` passes on the application folder (warn-only in Phase 2; blocking in Phase 3+).
- `scripts/lint_bullets.py` exits 0 (the tailor should never have touched `bullets.yaml`, but we lint anyway).
- Rerunning with the same inputs produces a byte-identical docx and an identical provenance file.

### 4.8 Fit report (sibling artifact)

Alongside `resume-plan.yaml`, the tailor writes `fit-report.md` — a short human-facing document that explains the plan's reasoning. It is the user's review surface before merging the branch.

Schema:

```markdown
# Fit report — <Company> <Role>

Target family: developer-relations
Summary: devrel-summary-docs-platform (or <inline summary_text>)

## Why the JD matches

- JD line: "... build reference implementations for partners..."
  → bullet: slack-api-refs-adopted-externally
- JD line: "... own documentation for the platform..."
  → bullet: independent-docs-pipelines-openapi

## Gaps

- JD asks for <thing>; no bullet in bullets.yaml covers this. Options:
  (a) skip (risk: looks inexperienced in X)
  (b) add a new bullet from user-provided experience (requires bullets.yaml update)

## Skills I ordered

1. Agentic Programming — JD emphasises MCP + Anthropic SDK
2. Technical Writing & Docs
3. Languages & Platforms
4. Editorial & Teaching
```

Every "JD line" quote is verbatim — the user should be able to grep `listing.md` for it. Every gap is named explicitly. No "should be fine" language.

The fit report also doubles as pre-context for `cover-letter-writer` (§5): the writer reads `fit-report.md` to understand what the tailor chose to emphasise before drafting the letter's bridge paragraph.

## 5. Component 3 — Cover letter in the user's voice

### 5.1 Goal

A cover letter per listing that reads like W.S. Gong wrote it — specific to the company and role, grounded in real projects, never generic.

### 5.2 Voice corpus

`voice-corpus/` contains real writing samples the cover-letter agent reads before drafting — the NVIDIA application-answers doc, READMEs from Bindery and other projects, prior cover letters, and any long-form posts. These samples are the ground truth for tone; the agent is instructed to match sentence rhythm and vocabulary, not to copy phrases.

`config/voice.yaml` captures the knobs:

```yaml
length: 300-400 words             # three tight paragraphs
opening: "specific hook — a product detail or recent announcement, never 'I am writing to apply'"
close: "direct, no thanks-for-your-consideration padding"
pronouns: first-person
forbidden_phrases:
  - "passionate about"
  - "dynamic team"
  - "wear many hats"
  - "results-oriented"
signature: "W.S. Gong"
```

### 5.3 Flow

1. **Research pass (mandatory before drafting).** Agent populates `applications/<…>/company-facts.md`: each concrete fact it plans to cite (product name, customer, recent announcement, funding event, founder quote) with the URL it came from. Sources: the listing.json itself (often includes company blurb), the company's homepage, `/products`, `/customers`, and the last six months of `/blog` — fetched via WebFetch. Anything not in company-facts.md is not eligible for citation. If the agent can't find a concrete, interesting company-specific detail, the draft's hook falls back to a role-specific detail from the JD (also citeable from `listing.md`).
2. Agent reads `listing.md`, the tailored `resume.docx` (extracted to text), `voice-corpus/*`, `config/voice.yaml`, and the freshly-written `company-facts.md`.
3. Produces `cover-letter.md` with three paragraphs:
   - **Hook** — a concrete detail about the company/role that only someone who read the JD closely would write. Every concrete noun cites a line in `company-facts.md` or `listing.md`.
   - **Bridge** — two or three evidence points from the resume that map directly to the top requirements, in the user's own earlier phrasing where possible. Every experience claim cites a `bullets.yaml` ID.
   - **Close** — what he'd want to talk about in a first conversation. No pleasantries.
4. Emit `cover-letter.provenance.yaml` per §8.8 — every concrete noun and every experience claim mapped to `bullets.yaml`, `company-facts.md`, or `voice-corpus/`. Sentences that are pure voice/connective tissue don't need entries.
5. Exports `cover-letter.pdf` styled to match the resume letterhead (same Raleway/Lato, same #D44500 accent, same margins) via a `build_cover_letter.py` sibling to `build_resume.py`. The PDF pass goes through `scripts/docx_to_pdf.py` — same LibreOffice-headless path as the resume.
6. Commits on the application branch. The pre-commit hook blocks the commit if any concrete claim is unsourced.

`resume.pdf` and `cover-letter.pdf` are the deliverables — they ship as separate files. Portals that accept two attachments get both; portals that only accept one get the resume. We do not merge the PDFs.

### 5.4 Acceptance criteria

- Every letter names the company and at least one specific product, customer, or recent public announcement — and every such mention has a `company-facts.md` citation.
- No forbidden phrase appears.
- Every experience claim in the letter resolves to a `bullets.yaml` entry.
- `cover-letter.provenance.yaml` has an empty `unsourced_claims`, and `scripts/check_provenance.py` passes.
- Length is within the configured range (hard fail if > 500 words).
- If the agent couldn't find a concrete company detail after its research pass, the hook paragraph cites the JD itself rather than inventing a fact.

## 6. Component 4 — Application tracking

### 6.1 Goal

A single source of truth for "what's happening with this application" that stays in sync with what's actually in the user's inbox, without pestering him to update spreadsheets.

### 6.2 `tracker.yaml` per application

```yaml
company: NVIDIA
role: "Developer Advocate, Agentic Systems"
listing_url: "https://…/jobs/4321098"
applied_via: greenhouse
applied_on: 2026-04-18
referrer: null
portal_url: "https://boards.greenhouse.io/…"
contact:
  recruiter: "Alex Kim <alex@nvidia.com>"
  hiring_manager: null
status: applied      # applied | screened | interviewing | offer | rejected | withdrawn | ghosted
status_history:
  - at: 2026-04-18T14:02-07:00
    status: applied
    source: manual
next_action: "wait 7d for recruiter response; follow up 2026-04-25"
mail_message_ids: []   # RFC-822 Message-Id values captured from Apple Mail
mailbox: "JobSearch/NVIDIA"   # iCloud Mail nested mailbox
notes_ref: notes.md
```

### 6.3 Email integration (iCloud Mail via Apple Mail + AppleScript)

The user reads mail in Apple Mail.app on macOS, signed into their iCloud account. The `tracker-agent` talks to Mail.app through `mcp__Control_your_Mac__osascript`. No app-specific passwords, no IMAP creds on disk — the agent rides the same signed-in session the user already uses.

#### What the agent reads

For each open application, the agent runs an AppleScript query against Mail.app's `INBOX` and the app's `JobSearch/<Company>` mailbox. Matching heuristics (identical to what a Gmail-backed version would use — only the transport changed):

- From-domain matches the company's primary domain (pulled from listing).
- Subject contains the role title OR a recruiter-ATS signature (e.g. `via Greenhouse`).
- Sender matches a short recruiter-domain allowlist (`@greenhouse.io`, `@ashbyhq.com`, `@lever.co`, `@gem.com`, `@gem.com`, `@ripplematch.com`, plus the company's own primary domain).

Each matched message is captured as `{message_id, mailbox, date, subject, from, snippet}`. The `message_id` is the RFC-822 header — stable, unique, and the basis for the `message://<…>` URL that Mail.app honours for deep-linking back to a specific message.

#### What the agent does on a match

1. Classifies the thread with a quick LLM call into one of: **screen request**, **scheduling**, **questions** (eligibility / comp / start-date / technical screen), **rejection**, **offer**, **other**. The `questions` and `scheduling` classifications are routes — they forward to the reply-drafter (§6.7) or the scheduler (§6.8) respectively.
2. Appends a `status_history` entry and updates `status` when a transition is clear (only promotes; only demotes with user confirmation).
3. Writes a one-line entry to `notes.md` that includes the `message://` deep-link (rendered as `message:<URL-encoded-message-id>`), date, sender, and one-sentence summary.
4. Appends the `message_id` to `tracker.yaml` → `mail_message_ids` so the sweep is idempotent.

Replies are never auto-sent. When a reply is warranted, the agent hands the thread to the reply-drafter or scheduler, which stages a draft in Mail.app's Drafts mailbox. The user opens the draft and sends.

#### Mailboxes, not labels

Apple Mail has no Gmail-style labels. The agent creates a nested mailbox `JobSearch/<Company>` on the iCloud account on first match and moves (not copies) matched messages into it. This keeps the user's INBOX clean and lets them re-run the tracker on the mailbox alone. The archiver (§7) moves the mailbox to `JobSearch-Archive/<Company>` when the application closes.

#### Example AppleScript the agent generates

```applescript
tell application "Mail"
  set matches to {}
  repeat with m in (messages of inbox whose sender contains "@greenhouse.io" ¬
                    or sender contains "@nvidia.com")
    set end of matches to {message id:(message id of m) as string, ¬
                           subject:(subject of m), ¬
                           date received:(date received of m) as string}
  end repeat
  return matches
end tell
```

The agent does not hand-write AppleScript for each call — it emits a parameterised query and lets `osascript` run it. The above is illustrative.

### 6.4 Portal-side tracking (best effort)

Some ATSes expose candidate portals. Where a login exists (Greenhouse candidate portal, Lever candidate email threads), the agent stores the `portal_url` but does not log in on its own; it links the user to it when follow-up is due.

### 6.5 Scheduled sweep

A second scheduled task runs every 2 hours: for each application where `status in {applied, screened, interviewing}`, query Apple Mail (via `mcp__Control_your_Mac__osascript`) for messages received since `last_checked_at` in the INBOX and in `JobSearch/<Company>`, update trackers, and produce a morning digest (`dashboard.md` at repo root — regenerated every sweep, not committed). The dashboard is the one thing the user looks at daily.

### 6.6 Acceptance criteria

- Every Apple Mail message related to a tracked company is linked from exactly one tracker within 2 hours of arrival (verified by `mail_message_ids` deduplication).
- No automated send of outbound email — only drafts, staged in Mail.app's Drafts mailbox.
- `dashboard.md` loads in under 1s and lists all non-archived applications grouped by status, with next-action dates.
- Every draft written by the reply-drafter or scheduler shows up in `Mail.app → Drafts` within one sweep cycle.

### 6.7 Recruiter follow-up replies (`reply-drafter`)

When `tracker-agent` classifies a message as **questions**, the thread is handed to `reply-drafter`. Recruiters routinely ask things like: "Are you authorized to work in the US without sponsorship?", "What's your target base?", "When could you start?", "Have you worked with <specific tech>?"

The hard rule is that every personal claim in a reply must trace to `config/personal-facts.yaml` (see §8.7), and every experience claim must trace to `bullets.yaml` or the already-committed resume for that application. If a question asks something the closed universe can't answer, the draft contains `[USER TO ANSWER: <question>]` inline rather than a fabricated answer.

#### Flow

1. Input: the full thread (via Apple Mail AppleScript), `tracker.yaml`, `config/personal-facts.yaml`, the application's committed `resume.docx` + `bullets.yaml`, `voice-corpus/*`.
2. Extract the recruiter's questions. Group by category: eligibility, compensation, availability, technical, logistics, other.
3. For each question, pick the answer from the closed universe. If none, insert the `[USER TO ANSWER: …]` placeholder and do NOT guess.
4. Compose the draft in the user's voice (per §5.2 `voice.yaml` constraints; same `forbidden_phrases`). Keep it short — recruiters scan.
5. Write the draft to `applications/<…>/replies/<YYYY-MM-DD>-<topic>.md` AND stage it as a draft in Mail.app's Drafts mailbox, replying to the original message (preserving `In-Reply-To` and `References` headers so threading works).
6. Emit `replies/<YYYY-MM-DD>-<topic>.provenance.yaml` (see §8.8) mapping every concrete claim to its source.
7. Commit on the application branch.

#### Hard rules

- No draft is ever sent. Only staged. User opens Mail.app → Drafts → reviews → sends.
- A draft containing any `[USER TO ANSWER: …]` placeholder still commits, but the `next_action` in `tracker.yaml` is set to `"recruiter-reply needs user input on <N> question(s)"`.
- Any concrete fact without a provenance entry blocks the commit (see §8.8).

### 6.8 Interview scheduling (`scheduler`)

When `tracker-agent` classifies a thread as **scheduling**, the thread is handed to `scheduler`. Calendar integration uses the Google Calendar MCP the user already has connected (`mcp__8cb1832e-5c3e-45d7-a416-7920a5827a02__*`).

#### Flow

1. Input: the thread, `tracker.yaml`, and access to Google Calendar via `list_calendars`, `list_events`, `suggest_time`.
2. Parse any proposed times out of the recruiter's email. Times are often in one of three shapes: explicit slots ("Tue 4/22 at 10am or 2pm PT"), a Calendly-style link, or an open "when works?" question.
3. Pull the user's existing events from the primary calendar over the candidate window (default: next 10 business days, 9am–6pm PT unless overridden in `config/voice.yaml` → `scheduling_preferences`). Conflicts include any event marked busy.
4. Produce up to three candidate slots, preferring mid-morning or mid-afternoon (avoiding user's hard-no windows if declared in `config/voice.yaml`).
5. Write `schedule/<YYYY-MM-DD>-<event>.yaml` capturing the proposed slots, the parsed source (quoted from the email), and timezone assumptions.
6. Stage a reply draft in Mail.app's Drafts mailbox proposing those slots, with the timezone spelled out.
7. Create a **tentative** event on Google Calendar using `create_event` with `status: tentative` (or the MCP's equivalent), titled `[TENTATIVE] <Company> — <Role> — <Stage>`, description linking to the application folder and the thread's `message://` URL. The event auto-declines nothing on the user's side; it just reserves the block.
8. Once the user sends the draft and the recruiter confirms a slot, the user tells the agent "confirmed <slot>". The scheduler updates the calendar event to confirmed and removes the `[TENTATIVE]` prefix.

If the recruiter sends a Calendly link, the scheduler captures the link in `schedule/*.yaml` and asks the user to book themselves — we don't auto-click through Calendly. The draft reply says "I've picked a slot on your Calendly — see you then" only after the user has booked.

#### Hard rules

- Never create a confirmed calendar event without user acknowledgment. Tentative only, until the user says "confirmed".
- Never reply to the recruiter on the user's behalf without the user sending the Mail.app draft.
- Timezone defaults to PT; if the recruiter specifies another, the reply mirrors theirs and the tentative event is scheduled in the user's local tz (the calendar handles the conversion).

#### Acceptance criteria

- Every parsed candidate slot in `schedule/*.yaml` quotes the source phrase from the email and includes timezone metadata.
- No calendar event is ever created with `status: confirmed` without user confirmation.
- Calendly-link threads produce a draft that acknowledges the link without claiming a time was booked.

## 7. Component 5 — Archiving

### 7.1 When an application archives

Any of:

- `status == rejected` for > 30 days
- `status == withdrawn`
- `status == ghosted` (auto-assigned after 45 days with no movement and at least one follow-up)
- `status == offer` AND user accepts/declines (user flags this manually)

### 7.2 Archive move

`archiver` is a simple, idempotent mover:

1. `git mv applications/<Company>/<Role>-<date>/ archive/<YYYY>/<Company>-<Role>-<date>/`
2. Append a one-line summary to `archive/<YYYY>/index.md` with final status, total elapsed days, and a link to the folder.
3. Commit on `main` with message `archive: <Company> <Role> (<final-status>)`.
4. Move the Apple Mail mailbox `JobSearch/<Company>` → `JobSearch-Archive/<Company>` via AppleScript (messages stay searchable; the "active" sweep only walks `JobSearch/*`).

### 7.3 Learning loop

Once a quarter, an `archive-review` agent reads the year's archive/index.md plus each folder's `fit-notes.md` and `tracker.yaml` and writes `archive/<YYYY>/retro.md`: patterns in which listings converted, which didn't, which bullets recurred in successful applications, suggested edits to `criteria.yaml` and `bullets.yaml`. User reviews the retro and merges any config changes by hand.

### 7.4 Acceptance criteria

- No application is deleted; every archive move is reversible by `git mv` back.
- `archive/<YYYY>/index.md` stays sorted by date and is never > 200 lines for a year.
- The retro agent's suggestions are written as a git patch (`.diff` file), not applied automatically.

## 8. Cross-cutting concerns

### 8.1 Secrets

No secrets in git. `config/secrets.env` (gitignored) holds anything the agents need beyond the workspace MCPs (API tokens for Greenhouse/Lever/Ashby public endpoints are rarely needed; if a private token ever is, it goes here). The spec assumes the user remains signed in to:

- **Apple Mail** — already authenticated to iCloud via the macOS system; the Control-your-Mac MCP uses AppleScript against Mail.app. No app-specific password, no IMAP creds on disk.
- **LinkedIn** and **Google Drive** via their normal Chrome session; Chrome MCP rides those cookies.
- **Google Calendar** via its connected MCP (already authenticated).

Personal-but-not-secret facts used by the reply-drafter (work auth, target base, start date, etc.) live in `config/personal-facts.yaml`, which is gitignored (see §8.7).

### 8.2 Determinism and reruns

Every agent writes to `search/runs/<timestamp>/` or to an application folder and is idempotent. Reruns on the same inputs are safe; reruns with changed inputs produce a new commit with a clear diff. There is no "update in place" that clobbers history.

### 8.3 Human-in-the-loop checkpoints

Two points where the user is always asked before anything external happens:

1. **Before applying** — the user reviews resume + cover letter + answers (if any) and explicitly says "submit". The agents never press Submit on a portal on their own.
2. **Before sending email** — replies to recruiters are staged in Apple Mail.app's Drafts mailbox (via AppleScript `make new outgoing message`); the user opens and sends.
3. **Before a calendar event is confirmed** — the scheduler creates `[TENTATIVE]` Google Calendar events only; promotion to confirmed requires the user saying "confirmed" after the recruiter locks a slot.

Every other step (searching, scoring, tailoring, tracking, archiving) runs without confirmation, because all of it is local and reversible.

### 8.4 Failure modes to watch

- LinkedIn changes DOM — Chrome MCP selectors break. Mitigation: adapter is one file; parser is prompt-based, not XPath-based.
- A recruiter email contains phishing. Mitigation: per MCP link-safety rules, every URL in a tracked email is displayed with its full destination before the user follows it; agent never auto-follows.
- Binary docx diffs look noisy. Mitigation: commit the unpacked OOXML alongside.
- The voice corpus drifts and the letters start sounding templated. Mitigation: the archive-review retro compares the last 10 letters' 3-grams against the corpus and flags convergence.

### 8.5 Out of scope (for v1)

- Auto-filling application forms. The agent produces the artifacts; the user uploads them.
- Salary negotiation support beyond restating `personal-facts.yaml`.
- Recruiter outreach (cold inbound from the user's side).
- Interview prep. Plausible v2; would live at `applications/<…>/interview-prep.md`.
- Sending email. Every reply is a Mail.app draft.
- Accepting a calendar invite without user confirmation.

### 8.6 PDF export toolkit

The spec settles on **LibreOffice headless** for DOCX → PDF because it renders the canonical Raleway/Lato/#D44500 style faithfully on macOS without requiring Microsoft Word, and because it works in CI (unlike `docx2pdf` which shells out to Word.app). The decision is committed; revisit only if a specific fidelity bug appears.

One script lives in `scripts/`:

```
scripts/docx_to_pdf.py    resume.docx → resume.pdf via `libreoffice --headless --convert-to pdf`
```

Pure wrapper — single file, no hidden state. Run it for both `resume.docx` and `cover-letter.docx`; the two PDFs are the deliverables and ship as separate files. We don't combine them — portals accept either one or both attachments, and splitting them keeps the artifacts diffable.

Install note: `brew install libreoffice` on first setup. Record the installed version in this file when Phase 2 lands.

### 8.7 Personal facts and sensitive data

`config/personal-facts.yaml` is the closed universe of personal claims the reply-drafter is allowed to assert. It's gitignored; a committed template at `config/personal-facts.example.yaml` shows the expected shape:

```yaml
eligibility:
  us_work_auth: "us-citizen"          # or: "permanent-resident", "h1b", "o1", "requires-sponsorship"
  sponsorship_needed: false
  clearance: null                      # e.g. "secret", "top-secret", or null

compensation:
  target_base_usd: [200000, 260000]   # min, max
  target_total_comp_usd: [260000, 360000]
  equity_required: false
  bonus_expectations: null

availability:
  earliest_start_date: "2026-06-01"
  notice_period_days: 14
  scheduling_hours_pt: { start: "09:00", end: "17:30" }
  scheduling_hard_nos: ["Fri 15:00-17:00"]

location:
  base_city: "San Francisco, CA"
  willing_to_relocate_to: ["New York, NY", "Seattle, WA"]
  hard_no_cities: []
  remote_preference: "hybrid"         # or "remote", "onsite"

work_history_disclosure:
  reason_for_leaving_last: "…short line…"
  reference_contacts_available: true
```

Rules:

- The file is never committed. A pre-commit check blocks any attempt to add `config/personal-facts.yaml` to the index (enforced via `.gitignore` plus a guard in `scripts/check_provenance.py`).
- The reply-drafter reads this file and only this file for personal claims. If a recruiter asks something the file doesn't answer, the draft inserts `[USER TO ANSWER: <question>]` — never a plausible-sounding guess.
- The user maintains this file by hand. The agents do not write to it.
- The `.example.yaml` is the canonical schema reference — any new field must be added there (with placeholder values) first.

### 8.8 Provenance and the no-hallucination guarantee

This is the hard-block enforcement that makes the system safe to trust on a real application cycle. Every output file that makes concrete claims has a sibling `.provenance.yaml` mapping each claim to a source, and a pre-commit hook refuses to commit if any claim is unsourced.

#### The claim universe

A "concrete claim" is any one of:

- **Experience claim** — a bullet, skill, or summary sentence asserting the user did, built, or measured something. Source must be an ID in `bullets.yaml` or a verbatim passage in the generalised resume template.
- **Company fact** — a product name, customer name, funding round, dollar figure, person, or announcement attributed to the target company. Source must be `applications/<…>/company-facts.md` with a fetched URL. The cover-letter-writer is responsible for populating company-facts.md in a research pass before drafting.
- **Personal fact** — work authorization, comp expectations, start date, relocation willingness, and any other answer to a recruiter question about the user. Source must be a key path in `config/personal-facts.yaml`.
- **Voice claim** — a sentence whose rhythm/vocabulary was lifted from the user's own prior writing. Source must be a path into `voice-corpus/`.

Sentences without concrete claims (connective tissue, transitions, restatements of the JD) do not need provenance entries.

#### Provenance schema

```yaml
# applications/<…>/resume.provenance.yaml
output: resume.docx
generated_at: 2026-04-18T15:02:00-07:00
claims:
  - output_field: "summary.sentence[1]"
    text: "Drove Cypress coverage to 90% on Slack's web platform."
    source: "bullets.yaml#slack-cypress-90"
    source_text: "Drove Cypress coverage to 90% on the web platform, catching regressions pre-merge."
    confidence: high
  - output_field: "role[Slack].bullet[1]"
    text: "Built working reference implementations for the Slack Web API, adopted as official examples."
    source: "bullets.yaml#slack-webapi-refimpl"
    confidence: high
unsourced_claims: []   # MUST be empty for commit to succeed
```

Cover-letter and reply provenance files follow the same shape, with sources pointing into `company-facts.md`, `personal-facts.yaml`, or `voice-corpus/`.

#### The CI check (`scripts/check_provenance.py`)

Pre-commit hook, installed via `.git/hooks/pre-commit`. On every commit that touches `applications/*`:

1. For each tailored resume, cover letter, or reply in the staged diff, load the sibling `.provenance.yaml`.
2. For each entry in `claims[]`, resolve the `source`:
   - `bullets.yaml#<id>` → find a bullet with that ID and compare `source_text` to the referenced bullet; warn if they've drifted.
   - `company-facts.md:L<n>` → confirm the line exists and contains a URL.
   - `personal-facts.yaml:<key.path>` → confirm the key resolves and the value matches what's in the claim.
   - `voice-corpus/<file>.md:L<n>` → confirm the file and line exist.
3. For each concrete claim actually in the output (re-extracted from the docx/md), confirm it appears in `claims[]`. Any output-side claim not in `claims[]` counts as unsourced.
4. `unsourced_claims` must be empty. The `[USER TO ANSWER: …]` placeholder pattern is whitelisted — it is not a claim, it's an explicit deferral.
5. Exit non-zero on any failure. Print the offending output field + claim text + why it failed.

#### Agent-side discipline

Agents are instructed: when an ungrounded claim would be the natural next sentence, STOP and write `[NEEDS SOURCE: <what you were about to claim>]` inline instead of fabricating. The commit will fail until either the user adds the source to the appropriate sidecar or the sentence is rewritten. This is the defensive posture: fail loudly, never fill the gap with a plausible guess.

#### Acceptance

- `scripts/check_provenance.py` is callable standalone (not just as a hook) and returns exit code 0 on a clean application, non-zero with a clear diagnostic on any violation.
- No resume, cover letter, or reply ever ships without a passing provenance file.
- User can disable the hook temporarily with `git commit --no-verify` **only with explicit intent** — CLAUDE.md §6 forbids the agent from ever running commits with `--no-verify`.

## 9. Agent prompt sketches

These are starting points, not final prompts. Each will live at `agents/<name>.md` in the repo and be loaded by the Cowork / Claude Code invocation that runs the agent.

### 9.1 `search-agent`

> You are a job-search agent for W.S. Gong. Read `config/criteria.yaml` and `config/sites.yaml`. For each site, execute its strategy (chrome-mcp | web-fetch | api). Normalise every listing to the schema in §3.4. De-dupe against `search/seen.db`. Write one `listings.jsonl` to a fresh `search/runs/<timestamp>/` folder. Do not score, rank, or drop listings — that is the fit-scorer's job. Log every adapter's raw response under `raw/` for debugging. Commit nothing.

### 9.2 `resume-tailor`

> You tailor W.S. Gong's resume for one listing. Read the listing, `bullets.yaml`, `WSGong_Resume_Template.docx`, and `docs/resume-style-spec.md`. Produce `resume-plan.yaml` selecting: a rewritten summary (≤ 3 sentences), an ordering of skill categories, and 2–4 bullet IDs per role. Hard rule: every claim must trace to an existing bullet or the generalized resume. If you are about to write a sentence you cannot cite to a `bullets.yaml` ID, STOP and write `[NEEDS SOURCE: <claim>]` instead — never fill the gap with a plausible guess. Then call `build_resume.py --plan resume-plan.yaml` to emit `resume.docx` in the application folder. Emit `resume.provenance.yaml` per §8.8. Commit on branch `app/<slug>`; the pre-commit hook will block you if any claim is unsourced.

### 9.3 `cover-letter-writer`

> Draft a 300–400 word cover letter for this listing in W.S. Gong's voice. BEFORE drafting, populate `applications/<…>/company-facts.md` with every concrete fact you plan to cite and the URL you got it from — no citation, no citing. Read the listing, the tailored resume, `voice-corpus/*`, `config/voice.yaml`, and your own company-facts.md. Three paragraphs: concrete hook, evidence bridge, direct close. Never use any `forbidden_phrases`. Cite one specific product, customer, or announcement by name from company-facts.md — if your research pass found nothing concrete, fall back to a JD-specific detail and cite listing.md. Output `cover-letter.md`, emit `cover-letter.provenance.yaml`, render `cover-letter.pdf`. Commit. If you're about to write a sentence with a concrete noun you can't cite, stop and write `[NEEDS SOURCE: <noun>]` inline — the pre-commit hook will block the commit until it's resolved.

### 9.4 `tracker-agent`

> For every application with status in {applied, screened, interviewing}, query Apple Mail (via `mcp__Control_your_Mac__osascript`) for messages received since `last_checked_at` in the INBOX and in `JobSearch/<Company>`, matching the company's domain or recruiter-ATS signatures. Classify each thread into: screen request, scheduling, questions, rejection, offer, or other. Update `tracker.yaml` (promote-only) and append to `notes.md` with the `message://` deep-link. For **scheduling** threads, hand off to `scheduler`. For **questions** threads, hand off to `reply-drafter`. Never send email — only stage drafts. Regenerate `dashboard.md` at repo root.

### 9.5 `archiver`

> Move any application matching §7.1 conditions from `applications/` to `archive/<YYYY>/`. Append to `archive/<YYYY>/index.md`. Rename the Apple Mail mailbox `JobSearch/<Company>` → `JobSearch-Archive/<Company>` via AppleScript. Commit on `main`.

### 9.6 `reply-drafter`

> A recruiter email has been classified as **questions**. Read the thread, `config/personal-facts.yaml`, the committed `resume.docx` and `bullets.yaml` for this application, and `voice-corpus/*`. Extract each question and answer ONLY from the closed universe: personal claims from `personal-facts.yaml`, experience claims from `bullets.yaml` / the committed resume, tone from `voice-corpus/`. For any question not answerable from those sources, insert `[USER TO ANSWER: <question>]` in the draft — do not guess. Write `applications/<…>/replies/<YYYY-MM-DD>-<topic>.md` and stage the corresponding draft in Mail.app's Drafts mailbox, preserving `In-Reply-To` and `References` headers. Emit `replies/<YYYY-MM-DD>-<topic>.provenance.yaml`. Set `tracker.yaml → next_action` to flag any outstanding user placeholders. Commit. Never send.

### 9.7 `scheduler`

> A recruiter email has been classified as **scheduling**. Read the thread, `tracker.yaml`, and `config/voice.yaml` (for scheduling preferences). Use the Google Calendar MCP to list the user's events over the next 10 business days. Parse proposed slots (or detect a Calendly link, or an open "when works" question). Produce up to three candidate slots that don't conflict; write `applications/<…>/schedule/<YYYY-MM-DD>-<event>.yaml` with parsed-source phrases quoted. Stage a reply draft in Mail.app proposing those slots with explicit timezone. Create a **tentative** Google Calendar event titled `[TENTATIVE] <Company> — <Role> — <Stage>`, description linking back to the application folder and the Mail.app thread. Never confirm a slot without explicit user acknowledgment. Never auto-book Calendly links. Commit the schedule YAML.

### 9.8 `url-ingest` (utility, not a full agent)

> Given a single listing URL, detect the source (LinkedIn, Greenhouse, Lever, Ashby, or generic). Parse the listing into the §3.4 schema — for LinkedIn, use the Chrome MCP against the user's signed-in session; for ATS URLs, use the public API; for anything else, WebFetch + prompt-based extraction. Bypass `seen.db` (this is a user-initiated ingest). Write `applications/<Company>/<Role>-<YYYY-MM-DD>/listing.json` + `listing.md`, create branch `app/<…>`, commit the raw listing, and hand off to `resume-tailor`.

## 10. Rollout plan

A staged build — each phase is shippable on its own.

- **Phase 1 (week 1):** repo init + `criteria.yaml`, `sites.yaml` for Greenhouse/Lever/Ashby APIs only, `search-agent`, `fit-scorer`, `summary.md`. No tailoring yet. Proves the top-of-funnel.
- **Phase 2 (week 2):** `bullets.yaml` built out from existing template + NVIDIA/Vercel/Handshake tailored resumes. `resume-tailor` + `build_resume.py --plan` extension. `scripts/docx_to_pdf.py` (§8.6) lands with this phase. `scripts/url_ingest.py` (§3.8) also lands here — it's an on-ramp into tailoring. `scripts/check_provenance.py` (§8.8) starts out warning-only; flip it to a blocking pre-commit hook once resume provenance is stable. Manual cover letters for now.
- **Phase 3 (week 3):** `voice-corpus/` seeded; `cover-letter-writer` + `build_cover_letter.py`. `company-facts.md` research pass enforced. Provenance hook extended to cover letters (blocking). End-to-end auto-tailoring on branch; user merges on approval.
- **Phase 4 (week 4):** `tracker-agent` + Apple Mail AppleScript watcher + `dashboard.md`. Scheduled sweeps on. `reply-drafter` (§6.7) and `scheduler` (§6.8) ship alongside the tracker — replies need `config/personal-facts.yaml` in place first; scheduler needs the Google Calendar MCP configured. Provenance hook extended to reply drafts (blocking).
- **Phase 5 (week 5):** `archiver` + `archive-review` retro. Migrate the existing `NVIDIA/`, `Vercel/`, `Handshake/`, `APublicSpace/`, `MarineLayer/`, `SFMOMA/` folders into `applications/` format.

## 11. Open questions

1. Do you want the dashboard surfaced as a Notion database mirror (read-only, rebuilt from `tracker.yaml` files) or is a local `dashboard.md` enough? The hybrid adds complexity; the spec currently assumes not.
2. `comp_floor_usd` — is 180k right, or should Phase 1 run without any comp filter while we see what the corpus looks like?
3. For LinkedIn specifically: are "Easy Apply" listings in scope, or only listings that route out to a company ATS? Easy Apply needs special-cased tailoring since it takes a PDF upload and a handful of inline fields. The URL-ingest path (§3.8) currently produces the listing either way — the open question is about the apply flow, not discovery.
4. Cover letter PDF letterhead — match the resume exactly, or a slimmer top strip (name + one line of contact)? I'd default to slimmer.
5. Retention: how long does `search/runs/` keep raw HTML? The spec silently assumes forever; a 30-day broom may be kinder to the repo.
6. `config/personal-facts.yaml` — review the §8.7 schema and decide what you're comfortable having the reply-drafter answer automatically. Everything not in the file becomes `[USER TO ANSWER]` placeholders — which is the safe default but costs you more turnarounds with recruiters.
7. Scheduling window defaults — currently 9am–6pm PT, next 10 business days. Override via `config/voice.yaml → scheduling_preferences`?
8. Company research depth for cover letters — the research pass currently fetches homepage + /products + /customers + 6 months of /blog. Enough? Too much? Any companies where that's likely to return garbage?
9. Combined-PDF ordering — resume first, cover letter second. Flip it for employers that want the cover letter on top?
10. Provenance strictness in early phases — the hook ships warning-only in Phase 2 and flips to blocking before Phase 3 lands. Comfortable with that ramp, or should it be blocking from day one?

---

*End of spec. File lives at `Resumes/job-search-agent-spec.md`. Edit freely; diffs are how this gets better.*
