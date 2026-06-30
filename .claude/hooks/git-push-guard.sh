#!/usr/bin/env bash
# PreToolUse hook (Bash matcher, scoped to `git push` via the settings `if`).
#
# Fetches origin, then for the current branch either:
#   - injects "N commits ahead of origin/main" (+ the commit list) as context, or
#   - returns permissionDecision "ask" when HEAD is already fully merged into
#     origin/main (stale: nothing to push that isn't already upstream).
#
# Reads the tool-call JSON on stdin; emits a PreToolUse hookSpecificOutput JSON.
# Never hard-blocks: on any unexpected state it allows the push.
#
# Note: "merged" is the fast-forward/merge-commit sense (HEAD is an ancestor of
# origin/main). A squash- or rebase-merged branch has different SHAs and reads
# as "ahead", not stale.
set -uo pipefail

input=$(cat)
cmd=$(printf '%s' "$input" | jq -r '.tool_input.command // ""' 2>/dev/null || printf '')

# Double-guard: only act on git push (the settings `if` is the first filter).
case "$cmd" in
  *"git push"*) ;;
  *) exit 0 ;;
esac

repo="${CLAUDE_PROJECT_DIR:-$(pwd)}"
cd "$repo" 2>/dev/null || exit 0
git rev-parse --git-dir >/dev/null 2>&1 || exit 0

branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)

fetch_note=""
git fetch origin --quiet 2>/dev/null || fetch_note="(could not fetch origin; comparison may be stale) "

allow_ctx() {  # $1 = additionalContext
  jq -nc --arg c "$1" \
    '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"allow",additionalContext:$c}}'
}

# No origin/main to compare against → allow, with a note.
if ! git rev-parse --verify --quiet origin/main >/dev/null 2>&1; then
  allow_ctx "${fetch_note}origin/main not found; skipping the ahead/stale check for branch '${branch}'."
  exit 0
fi

# HEAD already contained in origin/main → stale; ask before pushing.
if git merge-base --is-ancestor HEAD origin/main 2>/dev/null; then
  reason="${fetch_note}Branch '${branch}' is already fully merged into origin/main: every commit on HEAD is already upstream, so this push is redundant or re-pushes a stale branch. Confirm you still want to push."
  jq -nc --arg r "$reason" \
    '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"ask",permissionDecisionReason:$r}}'
  exit 0
fi

# Otherwise: show what would go up.
ahead=$(git log --oneline --no-decorate origin/main..HEAD 2>/dev/null)
count=$(printf '%s\n' "$ahead" | grep -c .)
allow_ctx "${fetch_note}Branch '${branch}' is ${count} commit(s) ahead of origin/main:
${ahead}"
exit 0
