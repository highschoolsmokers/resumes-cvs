# Résumés & CVs — a fast, grounded job-application tailor

Bring a job-listing URL (or a list of them). Get back a tailored résumé PDF and
a cover-letter PDF per listing, in a house Swiss/Inter style, with every claim
traceable to a file you control — no hallucinated bullets, no invented company
facts. **You** upload the applications; the tool never submits.

Markdown-first and deliberately small: no scraping pipeline, no queue, no
tracker. See `SPEC.md` for the full design and `CLAUDE.md` for the operating
playbook.

## One listing

```bash
# 1. Ingest the URL (Greenhouse / Lever / Ashby fetch via their APIs, no browser).
python3 scripts/url_ingest.py "https://job-boards.greenhouse.io/acme/jobs/12345" --no-commit
```

Then, in Claude Code: tailor `resume.md` (copy the matching target base and
light-tune it to the JD) and write `cover-letter.md`, and render:

```bash
python3 scripts/render_resume.py --input applications/Acme/<role>-<date>/resume.md --out applications/Acme/<role>-<date>/resume.pdf
.venv/bin/python scripts/build_cover_letter.py --input applications/Acme/<role>-<date>/cover-letter.md --out applications/Acme/<role>-<date>/cover-letter.docx
python3 scripts/docx_to_pdf.py applications/Acme/<role>-<date>/cover-letter.docx
```

## A list of listings

In Claude Code, paste the URLs to the `/batch-apply` command:

```
/batch-apply <url1> <url2> <url3> ...
```

It ingests all of them (`scripts/batch_ingest.py`), fans out one tailoring worker
per listing in parallel, renders every PDF in a single LibreOffice pass, and
prints a review table. LinkedIn / generic URLs come back as stubs that need a
browser fetch or a pasted JD. Nothing is submitted.

## The pieces

- `master-resume.md` — the real résumé superset; source of truth. Tailoring subtracts and reorders, never invents.
- `resume-devdocs.md` / `resume-education.md` / `resume-fde.md` / `resume-qa.md` — four target bases; the first three are generated from the master via `render_resume.py --emit-base`.
- `voice.md` (+ private `voice/` samples) — cover-letter voice, letterhead, length, forbidden phrases.
- `applications/<Company>/<role-slug>-<date>/` — one folder per job (gitignored).
- `scripts/` — `url_ingest.py`, `batch_ingest.py`, `render_resume.py`, `build_resume.py`, `build_cover_letter.py`, `docx_to_pdf.py`, `lint_resume.py`; LinkedIn: `linkedin_export.py`, `linkedin_apply.py`, `linkedin_selectors.py`, `linkedin_browser_probe.py`.
- `resume-template.docx` — the Swiss/Inter master the engine renders into.

## LinkedIn profile sync

Keep the LinkedIn profile in step with the master résumé. Same grounding rule:
the profile copy is generated from `master-resume.md`, never hand-invented.

```bash
# 1. Generate the LinkedIn-field copy from the master (headline/About/experience/skills),
#    within LinkedIn's char limits and voice rules. --json feeds the driver.
.venv/bin/python scripts/linkedin_export.py --target education \
    --out linkedin-profile.md --json linkedin-profile.json

# 2. Dry run (default): opens real Chrome, fills fields, screenshots, saves NOTHING.
.venv/bin/python scripts/linkedin_apply.py                    # Headline + About
.venv/bin/python scripts/linkedin_apply.py --experience --fields ""   # position descriptions

# 3. Commit for real — asks before each Save (drop --yes to confirm each one).
.venv/bin/python scripts/linkedin_apply.py --experience --commit
```

LinkedIn has no write API, so the driver uses Playwright + real Chrome. First
run opens a window to log in once (session persists in the gitignored
`.linkedin-chrome-profile/`). It never submits silently: dry-run is the default
and every save is confirmed. Selectors live in `linkedin_selectors.py` — the one
file to edit if LinkedIn's DOM changes; `linkedin_browser_probe.py` re-checks the
launch strategy. Requires `playwright` (in `requirements.txt`) and Google Chrome.

## Setup

```bash
brew install --cask libreoffice font-inter        # PDF render + embedded font
python3 -m venv .venv && .venv/bin/pip install python-docx PyYAML   # for build_cover_letter.py
```

`build_cover_letter.py` runs via `.venv/bin/python`; the other scripts run on
system `python3`.

## Two rules the tool never breaks

1. **Every concrete claim is grounded.** Résumé lines trace to `master-resume.md` / a base; cover-letter facts to the JD or durable knowledge. Unsourced → flagged `[NEEDS SOURCE]`, and `build_cover_letter.py` refuses to render.
2. **You submit.** Uploading an application and sending any outreach are always manual. The tool produces artifacts; you cross the line.

## License

MIT. See `LICENSE`.
