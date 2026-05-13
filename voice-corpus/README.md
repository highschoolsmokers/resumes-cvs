# voice-corpus/

Real writing samples the `cover-letter-writer` agent reads BEFORE drafting,
as ground truth for W.S. Gong's voice. The agent is instructed to match
sentence rhythm and vocabulary, not to copy phrases verbatim.

## What to drop in here

- **Prior cover letters** — anything you've hand-written for past roles.
  Even rejected ones. The useful signal is phrasing, not outcomes.
- **Application answers** — NVIDIA's is already seeded
  (`nvidia-application-answers.md`). Add any other long-form answers you've
  written in recent memory.
- **Project READMEs** — your own writing on Bindery, Colophon, Litverity,
  Paperless, and any other shipped projects. The first-person passages
  are the voice signal; code blocks are fine to keep because the agent
  will skip them.
- **Long-form posts** — blog posts, substack drafts, work-in-public
  threads. Anything where you wrote more than three paragraphs in your
  own voice.

## What NOT to drop in here

- Boilerplate you copied from elsewhere. The point is your voice; if you
  didn't phrase it yourself, it poisons the corpus.
- Anything ghost-written.
- Sensitive personal info (medical, financial, legal). The cover letter
  agent will read this folder; don't give it things that shouldn't end
  up in writing.

## How the agent uses this

Per spec §5.3: the agent reads every `.md` file in this directory before
drafting. Every concrete experience claim in a cover letter still has to
cite a `bullets.yaml` id — voice-corpus is for tone, not for facts. If
a passage here contains a claim you don't want to repeat, either remove
the passage or trust that `bullets.yaml` / `company-facts.md` are the
authoritative sources for the agent's factual citations.

## Citation form

Cover-letter provenance entries that trace a sentence's tone or phrasing
back to this folder use:

```yaml
source: voice:nvidia-application-answers.md
```

Paths are relative to the `voice-corpus/` root.

## What's here now

- `nvidia-application-answers.md` — seeded from `NVIDIA/` on Phase 3 kickoff.
- _(add more)_
