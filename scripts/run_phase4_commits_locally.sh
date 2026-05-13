#!/usr/bin/env bash
# run_phase4_commits_locally.sh — land Phase 4 (tracker / reply-drafter /
# scheduler) as per-logical-unit commits per CLAUDE.md §1.2.
#
# Why this script exists: the Cowork sandbox that produced the edits can't
# touch `.git/`, so the new files and edits landed uncommitted in the
# working tree. This script replays them as seven commits on the current
# branch (presumably `main` — Phase 4 infra is not per-application).
#
# Phase 4 scope (CLAUDE.md §2, spec §§6, 8.7, 9.4–9.7):
#
#   1. config/personal-facts.example.yaml    — committed scaffold; the
#      real config/personal-facts.yaml is gitignored and filled by the
#      user locally. Closed universe for reply-drafter personal claims.
#   2. scripts/sweep.py + scripts/dashboard.py — deterministic halves of
#      the tracker loop. sweep.py finds unseen Apple Mail messages and
#      writes batch.jsonl; dashboard.py renders dashboard.md from every
#      tracker.yaml. The agent in step 3 drives sweep.py.
#   3. agents/tracker-agent.md                — classifies each unseen
#      thread (screen-request | scheduling | questions | rejection |
#      offer | other), moves it into JobSearch/<Company>, updates
#      tracker.yaml, hands off to the next agent.
#   4. agents/reply-drafter.md                — drafts answers to
#      recruiter questions; every concrete claim traces to the closed
#      universe (personal-facts / bullets / voice-corpus). Unanswerable
#      questions become [USER TO ANSWER: …] placeholders — never guesses.
#      Stages drafts in Mail.app → Drafts; NEVER sends.
#   5. agents/scheduler.md                    — proposes up to 3 slots
#      from Google Calendar availability, creates [TENTATIVE] holds,
#      stages a reply draft. Never auto-books Calendly. Promotion to
#      confirmed requires user acknowledgement.
#   6. applications/_template expansion       — replies/ and schedule/
#      skeletons + README updates + tracker.yaml schema bumps
#      (company_domains, last_checked_at).
#   7. requirements.txt + CLAUDE.md           — python-dateutil dep for
#      scheduler time parsing; Phase 4 status marker; open questions
#      #1 and #6 resolved (Notion=no, personal-facts=scaffold-only).
#
# Run from inside the repo root (the directory containing CLAUDE.md):
#
#     bash scripts/run_phase4_commits_locally.sh
#
# Safe to re-run only if none of the seven commits have landed yet.
# Partial state → `git reset --mixed <sha-before-phase-4>` and rerun, or
# comment out the completed steps.

set -euo pipefail

# ─── Preconditions ─────────────────────────────────────────────────────

if [[ ! -f CLAUDE.md || ! -f job-search-agent-spec.md ]]; then
  echo "run_phase4_commits_locally.sh: run this from the Resumes/ repo root." >&2
  exit 2
fi

local_name="$(git config --local --get user.name || true)"
local_email="$(git config --local --get user.email || true)"

if [[ -z "$local_name" || -z "$local_email" ]]; then
  echo "run_phase4_commits_locally.sh: local git identity not set."
  echo "  Per CLAUDE.md §1.3, identity must be LOCAL — no --global:"
  echo "    git config user.name  'W.S. Gong'"
  echo "    git config user.email 'billygong@me.com'"
  echo "  Then re-run this script."
  exit 2
fi

echo "Committing as: ${local_name} <${local_email}>"
echo "On branch:     $(git rev-parse --abbrev-ref HEAD)"
echo
echo "Phase 4 lands as 7 commits on the CURRENT branch. Phase 4 infra is"
echo "cross-application (agents/, scripts/, config/), so main is the right"
echo "target — not a per-app branch. If you're on an app branch, Ctrl-C now."
echo
read -r -p "Proceed? (y/N) " go
case "$go" in
  y|Y|yes|YES) ;;
  *) echo "aborted."; exit 1 ;;
esac

# ─── Helpers ───────────────────────────────────────────────────────────

commit_step() {
  # commit_step "<message>" <file-or-dir> [<file-or-dir>…]
  local msg="$1"; shift
  echo
  echo "→ $msg"
  for f in "$@"; do
    if [[ -e "$f" || -L "$f" ]]; then
      git add -- "$f"
    else
      echo "   (skip: $f does not exist)"
    fi
  done
  if git diff --cached --quiet; then
    echo "   (nothing staged — skipping commit)"
    return 0
  fi
  git commit -m "$msg"
}

# Sanity: refuse if personal-facts.yaml is somehow staged (it's gitignored,
# but if a past session touched it in a non-ignored location, abort).
if git ls-files --cached --error-unmatch config/personal-facts.yaml >/dev/null 2>&1; then
  echo "run_phase4_commits_locally.sh: config/personal-facts.yaml is tracked!"
  echo "  It must be gitignored (see .gitignore and CLAUDE.md §1.4)."
  echo "  Run:   git rm --cached config/personal-facts.yaml"
  echo "  Then re-run this script."
  exit 2
fi

# ─── Commits ───────────────────────────────────────────────────────────

commit_step "personal-facts: commit example scaffold for reply-drafter universe" \
  config/personal-facts.example.yaml

commit_step "sweep: deterministic Apple Mail sweep + dashboard renderer" \
  scripts/sweep.py \
  scripts/dashboard.py

commit_step "tracker-agent: classify + route every new thread per spec §9.4" \
  agents/tracker-agent.md

commit_step "reply-drafter: closed-universe recruiter-question drafts per spec §9.6" \
  agents/reply-drafter.md

commit_step "scheduler: propose slots + tentative calendar holds per spec §9.7" \
  agents/scheduler.md

commit_step "applications/_template: replies/ + schedule/ skeletons, tracker schema bump" \
  applications/_template/README.md \
  applications/_template/tracker.yaml \
  applications/_template/replies \
  applications/_template/schedule

commit_step "phase 4: python-dateutil dep; CLAUDE.md status + open-Q resolutions" \
  requirements.txt \
  CLAUDE.md

# ─── Self-check ────────────────────────────────────────────────────────

echo
echo "All Phase 4 commits landed. Recent history:"
git log --oneline -12
echo
echo "Working tree status (untracked app folders + gitignored personal-facts.yaml are expected):"
git status --short
echo
echo "Sanity check 1: provenance sweep (template skip should still apply)."
python3 scripts/check_provenance.py --all || true
echo
echo "Sanity check 2: dashboard renders from current trackers."
python3 scripts/dashboard.py
echo "  (Regenerated dashboard.md at repo root; gitignored.)"
echo
echo "Next setup steps (NOT automated by this script):"
echo "  1. Copy config/personal-facts.example.yaml → config/personal-facts.yaml"
echo "     and fill in the fields you're comfortable disclosing. Gitignored."
echo "  2. Grant Cowork / Claude Code access to the Control-your-Mac MCP"
echo "     (Apple Mail + AppleScript) and the Google Calendar MCP."
echo "  3. Register the every-2h sweep as a scheduled task once you're ready"
echo "     for the tracker to run on its own (see CLAUDE.md §2 Phase 4 create list)."
