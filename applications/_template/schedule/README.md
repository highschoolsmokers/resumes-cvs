# schedule/

Slot proposals the `scheduler` agent produces for scheduling threads.

## Naming

- `<YYYY-MM-DD>-<event>.yaml` — one file per scheduling round.

`<YYYY-MM-DD>` is the day the scheduler ran (not the interview date).
`<event>` names the stage — `recruiter-call`, `hiring-manager`,
`technical-screen`, `onsite-loop`. Stage vocabulary lives in
`config/voice.yaml → scheduling_preferences.known_stages`.

If the recruiter reschedules, add a new `<YYYY-MM-DD>-<event>.yaml` —
do not overwrite the original. The history is the audit trail.

## Invariants

- Google Calendar is the source of truth; this YAML is the audit trail.
  Each `candidate_slots[*].tentative_event_id` points to a real event
  whose title starts with `[TENTATIVE]`.
- The prefix `[TENTATIVE]` is the invariant the tracker, archiver, and
  user rely on to distinguish holds from confirmed interviews. Never
  omit it until the user confirms a slot.
- `source_phrases[]` quote the recruiter's email verbatim — that's how
  the user verifies the parse before confirming.
- If a Calendly link is present, `calendly.link` is set, `calendly.note`
  explains we did not auto-book, `candidate_slots[]` is empty, and no
  tentative calendar events are created.
- `confirmed: false` on first write. The promotion flow (step 7 in
  `agents/scheduler.md`) flips it to `true` and strips the `[TENTATIVE]`
  prefix from the winning event.

## When the user confirms

User says "confirmed slot 2" (or similar). Scheduler's promotion flow:

1. Updates the winning event: strip `[TENTATIVE]`, append
   `Confirmed on <ISO date>.` to the description.
2. Deletes the other tentative events.
3. Sets `confirmed: true` and `confirmed_slot_index: <n>` in this YAML.
4. Sets `tracker.yaml → next_action: "interview on <date/time>"`.

## See also

- `agents/scheduler.md` — the agent that writes these files.
- Spec §§6.8, 9.7.
- `config/voice.yaml → scheduling_preferences` — day window, preferred
  blocks, buffers, tentative title template.
- `config/personal-facts.yaml → availability.scheduling_hard_nos` —
  blocking constraints that override preferences.
