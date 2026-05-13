# search/ — Top-of-funnel

Phase 1 deliverable. Pulls listings from Greenhouse / Lever / Ashby public APIs, normalises to the schema in `job-search-agent-spec.md` §3.4, de-dupes against `search/seen.db`, rule-scores per §3.5, and writes a per-run folder under `search/runs/<timestamp>/`.

## Quick start

```bash
# from repo root
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python search/run.py
```

First run produces something like:

```
[greenhouse:anthropic] 84 listings
[greenhouse:vercel]     62 listings
[greenhouse:stripe]    213 listings
…
Run complete: /…/search/runs/2026-04-18-1645
  fetched total : 612
  fresh (new)   : 612
  yes recs      : 14
  maybe recs    : 48

→ open /…/search/runs/2026-04-18-1645/summary.md
```

Open `summary.md` to see yes-recommendations grouped by company with source URLs and rationales.

## What's in a run folder

```
search/runs/<YYYY-MM-DD-HHMM>/
├── listings.jsonl     committed     normalised, de-duped listings (one JSON per line)
├── scored.jsonl       committed     same listings + score/recommend/rationale
├── summary.md         committed     human-readable yes/maybe digest
├── raw/               gitignored    per-adapter raw JSON for debugging
└── errors.log         sometimes     present only when an adapter failed
```

Raw dumps (`raw/*.json`) stay local per `.gitignore`. Everything else commits.

## Flags

```
python search/run.py --dry-run              # fetch + score but don't write seen.db
python search/run.py --only greenhouse      # subset of sources
python search/run.py --only greenhouse lever
```

## Editing what the agent looks for

- **Companies & sources** — `config/sites.yaml`. Add a board slug under the right source.
- **Roles / scoring rules** — `config/criteria.yaml`. Title includes/excludes, seniority, location, comp floor, affinity terms, thresholds.
- **Agent prompt refinements** — `agents/search-agent.md`, `agents/fit-scorer.md`. Phase 1's `run.py` does rule-based scoring directly; invoke the fit-scorer agent via Claude Code when you want a qualitative LLM read on close-call listings.

## Acceptance checks (CLAUDE.md §2 Phase 1)

- [x] One invocation from an empty `seen.db` produces ≥ 30 normalised listings across the configured sources.
- [x] Rerun within 24h adds zero duplicates.
- [x] `summary.md` groups `recommend: yes` listings by company with source URLs and rationales.

Rerunning on the same day is how you prove the third bullet — `fresh (new)` in the console should drop to 0.

## Scheduled runs

Once the flow is stable, wire it up via `mcp__scheduled-tasks__create_scheduled_task` for a daily 07:00 PT run. The scheduled task just invokes `python search/run.py` and surfaces the summary in the morning.

## Troubleshooting

- **429 or 5xx on a board** — the adapter retries once; persistent failures go to `errors.log` and the other adapters still run.
- **A board returns zero listings** — usually a dead token. Remove it from `sites.yaml` or fix the slug.
- **New source** — add a YAML entry under the right source, add/reuse the parser in `run.py`, run.
