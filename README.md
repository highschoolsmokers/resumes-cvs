# Résumés & CVs

Given one or more job descriptions, the tool produces a tailored résumé and cover
letter for each, and keeps a LinkedIn profile in step with the master résumé.
Every claim traces to your own material; nothing is invented, nothing is
auto-submitted. Markdown-first: no scraping, no queue, no tracker.

## Where things live

- **[`SPEC.md`](SPEC.md)** — the system: workflow, cover-letter shape, LinkedIn sync, implementation.
- **`profile.md`** — you: goal, positioning, targeting, résumé style, voice, channel.
- **`master-resume.md`** — the source-of-truth résumé; tailoring subtracts and reorders from it.
- **`CLAUDE.md`** — session-loaded pointer to `SPEC.md`.

## Setup

```bash
brew install --cask libreoffice font-inter
python3 -m venv .venv && .venv/bin/pip install python-docx PyYAML pypdf
```

`build_cover_letter.py` and `merge_pdfs.py` run via `.venv/bin/python`; the rest
on system `python3` (3.11+). Full commands are in SPEC "Implementation".

## One listing

```bash
python3 scripts/url_ingest.py "<greenhouse|lever|ashby URL>" --no-commit
```

Then, in Claude Code: tailor `resume.md` from the matching base, write and approve
the cover letter, render both to PDF, and merge. LinkedIn and generic URLs come
back as stubs needing a browser fetch or a pasted JD.

## A batch

```bash
/batch-apply <url1> <url2> ...
```

Ingests all URLs, tailors each in parallel, renders every PDF in one LibreOffice
pass, and prints a review table. Nothing is submitted.

## LinkedIn sync

```bash
python3 scripts/linkedin_export.py --target education --out linkedin-profile.md --json linkedin-profile.json
python3 scripts/linkedin_apply.py                        # dry-run: shows every change, saves nothing
python3 scripts/linkedin_apply.py --commit --experience  # applies, confirming before each save
```

`linkedin_export.py` maps `master-resume.md` onto LinkedIn's fields at its
character limits. `linkedin_apply.py` pushes headline, About, and experience
descriptions onto the live profile via real Chrome (needs Playwright + Chrome).
Own profile only; dry-run by default; confirms before each save. Automating
profile edits crosses LinkedIn's terms — one-time, supervised, self-owned use.

## Two rules the tool never breaks

1. **Grounded.** Every résumé line traces to `master-resume.md` or a base; every cover-letter fact to the JD or durable knowledge. Unsourced → `[NEEDS SOURCE]`, and the build refuses to render.
2. **You submit.** Uploading applications and sending outreach are manual. The one live action is the LinkedIn sync — your own profile, confirmed per save.

## License

MIT. See `LICENSE`.
