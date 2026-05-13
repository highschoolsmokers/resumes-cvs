#!/usr/bin/env bash
# run_cleanup_commits_locally.sh — land the test-drive cleanup commits.
#
# Why this script exists: the Cowork sandbox that produced the edits can't
# touch `.git/`, so the changes landed uncommitted in the working tree.
# This script replays them as three per-logical-unit commits per
# CLAUDE.md §1.2.
#
# Cleanup scope (findings from the Phase 1–3 test drive against Vercel):
#
#   1. .gitignore                    — add **/.docx_to_pdf_scratch/
#   2. agents/cover-letter-writer.md — fix bogus `--out` flag in merge_pdfs.py
#                                      examples (positional args only)
#   3. scripts/check_provenance.py   — skip applications/_template/ in bulk
#                                      modes (template placeholders are not
#                                      meant to resolve; was triggering 8
#                                      false-positive issues under --all).
#                                      Prereq for flipping the pre-commit
#                                      hook to --block per §2 Phase 3.
#
# Run from inside the repo root (the directory containing CLAUDE.md):
#
#     bash scripts/run_cleanup_commits_locally.sh
#
# Strict-mode (`set -euo pipefail`). Safe to re-run ONLY if none of the
# three commits below have landed yet; if partial, `git reset --mixed HEAD`
# and rerun, or comment out the completed steps.

set -euo pipefail

# ─── Preconditions ─────────────────────────────────────────────────────

if [[ ! -f CLAUDE.md || ! -f job-search-agent-spec.md ]]; then
  echo "run_cleanup_commits_locally.sh: run this from the Resumes/ repo root." >&2
  exit 2
fi

local_name="$(git config --local --get user.name || true)"
local_email="$(git config --local --get user.email || true)"

if [[ -z "$local_name" || -z "$local_email" ]]; then
  echo "run_cleanup_commits_locally.sh: local git identity not set."
  echo "  Per CLAUDE.md §1.3, identity must be LOCAL — no --global:"
  echo "    git config user.name  'W.S. Gong'"
  echo "    git config user.email 'billygong@me.com'"
  echo "  Then re-run this script."
  exit 2
fi

echo "Committing as: ${local_name} <${local_email}>"
echo "On branch:     $(git rev-parse --abbrev-ref HEAD)"
echo
read -r -p "Proceed? (y/N) " go
case "$go" in
  y|Y|yes|YES) ;;
  *) echo "aborted."; exit 1 ;;
esac

# ─── Helpers ───────────────────────────────────────────────────────────

commit_step() {
  # commit_step "<message>" <file> [<file>…]
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

# ─── Commits ───────────────────────────────────────────────────────────

commit_step "gitignore: add docx_to_pdf scratch dir" \
  .gitignore

commit_step "cover-letter-writer: correct merge_pdfs.py CLI form in docs" \
  agents/cover-letter-writer.md

commit_step "provenance: skip applications/_template/ in bulk modes" \
  scripts/check_provenance.py

# ─── Self-check ────────────────────────────────────────────────────────

echo
echo "All cleanup commits landed. Recent history:"
git log --oneline -10
echo
echo "Working tree status (untracked Vercel app folder is expected):"
git status --short
echo
echo "Sanity check: provenance sweep across applications/ and archive/."
echo "(If you've run the test drive, this should report 2 sidecar(s) OK.)"
python3 scripts/check_provenance.py --all || true
