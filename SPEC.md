# SPEC — Job Search System v2

**Owner:** W.S. Gong
**Status:** DRAFT — under review
**Date:** 2026-06-30
**Supersedes:** `job-search-agent-spec.md` (v1, retired — see §10 kill list)

---

## 1. The one goal

Land W.S. a **developer-documentation / developer-experience role at an AI or dev-tools company**, paying **≥ $120k**, **remote / SF / hybrid**, as fast as possible.

**Success is measured in responses and interviews — not documents produced.** The v1 system produced lots of artifacts and zero responses. v2 is judged only by replies landing in the inbox.

Hard truth that shapes everything below: the bottleneck was never prose quality. It was **(a)** scattered positioning, **(b)** a résumé that reads as a 6-year gap to a tech recruiter, and **(c)** cold-applying into a ~1–2% response funnel. v2 fixes all three. Better documents alone would not have moved the needle.

---

## 2. Positioning — the single narrative

One identity, stated the same way everywhere:

> **A developer-documentation engineer for the AI era.** Wrote the Slack developer documentation an entire ecosystem built against. Actually ships code. Fluent in the modern agentic stack (Anthropic SDK, MCP, tool-use loops). A trained, published writer — so the docs read like a human wrote them, because one did.

Rules this enforces:

- **Drop "Engineer. Writer, Editor." as a tagline.** It's three people. Pick one: *developer docs / DX*. Engineering and editing become *evidence*, not the headline.
- **The MFA is an asset, not a gap.** For a writing role, "I left to earn an MFA and teach writing" is a credential. We state it plainly and proudly; we do not hide or apologize for 2020–2024.
- **Make "Independent / AI Documentation" concrete.** Right now it reads as "unemployed/freelance." Reframe as named, portfolio-backed projects (the agentic QA system, docs-as-tests pipelines, this very tooling). Link a portfolio. Vague self-employment → demonstrable recent AI+docs work.
- **Lead with the most recent *and* most credible thing**, not the longest. Recency + AI relevance wins the 6-second scan.

---

## 3. Targeting

**Role titles to match:** technical writer, senior/staff technical writer, developer documentation engineer, docs engineer, developer experience (DX) engineer, developer educator, developer advocate (docs-leaning), content engineer.

**Company types:** AI labs and AI-product companies; SDK / API / dev-tools companies; anything that ships a developer platform and needs docs.

**Filters:** comp ≥ $120k · remote-US OR Bay Area (on-site/hybrid OK) · drop roles that are pure marketing/DevRel-influencer with no writing/eng substance.

**Out of scope (do not apply):** pure staff-SWE reqs (gap kills it), dated QA-only roles, non-technical editorial.

---

## 4. Channel — the real leak, addressed

Cold portal applications convert at ~1–2%. We keep doing them (volume), but v2 explicitly adds the higher-converting channels because that's where the actual job comes from:

1. **Warm-path first.** For any target company, before cold-applying, spend 5 minutes checking for a warm route: anyone in the network at the company, a relevant person to message, an alum/mutual. A referred application converts ~10× a cold one.
2. **A short, reusable outreach blurb** (in his voice) for cold-messaging a hiring manager or asking for a referral. This is a first-class artifact, equal to the résumé.
3. **Honest volume math.** At 1–2% cold, landing interviews means *many* applications or *fewer warm ones*. The system makes each application cheap (minutes) so volume is feasible, AND nudges toward warm paths so volume isn't the only lever.

> **Resolved:** W.S. owns the networking. The tool provides a reusable **referral-DM framework** (template + per-company fill-ins), not automated outreach.

---

## 5. The workflow (the whole thing)

No fetching (egress is dead). No search agent. No tracking. You bring the job; the system turns it around fast.

```
1. You paste a job description (or drop it in a file).
2. System reads: master-resume.md + voice samples + the JD.
3. Out comes, in one pass:
   - a tailored résumé (markdown, DX-positioned, JD-keyword-aware)
   - a cover letter in YOUR voice (grounded in your real past letters)
   - a 3-sentence outreach blurb for a referral / hiring-manager DM
   - a 2-line "warm path check" reminder (who do you know here?)
4. You review/edit the markdown (fast — it's already close).
5. Render to PDF only when you're happy.
```

Design principles:

- **Markdown-first.** Everything is editable plain text until the final render. No binary diffing, no OOXML surgery, no back-propagation engine.
- **Grounded, not invented.** Résumé claims come from your real master résumé; letter voice comes from letters you actually wrote. If a claim isn't supported, it's flagged, not fabricated. (This is the *one* good idea we keep from v1 — minus the 200 lines of rules and the git hook.)
- **Fast by having no pipeline.** The tailoring is done in one pass, not handed across 8 agents and a queue.
- **Voice by example, not by rules.** The letter sounds like you because it's pattern-matched on 2–3 of your real letters — not because of a 200-line list of banned phrases.

---

## 6. The files (the whole repo)

```
master-resume.md     # your REAL resume, full superset, DX-positioned. Source of truth.
voice/               # 2–3 cover letters you actually wrote (for voice matching)
me.md                # name, contact, links, comp/location, + a SHORT list of real hard rules
                     #   (no em-dashes; openings that aren't buzzy) — distilled, not a manifesto
applications/        # one folder per job: the pasted JD + the tailored outputs
SPEC.md              # this file
render/              # the one styling asset kept from v1: markdown/docx -> clean PDF
```

That's it. Compare to v1's 24 scripts + 8 agents + 69k-word spec.

---

## 7. The artifacts, defined

- **master-resume.md** — built from your real 2026-05-14 resume, re-pointed at the dev-docs narrative (§2). The superset; tailoring *subtracts and reorders*, never invents.
- **Tailored résumé** — per JD: reorders/selects to match keywords, keeps it truthful, fits one page where possible.
- **Cover letter** — 250–350 words, your voice; opens with your own framing, maps your background to what the JD asks, never quotes the company back at itself. Full rules: `docs/cover-letter-spec.md`.
- **Outreach blurb** — 3 sentences, your voice, for a referral ask or hiring-manager DM.

---

## 8. Quality bar (how we know an artifact is good)

- A recruiter can tell in 6 seconds that you're a **developer-docs person**.
- Every résumé line is true and traceable to master-resume.md.
- The cover letter would pass as written by you, by you.
- You change **< 10%** of the output before sending. (v1: you rewrote everything. That's the metric that has to move.)
- The whole turnaround for one job is **minutes**, not a pipeline run.

---

## 9. Anti-patterns (never ship these)

The catalog of voice and content failures that made v1 read as bullshit. Every artifact is checked against this list before it ships. **The fix for bad voice is fewer of these plus real examples — never another rule.** If this list grows faster than the writing improves, we've drifted; stop and cut.

**Voice & prose**

- **Keyword soup.** Listing concepts as if they were skills — especially ones you don't actually *do*. `Constitutional AI` is a research paper, not a skill. → Name tools you've shipped with; cut the padding.
- **Fog verbs.** "working on / leveraging / passionate about / excited by agentic systems." → Say what you built and what happened.
- **The cute aphorism.** "Docs-as-tests catches drift before users do." Sounds smart, states nothing. → Give the concrete mechanism and the result.
- **Self-assessment flourishes.** Grading your own prose: "so the test plans read clearly," "keeps the bug reports sharp," "and it shows in how I document it." Corny, and unverifiable. → State the credential or the artifact plainly and stop ("MFA in Creative Writing." / "I write the bug reports and test plans."). Never tell the reader your writing is good; the writing does that or it doesn't.
- **The "X in; Y out" tic.** Pipeline-poetry standing in for substance. → One plain sentence.
- **Em-dashes (job-search register).** Colons, semicolons, parens, periods; en-dashes for ranges only. His literary voice uses them freely — this ban is job-search prose only.
- **Marketing-copy openings** (cover letters). No company news, no "what excites me about," no quoting their marketing back at them. Permanent. → Open with your own framing; durable company facts only.

**Structure & positioning**

- **Multiple identities.** "Engineer. Writer, Editor." → Pick one lane; everything else is *evidence*.
- **Buried lede.** Strongest proof not in the first third. → Lead with the Slack developer docs.
- **Unverifiable self-employment as a job title.** "Independent" reading as "unemployed." → Concrete named projects + a portfolio link.
- **Over-claiming.** Superlatives without proof. → Keep a strong claim only if it's demonstrably true; otherwise state the fact plainly.

**Meta**

- **Rule-bloat as a fix.** Adding the 201st "don't" instead of feeding three real examples. This is the failure that killed v1's cover letters.

---

## 10. Kill list (deleted in v2)

Everything below is removed — it was complexity with no payoff for this goal:

- search agent + fit-scorer + `search/` + `seen.db` + `sites.yaml` (no scraping; you bring the JD)
- tracker agent + `sweep.py` + Apple Mail automation + dashboard (no responses to track yet; revisit only once interviews exist)
- scheduler agent + Google Calendar integration
- reply-drafter + `personal-facts.yaml` machinery
- apply queue (`queue_add/apply_queue/queue_status`) + headless drainer + scheduled tasks
- semantic index (`build_index/retrieve` + sentence-transformers + `state/`)
- provenance git hook + `check_provenance` --block + `lint_*` gate (grounding stays as a habit, not a 12-phase enforcement apparatus)
- bullet-outcomes leaderboard, backprop engine, the 8-agent fan-out, the 69k-word spec

What we **keep**: the PDF-rendering/styling capability (Swiss style is fine), and the *principle* of grounding claims in real material.

---

## 11. Decisions & open questions

**Resolved (2026-06-30):**

- **Outreach scope** — tool provides a referral-DM framework; W.S. does the networking. (§4)
- **Résumé length** — two pages allowed.
- **Portfolio anchor** — https://www.ws-gong.com/code. The "Independent" entry points here; content to be supplied by W.S. (egress blocked, can't fetch).

**Resolved (2026-06-30, cont.):**

- **Targets** — three, from one master: **Dev Docs / DX (primary)**, **Developer Education**, **Forward-Deployed Engineering**. Each is an identity-line + summary swap over a shared body; the matching version goes to each role type. Never one blended résumé. Defined in `master-resume.md` → Summary by target.

**Still open:**

- **Render target:** keep the existing Inter/#D44500 Swiss PDF style (default), or a fresh look?

---

*This spec is intentionally short. If it grows past two pages of machinery, we've drifted again — stop and cut.*
