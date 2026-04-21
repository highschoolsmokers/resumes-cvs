# Application folder template

This is the scaffolding every per-application folder should mirror. Copy
this directory's contents into `applications/<Company>/<role-slug>-<YYYY-MM-DD>/`
when starting a new application by hand. In the normal path, `scripts/url_ingest.py`
and the `resume-tailor` / `cover-letter-writer` agents produce these files
automatically — this template is the spec for what they produce.

## Files that live here

### Produced by ingest (Phase 2)

- `listing.json` — normalised listing, schema per spec §3.4.
- `listing.md` — human-readable JD (markdown conversion of the source HTML).

### Produced by resume-tailor (Phase 2)

- `resume-plan.yaml` — the plan (closed-universe IDs only) that drives the build.
- `resume.docx` — the rendered Swiss-style resume.
- `resume.pdf` — same, via `scripts/docx_to_pdf.py`.
- `resume.unpacked/` — pretty-printed OOXML sibling of `resume.docx`; what makes the git diff legible.
- `resume.provenance.yaml` — one claim per sentence on the page; `unsourced_claims: []`.
- `fit-report.md` — why the JD matches, where it doesn't, and how skills were ordered.

### Produced by cover-letter-writer (Phase 3)

- `company-facts.md` — research artefact; every concrete noun in the letter cites an anchor here.
- `cover-letter.md` + `cover-letter.docx` + `cover-letter.pdf` — the letter (markdown source, DOCX render via `build_cover_letter.py`, PDF via `scripts/docx_to_pdf.py`).
- `cover-letter.provenance.yaml` — same guarantees as the resume sidecar.

The two PDFs — `resume.pdf` and `cover-letter.pdf` — are the deliverables. They ship to the portal as separate files; we do NOT merge them into a combined PDF.

### Produced by tracker-agent / reply-drafter / scheduler (Phase 4)

- `tracker.yaml` — schema per spec §6.2. Source of truth for the application's lifecycle. Updated by `tracker-agent` on every sweep.
- `notes.md` — one-line entries with Mail.app `message://` deep-links to every matched message. Append-only.
- `replies/<YYYY-MM-DD>-<topic>.md` + `.provenance.yaml` — `reply-drafter` outputs for recruiter-question threads. The draft body is staged in Mail.app → Drafts; the `.md` is the audit trail. See `replies/README.md`.
- `schedule/<YYYY-MM-DD>-<event>.yaml` — `scheduler` outputs for scheduling threads. Records source phrases, parsed slots, calendar conflicts, candidate slots (each with a `[TENTATIVE]` Google Calendar event ID), and the confirmation state. See `schedule/README.md`.

## What NOT to put here

- Raw HTML dumps or network fixtures. If you need those, they live under `search/runs/<ts>/raw/` and are gitignored.
- Anything under `config/secrets.env*`, `.DS_Store`, `~$*.docx`. See `.gitignore`.
- A second resume template or a different letterhead. The style spec is fixed.
