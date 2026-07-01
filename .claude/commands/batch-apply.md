---
description: Ingest a list of job-listing URLs and produce a tailored résumé + cover-letter PDF for each, in parallel. Never submits.
argument-hint: <url1> <url2> ... (or paste a list of URLs)
---

Prepare applications for every job-listing URL in `$ARGUMENTS` (and any URLs the
user pasted in the message). This is the batch workflow in **SPEC.md §9**. Follow
these steps exactly; the one hard rule is **never run two `soffice` processes at
once**, so all rendering is fenced into one final batched step run by you (not the
workers).

## 1. Ingest

Collect every URL from `$ARGUMENTS` and the message; then:

```bash
python3 scripts/batch_ingest.py <url1> <url2> ...
```

Read the JSON array it prints. Each entry has `folder`, `company`, `title`,
`source`, `requires_chrome_mcp`, `requires_user_fill`, `error`.

**Partition:**
- **Tailorable** = entries with a `folder` and neither stub flag set.
- **Stub** = `requires_chrome_mcp` or `requires_user_fill` true (LinkedIn /
  generic / a failed ATS fetch). These can't be auto-tailored. Set them aside and
  list them at the end as "needs a browser fetch or a pasted JD."

Caveat to watch: `batch_ingest.py` names folders from the JD's company field, so
two unknown-company stubs (or a casing difference vs. an existing folder on
macOS) can collide on one folder. Treat stubs by URL, not by folder.

## 2. Fan out the tailoring (parallel)

For the tailorable folders, spawn **one `batch-apply-worker` subagent per folder,
all in a single message** so they run concurrently. Pass each worker only its
folder path. If there are more than ~5, do them in waves of 5 (say so; don't
build a queue).

Each worker classifies the target, copies the matching base, light-tunes to the
JD, and writes `resume.md` + `cover-letter.md` in its folder — it renders nothing
and touches no git. Collect each worker's returned JSON. Drop any
`chosen_target: "out_of_scope"` from the render set and note it in the table.

## 3. Render — ONE soffice batch

Only you do this, after all workers return. Build the docx first (no soffice),
then convert everything in a single call:

```bash
# per tailorable folder that produced files:
#   build_cover_letter.py needs python-docx → run it via the repo venv.
.venv/bin/python scripts/build_cover_letter.py --input <folder>/cover-letter.md --out <folder>/cover-letter.docx
python3 scripts/render_resume.py --input <folder>/resume.md --out <folder>/resume.docx --docx-only

# then ONE conversion for the whole batch:
python3 scripts/docx_to_pdf.py <folder1>/resume.docx <folder1>/cover-letter.docx <folder2>/resume.docx <folder2>/cover-letter.docx ...
```

If `.venv` is missing, create it once: `python3 -m venv .venv && .venv/bin/pip install python-docx PyYAML`.

`docx_to_pdf.py` converts all of them in one LibreOffice invocation. Never launch
`render_resume.py` without `--docx-only` here (that would fire its own soffice)
and never run these conversions concurrently.

## 4. Review table + hand off

Print one table:

```
Company | Role | Target | Gaps | Résumé | Cover letter
```

with clickable links to each `resume.pdf` / `cover-letter.pdf`. Below it, list
the stub URLs that still need a browser fetch or a pasted JD, and any
out-of-scope skips with their one-line reason.

Close with: the PDFs are ready in each `applications/<Company>/<slug>-<date>/`
folder; **nothing was submitted or committed** — the user uploads each to the
portal themselves (SPEC.md §8 trust boundary). Offer to fix any weak tailoring or
fill the stubs next.
