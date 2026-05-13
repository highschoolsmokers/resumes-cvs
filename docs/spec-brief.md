# Job-search system — brief spec

A pipeline that turns a job-listing URL into submission-ready application
materials (tailored resume + cover letter, both PDFs) whose every concrete
claim cites a source. Tracks inbox, drafts recruiter replies and scheduling
proposals. **Never** submits, sends, or confirms — three manual checkpoints.

## Pipeline

| # | Stage     | Driver                        | Agent / output                                                    |
| - | --------- | ----------------------------- | ----------------------------------------------------------------- |
| 1 | Search    | `search/run.py`               | `search-agent` → `listings.jsonl`                                 |
| 2 | Score     | (in `search/run.py`)          | `fit-scorer` → `scored.jsonl`, `summary.md`                       |
| 3 | Ingest    | `scripts/url_ingest.py`       | `listing.json` + `listing.md` per app                             |
| 4 | Tailor    | `build_resume.py`             | `resume-tailor` → `resume.docx`/.pdf + plan + provenance          |
| 5 | Cover     | `build_cover_letter.py`       | `cover-letter-writer` → `cover-letter.{md,pdf}` + provenance      |
| 6 | Combine   | `scripts/merge_pdfs.py`       | `combined.pdf` (resume first, cover letter second)                |
| 7 | Submit    | **user only**                 | uploads PDFs via the portal                                       |
| 8 | Track     | `scripts/sweep.py` (every 2h) | `tracker-agent` → `tracker.yaml`, regenerates `dashboard.md`      |
| 9 | Reply     | (tracker hands off)           | `reply-drafter` → draft in Mail.app/Drafts (`questions` threads)  |
| 10| Schedule  | (tracker hands off)           | `scheduler` → 3 slots + `[TENTATIVE]` Calendar + draft reply      |

## Inputs (closed universe — agents read only these)

```
resume-template.docx        pristine Swiss template (Inter, 25/75 grid)
bullets.yaml                every usable resume claim, tagged by role family
config/criteria.yaml        search filters, comp floor, excludes
config/voice.yaml           cover-letter tone, forbidden phrases, scheduling defaults
config/personal-facts.yaml  answers to recruiter "personal" questions
config/sites.yaml           job-board adapters (Greenhouse / Lever / Ashby)
voice-corpus/               real writing samples for cover-letter voice
```

## Per-app output (`applications/<Company>/<role-slug>-<date>/`)

Listing + resume + cover-letter artifacts + their provenance sidecars +
`tracker.yaml` + `replies/<thread>.{md,provenance.yaml}` +
`schedule/<thread>.md` + `notes.md`. Skeleton lives at `applications/_template/`.

## Scripts

```
build_resume.py             render resume.docx from a plan + bullets.yaml
build_cover_letter.py       render cover-letter.docx with the letterhead
search/run.py               fetch → dedupe → score → emit summary
scripts/url_ingest.py       single-URL on-ramp; produces listing.json
scripts/extract_bullets.py  one-time: dump DOCX bullets for hand-curation
scripts/backprop_edits.py   prompted: fold docx hand-edits back into bullets.yaml
scripts/bullets_lookup.py   human grep over bullets.yaml
scripts/lint_bullets.py     schema lint (ids unique, roles resolve)
scripts/lint_resume.py      Swiss-typography consistency (called by build_resume)
scripts/check_provenance.py provenance gate; pre-commit hook in --block
scripts/docx_to_pdf.py      DOCX → PDF via headless LibreOffice
scripts/merge_pdfs.py       combine into resume+letter combined.pdf
scripts/sweep.py            Apple Mail sweep driver → tracker.yaml updates
scripts/dashboard.py        rebuild dashboard.md from every tracker.yaml
scripts/install_apply_skill.sh  install /apply slash command system-wide
```

## Agents (prompts in `agents/`)

```
search-agent          fetch + normalize listings from configured boards
fit-scorer            score against criteria; emit yes/maybe/no recommendation
resume-tailor         plan bullets per listing; refuse on unsourced claim
cover-letter-writer   research company; write letter citing facts + voice
tracker-agent         classify Mail.app threads; promote tracker; route
reply-drafter         answer questions from closed universe; stage Mail draft
scheduler             propose 3 slots from Calendar; stage draft + tentative event
```

## Guardrails — the hallucination gate

| Output domain      | Must cite                                                 |
| ------------------ | --------------------------------------------------------- |
| Resume bullets     | id in `bullets.yaml` or anchor in `resume-template.docx`  |
| Cover-letter facts | `company-facts.md` (with URL) or `bullets.yaml`           |
| Recruiter replies  | key in `config/personal-facts.yaml`                       |

Unsourced → output literally writes `[NEEDS SOURCE: …]` or `[USER TO ANSWER: …]`.
`check_provenance.py` is the pre-commit hook that blocks commits with
unsourced claims.

## Trust boundary — three hard checkpoints

1. **Submission** — user uploads PDFs to the portal. The agent never clicks Submit.
2. **Email** — drafts land in Apple Mail / Drafts via `make new outgoing message`. Never `send`.
3. **Calendar** — events stay `[TENTATIVE]` until the user says "confirmed".

Everything else — search, score, tailor, draft, commit, archive — runs unattended.
