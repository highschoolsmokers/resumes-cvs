# RUBRIC — cover-letter judgment

Trained criteria for cover letters: the judgment layer between profile.md's hard
rules (mechanically enforced by voice_lint.py) and the raw voice/ samples (routed
by voice_index.py). User-approved; every change is one commit naming its source
example. `git log RUBRIC.md` is the training history. Mechanism: SPEC §7.

## Global — every letter
- Strongest matches only. Map the two or three real overlaps; let honest gaps
  stand rather than paper over them. [everlaw]
- The opener earns its place: state what the candidate is and the strongest
  proof, or the two spans that make the fit — never a thesis or warm-up.
  [adobe, vercel]
- Offer no claim the candidate can't stand behind: a dated, past-tense-only skill
  is left out, not implied current, against a current-proficiency ask. [adobe]
- Every clause is a fact; nothing explains its own relevance to the reader.
- Fit maps real work to the listing's actual asks, in the candidate's words.

## Per register
- **qa-sdet** — opener leads with the QA span, or fuses QA + AI-verification
  (both-halves) for AI-augmented roles; close is ends-on-fit or a disposition
  about how things break / test-signal quality. [qa, pinterest, adobe]
- **fde-customer-success / fde-internal-tooling** — "I am a…" opener leading with
  production work on the target stack; disposition close ending on a concrete
  object. [vercel, everlaw]
- **docs-dx** — opener leads with the docs identity and the Slack docs; fit names
  the doc artifacts plus the Anthropic-stack tools. [dev-docs, salesforce]

## Anti-patterns (shapes; profile.md enforces the exact phrases)
- Plan-close — forward-looking unrequested work ("the first thing I'd do…").
- Fronted "What has [verb] me…" pseudo-cleft — announces a disposition instead of
  stating it. [retired 2026-07-03]
- Windups ("Now I", "Lately"); marketing-copy openers ("what excites me about").

## How this is trained
Each canonized known-good is scored here. Confirmations change nothing. A gap, an
over-strict criterion, or a new bad pattern → propose → approve → commit
(`rubric: <change> (from <sample-id>)`). Prune: merge a covered criterion, cut one
that never fires (also a commit). Keep it shorter than the corpus it generalizes.
