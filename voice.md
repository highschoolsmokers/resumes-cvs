# Voice — cover letters

How a W.S. Gong cover letter sounds, calibrated from the real letters in
`voice/`. This file is the *sound*; the *shape* (job, structure, anti-patterns)
lives in `SPEC.md` §11 (Cover letters). It is the cover-letter counterpart to
`master-resume.md`: the source a tailored letter is written against.

The three config blocks near the end — **Letterhead**, **Length**, **Forbidden
phrases** — are also parsed by `scripts/build_cover_letter.py` at render time,
the same way `render_resume.py` parses `master-resume.md`.

## The sound

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

## Letterhead

- **Name:** W.S. Gong
- **Subhead:** Developer. Writer, Editor.
- **Contact:** San Francisco, CA · billygong@me.com · ws-gong.com/code · linkedin.com/in/billy-gong

## Length

- **Target:** 250–350 words
- **Hard max:** 500 words

## Forbidden phrases

Warn-only at render. Each is a generic tell. Keep this list short: per `SPEC.md`
§9 the fix for bad voice is fewer rules and more real examples, not a longer
list.

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
