# job-search plugin

Personal Cowork plugin wrapping the agentic job-search workflow in this repo
(`/Users/Gong/workspace/resumes-cvs`). It exposes the workflow as Cowork skills
so new sessions discover them via `<available_skills>` and trigger on
natural-language phrases.

**Canonical source.** This `plugin/` directory is the source of truth. The
installed/session plugin is materialized from it — edit here, then rebuild the
plugin. Do not edit an installed copy directly; it will be overwritten.

## What's in it

| Skill   | Triggers on                                                        | What it does                                                                                        |
| ------- | ----------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| `apply` | "apply to `<url>`", "prep this job", "tailor my resume for `<url>`" | URL → normalised listing → tailored résumé → cover letter → combined PDF. Hands artifacts over; does NOT submit. |

Future skills (one per pipeline stage) go in `skills/` alongside `apply` and
auto-discover the same way.

## Scope & non-goals

- **In scope:** everything up to a reviewable PDF packet per application (SPEC.md §§2, 7).
- **Out of scope:** submitting applications, filling portal forms, sending email
  or outreach. Those are trust-boundary actions the user performs themselves
  (SPEC.md §3, CLAUDE.md).

## Prerequisites

- This repo, with the source-of-truth files: `SPEC.md`, `profile.md`,
  `master-resume.md`, the `resume-*.md` bases, and `voice/`.
- Python 3.11+ with `.venv` from `requirements.txt` (`python3 -m venv .venv &&
  .venv/bin/pip install -r requirements.txt`).
- `libreoffice` + `font-inter` (PDF render; see SPEC.md §9 Environment).
- The Chrome MCP connected (only for LinkedIn URLs; other ATS adapters and the
  reader-proxy path work without it).

## Personal vs. distributable

This plugin is personal: paths, voice, and source material are W.S. Gong's, in
the user layer (`profile.md`, `master-resume.md`, `voice/`, the bases). The
engine (`SPEC.md`, `scripts/`, this skill body) is generic. A fork generalises by
swapping the user layer; the skill body needs no rewrite.
