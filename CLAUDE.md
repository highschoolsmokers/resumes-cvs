# CLAUDE.md — operating playbook (v2)

How to work in this repo. **Read `SPEC.md` first** — it's the single source of
truth for *what* this system is and every content/voice rule. This file is *how*
to operate it. If the two ever disagree, SPEC.md wins; fix this file.

The v1 pipeline (search agent, apply queue, tracker/scheduler, provenance git
gate, 8 tailoring agents, `bullets.yaml`) is **retired** — see `SPEC.md` §14 and
`archive/v1/`. Do not resurrect it.

## What this is

You bring a job listing (a URL, or several); the system turns out a tailored
résumé PDF + cover-letter PDF per listing, grounded in real material, fast. The
human uploads them. Nothing is auto-submitted.

## The files

- `master-resume.md` — the REAL résumé superset; source of truth. Tailoring **subtracts and reorders**, never invents.
- `resume-devdocs.md` / `resume-education.md` / `resume-fde.md` / `resume-qa.md` — the four target bases (SPEC §10). The first three are generated from the master (`render_resume.py --emit-base`); `resume-qa.md` is hand-maintained. A tailored application copies the matching base and light-tunes it to the JD.
- `voice.md` — cover-letter voice + letterhead/length/forbidden-phrase config. `voice/` — his real letters (gitignored).
- `applications/<Company>/<role-slug>-<YYYY-MM-DD>/` — one folder per job (gitignored): `listing.{json,md}`, `resume.md`+`.pdf`, `cover-letter.md`+`.pdf`.
- `resume-template.docx` — the Swiss/Inter master the engine renders into. `SPEC.md`, this file.

## The scripts (`scripts/`)

- `url_ingest.py <URL> --no-commit` — one URL → `listing.{json,md}`. Greenhouse/Lever/Ashby via ATS APIs (no browser); LinkedIn/generic → a stub flagged for a browser fetch or a pasted JD.
- `batch_ingest.py <URL…>` — many URLs → a JSON manifest (folders + stub flags). No git.
- `render_resume.py --input <resume.md> --out <pdf>` — render a tailored résumé. Also `--target <t>`, `--emit-base`, `--docx-only`.
- `build_cover_letter.py --input <md> --out <docx>` — needs `python-docx`; **run via `.venv/bin/python`**. Reads `voice.md`; aborts on `[NEEDS SOURCE]`.
- `docx_to_pdf.py <docx…>` — many docx → PDF in **one** LibreOffice run. **Never run two `soffice` processes at once.**
- `lint_resume.py <docx>` — Swiss-style linter (manual check).

## The two workflows

- **One URL, by hand:** `url_ingest.py <url> --no-commit` → tailor `resume.md` (copy the target base, light-tune) → write `cover-letter.md` (SPEC §11) → render (`render_resume.py --input`, `build_cover_letter.py` via `.venv`, `docx_to_pdf.py`).
- **A list of URLs:** the `/batch-apply` command (`.claude/commands/batch-apply.md`) — ingest → fan out one `batch-apply-worker` subagent per listing → one batched render → review table.

## Conventions

- **Naming:** lowercase kebab, ISO dates — `senior-dx-engineer-2026-07-01/`. Company folder keeps its name.
- **Branches:** `main` is always submittable. Do feature work on a branch; fast-forward `main` and push when done. Never `git push --force` to `main`.
- **Commits:** `<area>: <verb> <object>`, one logical change each. End messages with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`. Commit only when asked.
- **Git identity:** local to this repo (`git config user.name/.email`, no `--global`). Default `W.S. Gong <billygong@me.com>`.
- **`.gitignore`:** `applications/*` (except `_template/`), `voice/`, `.venv/`, `.DS_Store`, populated `config/`. Never commit private working content or a rendered PDF you didn't mean to. If you need to track something under a gitignored path, refactor the path — don't add an exception.

## Environment

- Python 3.11+. `.venv` (gitignored): `python3 -m venv .venv && .venv/bin/pip install python-docx PyYAML`. Only `build_cover_letter.py` needs it; the other scripts run on system `python3`.
- LibreOffice for PDF (`brew install --cask libreoffice`); Inter font (`brew install --cask font-inter`) embedded at build time.
- Fetching: ATS APIs need no browser. LinkedIn/generic listings need a Chrome/Playwright fetch or a pasted JD (they ingest as stubs until then).

## Trust boundary (never cross)

- **Never submit an application.** Produce the PDFs; the human uploads them.
- **Never send an email or outreach message.** Draft only.
- These hold in the batch flow too. See `SPEC.md` §8.

## What not to do

- **Don't invent.** Every résumé line traces to a base / `master-resume.md`; every cover-letter fact to the JD or durable knowledge. If you can't source it, write `[NEEDS SOURCE: …]` and stop — `build_cover_letter.py` refuses to render with it, and that's the point.
- **Don't grade his own prose** ("so the test plans read clearly," "keeps the bug reports sharp") — SPEC §12 self-assessment flourishes. State the credential/artifact plainly.
- **Don't use em-dashes** in job-search prose (résumés, cover letters). Colons, semicolons, parens, periods; en-dashes for ranges. (His literary voice uses them — a different register.)
- **Don't quote a company's marketing/news** back at them in a cover letter. Ever. Open with his own framing.
- **Don't change the résumé font, accent, or template** without sign-off. Refer to him as **W.S. Gong** in résumé/CV contexts.
- **Don't resurrect v1** (queue, tracker, provenance hook, bullets.yaml). It's in `archive/v1/` for history only.

## Files of record (read in this order)

1. `SPEC.md` — what we're building and every rule.
2. `CLAUDE.md` (this) — how to operate it.
3. `master-resume.md` — ground truth for experience claims.
4. `voice.md` + `voice/` — tone for cover letters.
