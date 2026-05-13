# scripts/

Deterministic drivers for the job-search pipeline. All Python lives here; one
directory, flat layout, grouped below by purpose. Agents (`agents/*.md`)
drive these scripts but never reimplement what they do.

The pre-commit hook (`.githooks/pre-commit`) runs the linters (provenance,
bullets, resume, agents) on every commit. Install once per clone:
`bash scripts/install_provenance_hook.sh`.

## Build (markup → DOCX / PDF)

| Script | Purpose |
| ------ | ------- |
| `scripts/build_resume.py` | Render `resume.docx` from a plan + `bullets.yaml`. `--no-unpacked` skips the OOXML sibling (used by `/apply`); calls `lint_resume.py` inline. |
| `scripts/build_cover_letter.py` | Render `cover-letter.docx` from `cover-letter.md`. Refuses on `[NEEDS SOURCE: …]` or word-count overrun. |
| `docx_to_pdf.py` | Headless LibreOffice; accepts multiple inputs in one batch (saves the cold-start cost). |
| `merge_pdfs.py` | `pypdf` combine into `combined.pdf`. Not used by `/apply` (resume + cover ship as separate files); kept for portals that demand a single attachment. |

## Apply pipeline

| Script | Purpose |
| ------ | ------- |
| `url_ingest.py` | URL → `applications/<Co>/<role-slug>-<date>/listing.{json,md}` + branched + auto-committed. Greenhouse / Lever / Ashby via API; LinkedIn stubs for Chrome MCP fill; generic stubs for user paste. |
| `queue_add.py` | Append a URL to `queue.jsonl` (gitignored). Validates URL shape; rejects duplicates against `queue.history.jsonl`. |
| `apply_queue.py` | Drainer. Invokes `claude -p '/apply <url>'` per entry. Distinguishes infra vs URL failures; flocks against concurrent drains; resets to main between entries (detaches if main is checked out in another worktree). |
| `queue_status.py` | Markdown summary of pending / completed-24h / failed. Inlined into `dashboard.md`. |

## Closed-universe data layer

| Script | Purpose |
| ------ | ------- |
| `build_index.py` | Build `state/embeddings.npz` over `bullets.yaml` + `voice-corpus/` using `sentence-transformers/all-MiniLM-L6-v2`. Idempotent on sha + mtime. |
| `retrieve.py` | Top-K cosine query over the index. JSONL on stdout. Agents call this before reading full files. |
| `bullets_lookup.py` | Human grep over `bullets.yaml` by `--tag` / `--family` / `--role` / `--keyword`. |
| `extract_bullets.py` | Walk every `resume.docx` under `applications/` and the generalized resume; dump paragraphs for hand-curation into `bullets.yaml`. |
| `backprop_edits.py` | Detect bullets whose `bullets.yaml` text doesn't appear verbatim in a tailored `resume.docx`. Detection-only today; in-place YAML rewrite is a follow-up. |

## Tracker + dashboard

| Script | Purpose |
| ------ | ------- |
| `sweep.py` | Walk every open `tracker.yaml`, query Apple Mail via `osascript`, emit `sweep/runs/<ts>/batch.jsonl`. The tracker-agent reads the batch and classifies. |
| `dashboard.py` | Rebuild `dashboard.md` from every `tracker.yaml`. Inlines queue status + bullet leaderboard. |
| `bullet_outcomes.py` | Pure derived view: `bullets.yaml × *.provenance.yaml × tracker.yaml` → `state/bullet_outcomes.{csv,md}`. Surfaces top-N bullets by interview rate. |

## Linters / provenance gate

| Script | Purpose |
| ------ | ------- |
| `check_provenance.py` | The hallucination guard. Every claim in a `.provenance.yaml` must resolve. `--warn` for repo-wide audit; `--block` (used by the pre-commit hook) for the gate. |
| `lint_bullets.py` | Structural lint over `bullets.yaml`: unique ids, role refs resolve, role families known, summary `built_from` resolves, coverage. |
| `lint_resume.py` | Whole-document Swiss consistency on a `.docx` or unpacked OOXML: single Inter family, approved size scale, 60-DXA baseline spacing, uniform cell padding. |
| `lint_agents.py` | Drift gate on `agents/*.md`: frontmatter parseable, file refs resolve, §-refs resolve in spec/CLAUDE.md, no opaque MCP hashes, has an `## Acceptance` section. |

## Setup (run once per clone or per machine)

| Script | Purpose |
| ------ | ------- |
| `install_provenance_hook.sh` | `git config core.hooksPath .githooks`. **Required** — without it, the provenance gate isn't enforced on commit. |
| `install_apply_skill.sh` | Copy `.claude/skills/apply/` into the Cowork user-skills dir so new tasks discover the `/apply` skill. Optional; Cowork only. |
| `install_apply_queue_schedule.sh` | Prints the `mcp__scheduled-tasks__create_scheduled_task` invocation that registers the apply-queue drainer (every 30 min by default). Run from an interactive Claude Code session. |
