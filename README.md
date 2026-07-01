# Résumés & CVs — a fast, grounded job-application tailor

Bring a job-listing URL (or a list of them). Get back a tailored résumé PDF and
a cover-letter PDF per listing, in a house Swiss/Inter style, with every claim
traceable to a file you control — no hallucinated bullets, no invented company
facts. **You** upload the applications; the tool never submits.

Markdown-first and deliberately small: no scraping pipeline, no queue, no
tracker.

## The single source of truth

Everything — the design, the operating playbook, and the cover-letter voice —
lives in **[`SPEC.md`](SPEC.md)**. Start there:

- **What it is & why** — SPEC §§1–10
- **How to run it** (setup, the one-listing and batch workflows, conventions) — SPEC §16
- **Cover-letter shape + voice** — SPEC §11 and §17
- **Résumé style** — SPEC §13

`CLAUDE.md` is a thin session-loaded pointer to `SPEC.md`.

## Setup (short version)

```bash
brew install --cask libreoffice font-inter                              # PDF render + embedded font
python3 -m venv .venv && .venv/bin/pip install python-docx PyYAML pypdf  # for build_cover_letter.py / merge_pdfs.py
```

`build_cover_letter.py` and `merge_pdfs.py` run via `.venv/bin/python`; the other
scripts run on system `python3`. Full commands are in SPEC §16.

## Two rules the tool never breaks

1. **Every concrete claim is grounded.** Résumé lines trace to `master-resume.md` / a base; cover-letter facts to the JD or durable knowledge. Unsourced → flagged `[NEEDS SOURCE]`, and `build_cover_letter.py` refuses to render.
2. **You submit.** Uploading an application and sending any outreach are always manual. The tool produces artifacts; you cross the line.

## License

MIT. See `LICENSE`.
