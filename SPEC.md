# SPEC — Job Search System v2

**Owner:** W.S. Gong
**Status:** current. Single source of truth. Supersedes the v1 specs in `archive/v1/`.
**Date:** 2026-06-30

The core (§§1–8) is intentionally short. §§9–13 are the folded-in detail
(batch flow, cover letters, résumé style, anti-patterns). If the *core* grows
past two pages of machinery, we've drifted — stop and cut.

---

## 1. The one goal

Land W.S. a **developer-documentation / developer-experience role at an AI or dev-tools company** (QA/SDET at an AI company is a valid secondary target — see §3), paying **≥ $120k**, **remote / SF / hybrid**, as fast as possible.

**Success is measured in responses and interviews — not documents produced.** The bottleneck was never prose quality. It was **(a)** scattered positioning, **(b)** a résumé that reads as a 6-year gap to a tech recruiter, and **(c)** cold-applying into a ~1–2% response funnel. Fix all three; better documents alone would not move the needle.

---

## 2. Positioning — the single narrative

One primary identity, stated the same way everywhere:

> **A developer-documentation engineer for the AI era.** Wrote the Slack developer documentation an entire ecosystem built against. Actually ships code. Fluent in the modern agentic stack (Anthropic SDK, MCP, tool-use loops). A trained, published writer — so the docs read like a human wrote them, because one did.

Rules this enforces:

- **Pick one lane per application.** Engineering and editing are *evidence*, not a three-person headline ("Engineer. Writer, Editor.").
- **The MFA is an asset, not a gap.** For a writing role, "I left to earn an MFA and teach writing" is a credential. State it plainly; never hide 2020–2024.
- **Make "Independent / AI Documentation" concrete.** Named, portfolio-backed projects (the agentic QA tooling, the multi-agent bookstore platform), not vague self-employment. Portfolio: https://www.ws-gong.com/code.
- **Lead with the most recent *and* most credible thing.** Recency + AI relevance wins the 6-second scan.

The other target families (§10) are variants of this superset, not different people.

---

## 3. Targeting

**Role titles to match:** technical writer, senior/staff technical writer, developer documentation engineer, docs engineer, developer experience (DX) engineer, developer educator, developer advocate (docs-leaning), content engineer. **Also in scope:** QA / SDET / test engineering **at AI or dev-tools companies**, especially roles about testing non-deterministic / LLM systems (this is where the deep QA history + recent AI-quality work land).

**Company types:** AI labs and AI-product companies; SDK / API / dev-tools companies; anything that ships a developer platform.

**Filters:** comp ≥ $120k · remote-US OR Bay Area (on-site/hybrid OK) · drop pure marketing/DevRel-influencer roles with no writing/eng substance.

**Out of scope:** pure staff-SWE reqs (the gap kills it), *dated* QA-only roles with no AI/modern-testing angle, non-technical editorial.

---

## 4. Channel — the real leak

Cold portal applications convert at ~1–2%. Keep doing them for volume, but:

1. **Warm-path first.** Before cold-applying, spend 5 minutes on a warm route (network at the company, an alum/mutual, someone to message). A referral converts ~10× a cold apply.
2. **A short reusable outreach blurb** (in his voice) for cold-messaging a hiring manager or asking for a referral — a first-class artifact, equal to the résumé.
3. **Honest volume math.** The system makes each application cheap (minutes) so volume is feasible, and nudges toward warm paths so volume isn't the only lever.

W.S. owns the networking. The tool provides a reusable referral-DM framework (template + per-company fill-ins), not automated outreach.

---

## 5. The workflow

You bring the job (a listing URL, or several); the system turns it around fast.

```
1. Paste one or more job-listing URLs (Greenhouse / Lever / Ashby fetch
   automatically; LinkedIn / generic need a browser fetch or a pasted JD).
2. System reads: the JD + the matching résumé base + voice.md + voice/ samples.
3. Out comes, per listing:
   - a tailored résumé (markdown → Swiss PDF, JD-keyword-aware)
   - a cover letter in his voice (grounded in his real past letters)
   - (on request) a 3-sentence outreach blurb for a referral / hiring-manager DM
4. Review/edit the markdown (fast — it's already close).
5. Render to PDF. You upload to the portal yourself. Nothing is auto-submitted.
```

For a **single** URL, do the steps by hand (ingest → tailor → render). For a
**list**, use the batch flow in §9.

Design principles:

- **Markdown-first.** Everything is editable plain text until the final render. No binary diffing, no OOXML surgery, no back-propagation engine.
- **Grounded, not invented.** Résumé claims come from `master-resume.md` / the target bases; letter voice comes from real letters. If a claim isn't supported, it's flagged (`[NEEDS SOURCE]`), never fabricated. This is the one principle kept from v1 — minus the 200 lines of rules and the git-hook gate.
- **Fast by reuse.** Each target has a ready base résumé; tailoring copies a base and light-tunes to the JD, rather than rewriting from scratch. No 8-agent pipeline, no queue.
- **Voice by example, not by rules.** The letter sounds like him because it's calibrated on his real letters in `voice/`, not a banned-phrase manifesto.

---

## 6. The files

```
master-resume.md          # REAL résumé superset, source of truth. Tailoring subtracts/reorders.
resume-qa.md              # target base: QA / SDET
resume-devdocs.md         # target base: Dev Docs / DX (primary)   ┐ generated from master via
resume-education.md       # target base: Developer Education        │ render_resume.py --emit-base
resume-fde.md             # target base: Forward-Deployed Engineering ┘
voice.md                  # cover-letter voice + letterhead/length/forbidden-phrase config
voice/                    # his real letters, for voice matching (gitignored)
applications/             # one folder per job: listing + tailored outputs (gitignored)
scripts/                  # render + ingest tooling (see §7)
resume-template.docx      # the Swiss/Inter master template the engine renders into
SPEC.md                   # this file
CLAUDE.md                 # operating playbook for the coding agent
```

`applications/*` and `voice/` are gitignored (private working content). The
target bases, `master-resume.md`, `voice.md`, and the specs are tracked.

---

## 7. The artifacts & the scripts

**Artifacts (per application):** `listing.{json,md}` (the JD), `resume.md` + `resume.pdf`, `cover-letter.md` + `cover-letter.pdf`. Optional: a 3-sentence outreach blurb.

**Scripts (all under `scripts/`):**

- `url_ingest.py <URL> --no-commit` — detect source; fetch Greenhouse/Lever/Ashby via ATS JSON APIs (no browser); LinkedIn/generic emit a stub `listing.json` flagged `requires_chrome_mcp` / `requires_user_fill`. Writes `applications/<Company>/<role-slug>-<YYYY-MM-DD>/listing.{json,md}`.
- `batch_ingest.py <URL...>` — ingest a list; prints a JSON manifest (folder, company, title, source, stub flags). Drives §9.
- `render_resume.py --input <resume.md> --out <resume.pdf>` — render a tailored résumé. `--target <t> --out <pdf>` renders a master target directly. `--emit-base --target <t> --out <md>` regenerates a target base. `--docx-only` stops at `.docx` (for batched PDF rendering).
- `build_cover_letter.py --input <cover-letter.md> --out <cover-letter.docx>` — reads `voice.md` (letterhead, length hard-max, forbidden phrases); aborts on `[NEEDS SOURCE]`.
- `docx_to_pdf.py <docx...>` — converts many docx to PDF in **one** LibreOffice invocation (soffice is single-instance; never run two concurrently).

Truthfulness / quality bar (how we know an artifact is good):

- A recruiter can tell in 6 seconds which lane he's in.
- Every résumé line traces to `master-resume.md` / the base; nothing invented.
- The cover letter would pass as written by him.
- He changes **< 10%** before sending.

---

## 8. Trust boundary

The agent produces artifacts. **The human uploads them.** Never auto-submit, never fill a portal form, never send an outreach message on his behalf. This is non-negotiable and applies to the batch flow too.

---

## 9. Batch workflow (URLs → materials)

Goal: paste a list of listing URLs, get a tailored résumé + cover-letter PDF per
listing, fast, in one interactive session. Driven by the `/batch-apply` command.

Sequence (only the tailoring fans out; soffice is fenced to one final step):

1. **Ingest** — `batch_ingest.py <urls…>` → JSON manifest. No git (`--no-commit`; `applications/*` gitignored). Partition **tailorable** vs. **stub** (LinkedIn/generic); surface stubs as "needs a browser fetch or a pasted JD" and continue.
2. **Fan out** — one `batch-apply-worker` subagent per tailorable folder, **all in one message**, concurrent. Each worker: classify the target (§10), copy that base, light-tune to the JD (reorder must-haves first, drop irrelevant entries, tune skills/summary wording — subtract/reorder only, never invent), write `resume.md` + `cover-letter.md`. Workers render nothing and touch no git. Cap concurrency at ~5 per wave for large lists.
3. **Render** — main session only. Build all `.docx` (no soffice): `build_cover_letter.py` per folder, `render_resume.py --input --docx-only` per folder. Then **one** `docx_to_pdf.py <all docx>` call → every PDF in a single soffice invocation.
4. **Review** — print a table (Company | Role | Target | Gaps | résumé.pdf | cover-letter.pdf) plus the stub list. Nothing is submitted; the human uploads each.

---

## 10. Targets & bases

Four target families, each a ready base résumé (single-summary `--input`
markdown) tailoring copies and light-tunes:

| Target | Base file | For |
|--------|-----------|-----|
| Dev Docs / DX *(primary)* | `resume-devdocs.md` | technical writer, docs engineer, DX, content engineer |
| Developer Education | `resume-education.md` | developer educator/advocate, teaching/curriculum, tutorials |
| Forward-Deployed Engineering | `resume-fde.md` | forward-deployed / solutions / full-stack-with-customers |
| QA / SDET | `resume-qa.md` | QA / SDET / test engineering at AI or dev-tools companies |

`resume-devdocs.md` / `education` / `fde` are **generated from `master-resume.md`**
(each is a "Summary (by target)" identity + summary over the shared body):

```
python3 scripts/render_resume.py --emit-base --target devdocs   --out resume-devdocs.md
python3 scripts/render_resume.py --emit-base --target education --out resume-education.md
python3 scripts/render_resume.py --emit-base --target fde       --out resume-fde.md
```

`resume-qa.md` is maintained by hand (it reorders the body QA-first and reframes
the AI work as quality engineering — not a pure summary-swap). Regenerate the
three generated bases whenever `master-resume.md` changes.

Never send one blended résumé. Pick the matching base per application.

---

## 11. Cover letters

**The job of the letter:** show, in his restrained voice, that he read the
listing and that his background fits it. Not a sales pitch, not an enthusiasm
contest. A reader should finish thinking "he read this and can do the work," not
"he really wants this."

**Shape.** Three short paragraphs, 250–350 words, signed.

1. **His own framing.** Why the role fits, plainly, in a sentence or two. Name the role and company so it's obviously not a form letter. That's the whole opening — no warm-up.
2. **The fit.** Take the two or three things the JD actually asks for and map real work to them: what he did, what happened. Pick the strongest matches; don't answer every bullet.
3. **Close.** One thing he'd want to talk through, or bring early. Then stop.

**Voice.** Calibrated from the real letters in `voice/`, not from rules. The only mechanical rules: plain, declarative, past tense for finished work, one idea per sentence; no em-dashes (job-search register); concrete nouns over adjectives.

**Never** (see also §12):

- **Quote the company's own words back at them.** No press releases, marketing copy, or mission-statement language. This was the v1 tell that read as bullshit. Permanent.
- **Company news as a hook.** Facts in the body must be durable, not timely.
- **"What excites me about / drew me to / pulled me to."**
- **Oversell.** A claim stays only if demonstrably true; otherwise the plain fact. No "this sounds like a dream," no thanking them for reading.
- **Fog and filler** ("passionate about," "leveraging," "dynamic team," "results-driven"). If it could appear in anyone's letter, cut it.

**Grounding.** Voice from `voice/`. Fit claims from the chosen résumé base. Company facts from the JD or durable knowledge — never invented; the letter works on JD detail alone. `build_cover_letter.py` reads `voice.md` for the letterhead, the 250–350 target + 500 hard-max, and the forbidden-phrase warn-list, and aborts on any `[NEEDS SOURCE]` marker.

---

## 12. Anti-patterns (never ship these)

The catalog of voice and content failures that made v1 read as bullshit. **The fix for bad voice is fewer of these plus real examples — never another rule.** If this list grows faster than the writing improves, we've drifted; stop and cut.

**Voice & prose**

- **Keyword soup.** Concepts listed as skills, especially ones he doesn't do. → Name tools he shipped with; cut padding.
- **Fog verbs.** "working on / leveraging / passionate about / excited by." → Say what he built and what happened.
- **The cute aphorism.** "Docs-as-tests catches drift before users do." Sounds smart, states nothing. → Concrete mechanism and result.
- **Self-assessment flourishes.** Grading his own prose: "so the test plans read clearly," "keeps the bug reports sharp," "and it shows in how I document it." Corny and unverifiable. → State the credential or artifact plainly and stop ("MFA in Creative Writing." / "I write the bug reports and test plans."). Never tell the reader his writing is good; the writing does that or it doesn't.
- **The "X in; Y out" tic.** Pipeline-poetry standing in for substance. → One plain sentence.
- **Em-dashes (job-search register).** Colons, semicolons, parens, periods; en-dashes for ranges only. His literary voice uses them freely — this ban is job-search prose only.
- **Marketing-copy openings** (cover letters). No company news, no "what excites me about," no quoting their marketing back. Permanent. → Open with his own framing; durable company facts only.

**Structure & positioning**

- **Multiple identities.** → Pick one lane; everything else is evidence.
- **Buried lede.** Strongest proof not in the first third. → Lead with the Slack developer docs (or, for QA, the Platform QA + AI-quality work).
- **Unverifiable self-employment as a title.** "Independent" reading as "unemployed." → Concrete named projects + the portfolio link.
- **Over-claiming.** Superlatives without proof. → Keep a strong claim only if demonstrably true; otherwise state the fact plainly.

**Meta**

- **Rule-bloat as a fix.** The 201st "don't" instead of three real examples. This is the failure that killed v1's cover letters.

---

## 13. Résumé style (Swiss / Inter — enforced by the engine)

The canonical look. `resume-template.docx` embodies it; `scripts/build_resume.py`
renders into it and calls `scripts/lint_resume.py` at the end of every render,
exiting non-zero on any divergence. The rules below are the intent; the template
+ linter are the enforcement.

- **One type family: Inter.** Hierarchy by weight and size. No second face. Inter OTF is embedded into the DOCX at build time so PDFs render identically anywhere.
- **Accent `#D44500` (orange)** on the name, tagline, and hyperlinks only — never on body, section labels, or metadata.
- **Grid:** 2-column table (~25% metadata gutter | 75% reading column). No decorative rules; hairline `#333333` 0.5pt section rules are kept as structural elements. Vertical rhythm on a 60/120 DXA lattice.
- **Hierarchy:** Name 24pt bold `#000`; Tagline 16pt bold accent; Section label 12pt bold; Role title 11pt bold; Company 10pt `#666`; Body 10pt `#000`; Date/location (left gutter) 9pt uppercase `#666`.
- **Per-entry stack:** role title → company → description. No inline `**Company** — Title` mixed-weight headers; hierarchy comes from the stack.
- **List sections** (Skills, Education, etc.): each item is its own paragraph, `**Label** — value`, no bullet characters.

**Forbidden:** a second type family; mixed-weight inline headers; accent anywhere but name/tagline/links; typed bullet characters; off-lattice spacing; fixed row heights. Any deviation needs explicit user sign-off (CLAUDE.md §6).

Referred to as **W.S. Gong** (not Billy) in all résumé/CV contexts. Two pages allowed.

---

## 14. Retired in v2 (the kill list)

Removed as complexity with no payoff for this goal (archived in git history / `archive/v1/`):

- search agent + fit-scorer + `search/` + `seen.db` + `sites.yaml` (no scraping; you bring the URL)
- tracker + `sweep.py` + Apple Mail automation + dashboard; scheduler + Calendar; reply-drafter + `personal-facts.yaml`
- the apply queue (`queue_add/apply_queue/queue_status`) + headless drainer + scheduled tasks
- semantic index (`build_index/retrieve` + sentence-transformers + `state/`)
- the **provenance/lint git gate** (`check_provenance --block`, the pre-commit hook, `lint_bullets`, `bullets.yaml`). Grounding is a habit + the `[NEEDS SOURCE]` render-abort, not a 12-phase apparatus.
- bullet-outcomes leaderboard, backprop engine, the v1 tailoring agents (`resume-tailor`, `cover-letter-writer`, `jd-analyzer`), the 8-agent fan-out, the 69k-word spec.

**Kept:** the Swiss PDF render/style, `url_ingest.py`, and the *principle* of grounding claims in real material.

---

## 15. Decisions & open questions

**Resolved:**

- Outreach: tool provides a referral-DM framework; W.S. does the networking (§4).
- Résumé length: two pages allowed.
- Targets: four (§10) — Dev Docs/DX (primary), Developer Education, FDE, QA/SDET. Never one blended résumé.
- Slack role is recorded as **Platform QA** in `master-resume.md` (surfaced for the QA target; the dev-docs targets still lead with the docs work).

**Open:**

- Render target: keep the Inter/#D44500 Swiss style (default), or a fresh look?
