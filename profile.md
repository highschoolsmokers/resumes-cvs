# Profile — W.S. Gong

The user-specific inputs the system tailors against: goal, positioning,
targeting, channel, résumé style, and voice. `SPEC.md` is the generic system;
this file is the user. Swap it to run the system for a different job search.

## Goal

Land a developer-documentation or developer-experience role at an AI or dev-tools
company; **≥ $120k**; remote, SF, or hybrid. Secondary: QA/SDET at an AI company.

Success is responses and interviews, not documents produced. What blocks it:
scattered positioning and cold applications that convert near 1–2%.

## Identity

One primary identity, stated the same way everywhere:

> **A developer-documentation engineer for the AI era.** Wrote the Slack developer documentation an entire ecosystem built against. Ships code. Fluent in the modern agentic stack (Anthropic SDK, MCP, tool-use loops). A trained, published writer; the documentation reads as human-written.

- **One lane per application.** Engineering and editing are evidence, not a combined headline.
- **Make "Independent" concrete.** Named, portfolio-backed projects (the agentic QA tooling, the multi-agent bookstore platform; https://www.ws-gong.com/code), not unspecified self-employment.
- **Lead with the most recent and most credible item.** Recruiters scan briefly; recency and AI relevance decide the first pass.

## Limitations & reframes

- **The break from full-time software (2020 onward).** The 2021–2024 MFA and the adjunct-faculty teaching after it. Present these as graduate study and teaching, not a gap; do not omit the years.

## Targeting

Titles: technical writer, docs/DX engineer, developer educator or advocate (docs-leaning), content engineer. Secondary: QA/SDET at AI or dev-tools companies, especially testing non-deterministic or LLM systems. Companies: AI labs and products, SDK/API/dev-tools, any company shipping a developer platform. Filters: comp ≥ $120k; remote-US or Bay Area; exclude influencer-DevRel roles with no writing or engineering substance. Out of scope: pure staff-SWE roles, dated QA-only roles with no AI angle, non-technical editorial.

## Target families & bases

One base résumé per family; send the matching one per application.

| Target | Base file | For |
|--------|-----------|-----|
| Dev Docs / DX *(primary)* | `resume-devdocs.md` | technical writer, docs engineer, DX, content engineer |
| Developer Education | `resume-education.md` | developer educator or advocate, teaching, curriculum, tutorials |
| Forward-Deployed Engineering | `resume-fde.md` | forward-deployed, solutions, full-stack-with-customers |
| QA / SDET | `resume-qa.md` | QA / SDET / test engineering at AI or dev-tools companies |

Dev Docs, Education, and FDE are generated from `master-resume.md` (a summary swap over the shared body); regenerate them when the master changes. QA is hand-maintained: it reorders the body QA-first and reframes the AI work as quality engineering.

## Channel

Cold applications convert near 1–2%; a referral about ten times higher. Spend five minutes on a warm path before applying cold. The system supplies a reusable referral-message framework in the user's voice; the user does the networking. Outreach is never automated.

## Résumé

**Register.** The summary is clipped and journalistic: implied-subject, telegraphic sentences ("Developer-documentation engineer with twenty-five years in software. At Slack, wrote the API references…"). Subjectless or third-person, not first-person. Lead with the role and the proof.

**Structure.** Strongest proof in the first third: the Slack developer documentation, or for QA the Platform QA and AI-quality work. Name projects and give the portfolio link; never let "Independent" read as unemployed. Use the name **W.S. Gong**, not Billy. Two pages allowed. (One identity per résumé — see Identity.)

**Style (Swiss / Inter).** The canonical look, enforced by the template and linter (SPEC Implementation):

- **One type family: Inter.** Hierarchy by weight and size, no second face.
- **Accent `#D44500`** on the name, tagline, and hyperlinks only; never body, labels, or metadata.
- **Grid:** two-column layout (~25% metadata gutter, 75% reading column); hairline `#333333` 0.5pt section rules; vertical rhythm on a 60/120 unit lattice.
- **Hierarchy:** Name 24pt bold `#000`; Tagline 16pt bold accent; Section label 12pt bold; Role title 11pt bold; Company 10pt `#666`; Body 10pt `#000`; Date and location (left gutter) 9pt uppercase `#666`.
- **Per-entry stack:** role title, then company, then description. No mixed-weight inline headers; hierarchy comes from the stack.
- **List sections** (Skills, Education): each item is its own paragraph, a bold label and a value, no bullet characters.

Forbidden: a second type family; mixed-weight inline headers; the accent anywhere but name, tagline, and links; typed bullet characters; off-lattice spacing; fixed row heights. Any deviation needs explicit sign-off.

## Voice

Rules for any prose written as the user: résumé lines, cover letters, referral messages. Plain, declarative, past tense for finished work. Concrete nouns over adjectives, one idea per sentence. State the fact and stop; cut anything that exists for rhythm or effect.

Never:

- **Decoration instead of fact.** Fog verbs ("working on," "leveraging," "passionate about"), aphoristic language ("Docs-as-tests catches drift before users do"), "X in; Y out" pipeline phrasing. Replace with the concrete tool, mechanism, or result.
- **Claims that aren't demonstrable.** Skills listed but not actually used; superlatives without proof; grading one's own prose ("so the test plans read clearly"). State only what's real; let a credential or artifact speak plainly ("MFA in Creative Writing") instead of praising it.
- **Maxims and lecturing.** No general truths about the domain, no "X needs Y," no restating facts about the company to the company, no telling the reader what their systems or role require. Only the user's own facts. Cut windups: "Now I," "Lately," "The thing I would," "the thing that."
- **Em-dashes in prose.** Colons, semicolons, parentheses, periods; en-dashes for ranges only. (The résumé's label/value separator is a layout element, not prose, and is exempt.) The literary register uses em-dashes freely; this ban is the job-search register only.

The correction for bad voice is fewer of these plus real examples, never another rule. If the list grows faster than the writing improves, stop and cut.

**Cover-letter sound.** Restrained and understated; the samples under-sell. Specific throughout: name the actual journals, bookstores, platforms, tools. Omit the warm openings and closings of the personal register: no thank-you openings, no gush, no apology closes. First person (the résumé is third-person), past tense for finished work.

The Letterhead, Length, and Forbidden phrases below are machine-parsed at render (see SPEC Implementation).

## Letterhead

- **Name:** W.S. Gong
- **Subhead:** Developer. Writer, Editor.
- **Contact:** San Francisco, CA · billygong@me.com · ws-gong.com/code · linkedin.com/in/billy-gong

## Length

- **Target:** 180–300 words
- **Hard max:** 500 words

## Forbidden phrases

Generic tells. A hit stops the render. Keep the list short and high-precision.

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
