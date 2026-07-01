# SPEC — Job Search System v2

**Owner:** W.S. Gong
**Status:** current. **Single source of truth** — this one file integrates the
former `CLAUDE.md` operating playbook, `voice.md`, and `README.md`. Supersedes
the v1 specs in `archive/v1/`.
**Date:** 2026-06-30

Read this file top to bottom before operating the system. §§1–15 are *what it is
and every rule*; §16 is *how to run it*; §17 + the **Voice config** appendix are
the cover-letter voice (the appendix is machine-parsed — see the note there).
`CLAUDE.md` is a thin pointer to this file; `README.md` is the repo's front door.
If the *core* (§§1–8) grows past two pages of machinery, we've drifted — stop and
cut.

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
2. System reads: the JD + the matching résumé base + the voice config (§17 +
   appendix) + voice/ samples.
3. Out comes, per listing:
   - a tailored résumé (markdown → Swiss PDF, JD-keyword-aware)
   - a cover letter in his voice (grounded in his real past letters)
   - (on request) a 3-sentence outreach blurb for a referral / hiring-manager DM
4. Review/edit the markdown (fast — it's already close).
5. Render to PDF. You upload to the portal yourself. Nothing is auto-submitted.
```

For a **single** URL, do the steps by hand (ingest → tailor → render; commands in
§16). For a **list**, use the batch flow in §9.

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
voice/                    # his real letters, for voice matching (gitignored)
applications/             # one folder per job: listing + tailored outputs (gitignored)
scripts/                  # render + ingest tooling (see §7)
resume-template.docx      # the Swiss/Inter master template the engine renders into
SPEC.md                   # this file — the single source of truth (design + playbook + voice)
CLAUDE.md                 # thin pointer to SPEC.md (auto-loaded each session)
README.md                 # repo front door (points here)
```

`applications/*` and `voice/` are gitignored (private working content). The
target bases, `master-resume.md`, and `SPEC.md` are tracked. The cover-letter
voice config that used to live in `voice.md` is now §17 + the **Voice config**
appendix of this file.

---

## 7. The artifacts & the scripts

**Artifacts (per application):** `listing.{json,md}` (the JD), `resume.md` + `resume.pdf`, `cover-letter.md` + `cover-letter.pdf`. Optional: a 3-sentence outreach blurb.

**Scripts (all under `scripts/`):**

- `url_ingest.py <URL> --no-commit` — detect source; fetch Greenhouse/Lever/Ashby via ATS JSON APIs (no browser); LinkedIn/generic emit a stub `listing.json` flagged `requires_chrome_mcp` / `requires_user_fill`. Writes `applications/<Company>/<role-slug>-<YYYY-MM-DD>/listing.{json,md}`.
- `batch_ingest.py <URL...>` — ingest a list; prints a JSON manifest (folder, company, title, source, stub flags). Drives §9.
- `render_resume.py --input <resume.md> --out <resume.pdf>` — render a tailored résumé. `--target <t> --out <pdf>` renders a master target directly. `--emit-base --target <t> --out <md>` regenerates a target base. `--docx-only` stops at `.docx` (for batched PDF rendering).
- `build_cover_letter.py --input <cover-letter.md> --out <cover-letter.docx>` — reads this file's voice config (letterhead, length hard-max, forbidden phrases); aborts on `[NEEDS SOURCE]`. Run via `.venv/bin/python`.
- `docx_to_pdf.py <docx...>` — converts many docx to PDF in **one** LibreOffice invocation (soffice is single-instance; never run two concurrently).
- `merge_pdfs.py <out.pdf> <in1.pdf> <in2.pdf>` — merge résumé + cover letter into a `combined.pdf` (résumé first). Output path is the **first** argument.
- `lint_resume.py <docx>` — standalone Swiss-style résumé linter. `voice_lint.py` — cover-letter voice linter (reads this file's Forbidden-phrases config).

Truthfulness / quality bar (how we know an artifact is good):

- A recruiter can tell in 6 seconds which lane he's in.
- Every résumé line traces to `master-resume.md` / the base; nothing invented.
- The cover letter would pass as written by him (because he writes it — §11).
- He changes **< 10%** before sending.

---

## 8. Trust boundary

The agent produces artifacts. **The human uploads them.** Never auto-submit, never fill a portal form, never send an outreach message or email on his behalf. This is non-negotiable and applies to the batch flow too.

---

## 9. Batch workflow (URLs → materials)

Goal: paste a list of listing URLs, get a tailored résumé + cover-letter PDF per
listing, fast, in one interactive session. Driven by the `/batch-apply` command.

Sequence (only the tailoring fans out; soffice is fenced to one final step):

1. **Ingest** — `batch_ingest.py <urls…>` → JSON manifest. No git (`--no-commit`; `applications/*` gitignored). Partition **tailorable** vs. **stub** (LinkedIn/generic); surface stubs as "needs a browser fetch or a pasted JD" and continue.
2. **Fan out** — one `batch-apply-worker` subagent per tailorable folder, **all in one message**, concurrent. Each worker: classify the target (§10), copy that base, light-tune to the JD (reorder must-haves first, drop irrelevant entries, tune skills/summary wording — subtract/reorder only, never invent), write `resume.md` + `cover-letter.md`. Workers render nothing and touch no git. Cap concurrency at ~5 per wave for large lists. **Note:** the auto-written cover letter conflicts with the he-writes-the-voice rule (§11); batch cover letters are drafts he must rewrite, not send-ready.
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

**The job of the letter.** Show, in his restrained voice, that he read the
listing and that his background fits it. Not a sales pitch, not an enthusiasm
contest. A reader should finish thinking "he read this and can do the work," not
"he really wants this."

**Who writes it.** He does. The agent reads the JD and the chosen résumé base,
supplies the facts and the structure, and proposes a draft **inline in chat**
for him to approve or rewrite. Only after he approves does it get written to
`cover-letter.md`, grammar-passed, voice-linted, and rendered. Never generate
the final prose from scratch; never write the file or render before he signs off
on the words.

**Shape.** ~180–300 words, signed. An opening framing paragraph, a fit
paragraph, and — optionally — a short closing paragraph.

1. **Opening framing.** Why the role fits, plainly, in a sentence or two. Name the role and company so it is obviously not a form letter. That is the whole opening: no warm-up.
2. **The fit.** Take the two or three things the JD actually asks for and map real work to them: what he did, what happened. Pick the strongest matches; don't answer every bullet.
3. **The close (optional).** One short paragraph stating how he works, as plain fact: curiosity, finding defects, fixing the process that let one through. Allowed *only* when it states settled temperament. The moment it looks forward and offers unrequested work ("the first thing I'd do…"), it is a plan-close and is banned (see below). A letter may end on the fit paragraph instead; both are correct. The known-good `voice/qa-cover-letter.md` has no close; `voice/pinterest-sdet-cover-letter.md` has one.

**Voice.** Calibrated from the real letters in `voice/`, not from rules (the sound is spelled out in §17). The only mechanical rules: plain, declarative; past tense for finished work; one idea per sentence; first-person past-tense facts only; concrete nouns over adjectives; no em-dashes (job-search register).

**Never:**

- **Quote the company's own words back at them.** No press releases, marketing copy, or mission-statement language. This was the v1 tell that read as bullshit. Permanent.
- **Company news as a hook.** Facts in the body must be durable, not timely.
- **Marketing-copy openings.** "What excites me about / drew me to / pulled me to."
- **The plan-close.** "The first thing I'd do is…," "what I'd want to own first…." Juvenile as a form and formulaic enough to read as AI-written; nobody asked for a plan. (Distinct from the allowed disposition close, which states settled temperament and looks backward, not forward.)
- **Lecturing their needs.** No "X needs Y," no maxims or aphorisms. His facts only; nothing explains its own relevance to the reader.
- **Oversell.** A claim stays only if demonstrably true; otherwise the plain fact. No "this sounds like a dream," no thanking them for reading.
- **Self-grading his own prose.** State the credential or artifact plainly ("MFA in Creative Writing"); never tell the reader his writing is good.
- Plus the cross-cutting voice failures in §12 (fog verbs, keyword soup, the cute aphorism, the "X in; Y out" tic).

**Grounding.** Voice from `voice/`. Fit claims from the chosen résumé base. Company facts from the JD or durable knowledge — never invented; the letter works on JD detail alone. `build_cover_letter.py` reads this file's **Voice config** appendix for the letterhead, the length target + hard-max, and the forbidden-phrase warn-list, and aborts on any `[NEEDS SOURCE]` marker.

**Known-goods.** `voice/qa-cover-letter.md` (no close) and `voice/pinterest-sdet-cover-letter.md` (disposition close). Calibrate every new letter against both.

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

(Cover-letter-specific anti-patterns — marketing-copy openings, the plan-close, lecturing their needs — live in §11 Never, where the whole letter policy is consolidated.)

**Structure & positioning**

- **Multiple identities.** → Pick one lane; everything else is evidence.
- **Buried lede.** Strongest proof not in the first third. → Lead with the Slack developer docs (or, for QA, the Platform QA + AI-quality work).
- **Unverifiable self-employment as a title.** "Independent" reading as "unemployed." → Concrete named projects + the portfolio link.
- **Over-claiming.** Superlatives without proof. → Keep a strong claim only if demonstrably true; otherwise state the fact plainly.

**Meta**

- **Rule-bloat as a fix.** The 201st "don't" instead of three real examples. This is the failure that killed v1's cover letters.

---

## 13. Résumé style (Swiss / Inter — enforced by the engine)

The canonical look. `resume-template.docx` embodies it and `scripts/build_resume.py`
renders into it; `scripts/lint_resume.py <docx>` is a standalone Swiss-style
linter you can run to check a rendered résumé. The rules below are the intent;
the template is the enforcement, the linter is the check.

- **One type family: Inter.** Hierarchy by weight and size. No second face. Inter OTF is embedded into the DOCX at build time so PDFs render identically anywhere.
- **Accent `#D44500` (orange)** on the name, tagline, and hyperlinks only — never on body, section labels, or metadata.
- **Grid:** 2-column table (~25% metadata gutter | 75% reading column). No decorative rules; hairline `#333333` 0.5pt section rules are kept as structural elements. Vertical rhythm on a 60/120 DXA lattice.
- **Hierarchy:** Name 24pt bold `#000`; Tagline 16pt bold accent; Section label 12pt bold; Role title 11pt bold; Company 10pt `#666`; Body 10pt `#000`; Date/location (left gutter) 9pt uppercase `#666`.
- **Per-entry stack:** role title → company → description. No inline `**Company** — Title` mixed-weight headers; hierarchy comes from the stack.
- **List sections** (Skills, Education, etc.): each item is its own paragraph, `**Label** — value`, no bullet characters.

**Forbidden:** a second type family; mixed-weight inline headers; accent anywhere but name/tagline/links; typed bullet characters; off-lattice spacing; fixed row heights. Any deviation needs explicit user sign-off (§16, Conventions).

Referred to as **W.S. Gong** (not Billy) in all résumé/CV contexts. Two pages allowed.

---

## 14. Retired in v2 (the kill list)

Removed as complexity with no payoff for this goal (archived in git history / `archive/v1/`). Do not resurrect any of it:

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

---

## 16. Operating playbook (how to run it)

The counterpart to §§1–15's *what*: this is *how* to operate the system. If this
section and the rules above ever disagree, the rules win; fix this section.

### Environment & setup

- **Python 3.11+.** `.venv` (gitignored) is only needed by `build_cover_letter.py`; the other scripts run on system `python3`.
- **LibreOffice** for PDF; **Inter** font embedded at build time.

```bash
brew install --cask libreoffice font-inter                       # PDF render + embedded font
python3 -m venv .venv && .venv/bin/pip install python-docx PyYAML pypdf   # for build_cover_letter.py / merge_pdfs.py
```

- **Fetching:** ATS APIs (Greenhouse/Lever/Ashby) need no browser. LinkedIn/generic listings need a Chrome/Playwright fetch or a pasted JD (they ingest as stubs until then). For JS-rendered or bot-walled listing pages, reach for a reader proxy early rather than cycling browser tools.

### One listing, by hand

```bash
# 1. Ingest (Greenhouse/Lever/Ashby via ATS APIs; add --company/--title if the source is generic).
python3 scripts/url_ingest.py "<URL>" --no-commit
```

Then, in Claude Code: tailor `resume.md` (copy the matching target base per §10
and light-tune to the JD — subtract/reorder, never invent), propose the cover
letter inline for his approval (§11), and render:

```bash
python3 scripts/render_resume.py --input applications/<Co>/<role>-<date>/resume.md --out applications/<Co>/<role>-<date>/resume.pdf
.venv/bin/python scripts/build_cover_letter.py --input applications/<Co>/<role>-<date>/cover-letter.md --out applications/<Co>/<role>-<date>/cover-letter.docx
python3 scripts/docx_to_pdf.py applications/<Co>/<role>-<date>/cover-letter.docx
.venv/bin/python scripts/merge_pdfs.py applications/<Co>/<role>-<date>/combined.pdf applications/<Co>/<role>-<date>/resume.pdf applications/<Co>/<role>-<date>/cover-letter.pdf
```

Return the path to the application **folder** when done, not just one file.

### A list of listings

Paste the URLs to the `/batch-apply` command (`.claude/commands/batch-apply.md`);
it runs §9. Nothing is submitted; the human uploads each.

### Conventions

- **Naming:** lowercase kebab, ISO dates — `senior-dx-engineer-2026-07-01/`. Company folder keeps its name.
- **Branches:** `main` is always submittable. Do feature work on a branch; fast-forward `main` and push when done. Never `git push --force` to `main`.
- **Commits:** `<area>: <verb> <object>`, one logical change each. End messages with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`. Commit only when asked.
- **Git identity:** local to this repo (`git config user.name/.email`, no `--global`). Default `W.S. Gong <billygong@me.com>`.
- **`.gitignore`:** `applications/*` (except `_template/`), `voice/`, `.venv/`, `.DS_Store`, populated `config/`. Never commit private working content or a rendered PDF you didn't mean to. To track something under a gitignored path, refactor the path — don't add an exception.
- **Shell:** commands must be zsh-friendly (this repo's shell is zsh).
- **Style sign-off:** don't change the résumé font, accent, or template (§13) without explicit sign-off.

---

## 17. Cover-letter voice — the sound

How a W.S. Gong cover letter *sounds*, calibrated from the real letters in
`voice/` (gitignored). §11 is the *shape* (job, structure, anti-patterns); this
is the sound. It is the cover-letter counterpart to `master-resume.md`: the
source a tailored letter is written against. The machine-parsed config blocks
follow in the **Voice config** appendix.

Restraint is the default. The `voice/` samples under-sell more than they sell:
"the highly unlikely event that I make it out of the slush pile," "if not,
that's perfectly okay." Carry that. A reader should finish thinking he can do
the work, not that he wants it.

Plain and economical. Short declaratives, concrete nouns, no warm-up. One idea
per sentence. Past tense for finished work.

Specific, always. Every sample names the actual thing: the journals (Fourteen
Hills, Guernica), the bookstores (Chaucer, Borders), the platforms (WordPress,
REST). The strongest move in all three is the same one: read the listing, find
a concrete need, map a real ability to it ("I noticed there is a process by
which to set up pickup orders... I could research incorporating the inventory
system"). That move is the spine of the fit paragraph.

The warm bookends in the samples do NOT carry over to a job-search letter. Strip
the thank-you openings, the gush ("this position sounds like a dream," "I love X
and would cherish the opportunity"), and the apology closes ("thank you for
reading my rambling cover letter"). Those belong to his personal and literary
register; the headers in each `voice/` file mark which register the sample is.

No em-dashes here. The job-search register uses colons, semicolons, parentheses,
periods; his literary voice uses em-dashes freely, but a cover letter is not the
literary voice.

**Professional-register samples.** `voice/qa-cover-letter.md` and
`voice/pinterest-sdet-cover-letter.md` are the known-goods in the register
job-search letters actually use: distilled, first-person past-tense facts, named
tools, no thesis-line openers or windups. Calibrate against both. The Pinterest
sample sanctions a short **closing paragraph** the first sample lacked: a
restrained statement of disposition (curiosity, finding defects, fixing the
process that let one through) is allowed, so long as it stays a plain fact and
never becomes a plan-close, a windup, gush, or a self-grade. The three literary
samples in `voice/` are a warmer, different register; do not copy their bookends
into a job-search letter.

---

## Voice config

The three blocks below — **Letterhead**, **Length**, **Forbidden phrases** — are
parsed at render time by `scripts/build_cover_letter.py` and `scripts/voice_lint.py`
(they read this file, splitting on these `##` headings), the same way
`render_resume.py` parses `master-resume.md`. Keep the heading names exactly as
they are, or the parser won't find them.

## Letterhead

- **Name:** W.S. Gong
- **Subhead:** Developer. Writer, Editor.
- **Contact:** San Francisco, CA · billygong@me.com · ws-gong.com/code · linkedin.com/in/billy-gong

## Length

- **Target:** 180–300 words
- **Hard max:** 500 words

## Forbidden phrases

Warn-only at render. Each is a generic tell. Keep this list short: per §12 the
fix for bad voice is fewer rules and more real examples, not a longer list.

- passionate about
- dynamic team
- wear many hats
- results-driven
- team player
- self-starter
- think outside the box
- synergy
- leverage my
- thank you for your consideration
- i look forward to hearing from you
- i am writing to apply
- i am writing to express
- fast-paced environment
- bring to the table
- what excites me about
- what drew me to
- what pulled me to
- the thing i would
- the thing that
- from nothing
