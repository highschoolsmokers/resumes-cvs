# replies/

Drafts the `reply-drafter` agent produces for recruiter-question threads.

## Naming

- `<YYYY-MM-DD>-<topic>.md` — plain-prose draft body.
- `<YYYY-MM-DD>-<topic>.provenance.yaml` — sidecar; one `claims[]` entry
  per concrete claim in the body. `unsourced_claims: []` is mandatory
  (the pre-commit hook blocks otherwise).

`<topic>` is kebab-cased, ≤ 30 chars, and names the thread's dominant
theme — `screen-availability`, `eligibility-comp`, `tech-prescreen`.
Don't embed the recruiter's name; threads fork, names don't.

## Invariants

- The draft body is staged in `Mail.app → Drafts` with the thread's
  `In-Reply-To` / `References` headers preserved. The `.md` file is the
  audit trail — the authoritative copy lives in Mail.app.
- Every concrete personal claim traces to `config/personal-facts.yaml`;
  every experience claim traces to `bullets.yaml` or the committed
  resume. Anything not sourceable becomes a
  `[USER TO ANSWER: <question>]` placeholder — never a guess.
- No `config/voice.yaml → forbidden_phrases` in the body.
- The draft is NEVER sent by an agent. The user opens Mail.app and sends
  manually.

## When a `[USER TO ANSWER:]` placeholder lands

The drafter sets `tracker.yaml → next_action` to something like:

    "recruiter-reply pending — 2 question(s) need user input; see replies/<file>.md"

Once the user fills the placeholders (editing the draft in Mail.app or
asking the agent to update the `.md`), remove the next_action flag.

## See also

- `agents/reply-drafter.md` — the agent that writes these files.
- Spec §§6.7, 8.7, 8.8, 9.6.
