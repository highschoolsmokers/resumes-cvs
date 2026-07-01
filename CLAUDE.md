# CLAUDE.md

**`SPEC.md` is the single source of truth for this repo** — design, operating
playbook, and cover-letter voice, all in one file. Read it top to bottom before
doing anything here. This file is a thin pointer so the essentials load every
session; everything else lives in `SPEC.md`.

- **What this is:** you bring a job-listing URL (or several); the system turns out
  a tailored résumé PDF + cover-letter PDF per listing, grounded in real material.
  The human uploads them. See `SPEC.md` §§1–10.
- **How to operate it:** `SPEC.md` §16 (environment, the two workflows, conventions).
- **Cover letters:** `SPEC.md` §11 (shape/policy) + §17 (voice). **He writes the
  prose**; the agent supplies facts/structure, proposes inline for approval, then
  grammar-passes, voice-lints, and renders.
- **Résumé style:** `SPEC.md` §13. Refer to him as **W.S. Gong** in résumé/CV contexts.

## Trust boundary (never cross)

- **Never submit an application.** Produce the PDFs; the human uploads them.
- **Never send an email or outreach message.** Draft only.
- **Never invent.** Every résumé line traces to `master-resume.md` / a base; every
  cover-letter fact to the JD or durable knowledge. If you can't source it, write
  `[NEEDS SOURCE: …]` and stop.

These hold in the batch flow too (`SPEC.md` §8).
