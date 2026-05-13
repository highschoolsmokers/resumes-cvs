#!/usr/bin/env bash
# run_commits_locally.sh — one-shot script to land Phase 1 + Phase 2 as a
# discrete commit history on your local machine.
#
# Why this script exists: the Cowork sandbox that produced these files
# can't touch `.git/`, so every file landed uncommitted in the working
# tree. This script replays them as the per-logical-unit commits called
# for in CLAUDE.md §1.2 — one commit per component, legible history.
#
# Run from inside the repo root (the directory containing CLAUDE.md):
#
#     bash scripts/run_commits_locally.sh
#
# The script is strict-mode (`set -euo pipefail`) and will stop at the
# first failed step. If it stops, inspect `git status` and either fix
# the issue or revert with `git reset --mixed HEAD` and rerun.
#
# Safe to re-run ONLY if you haven't yet made any of the commits below.
# If partial commits exist, either reset or comment out the already-done
# sections before re-running.

set -euo pipefail

# ─── Preconditions ─────────────────────────────────────────────────────

if [[ ! -f CLAUDE.md || ! -f job-search-agent-spec.md ]]; then
  echo "run_commits_locally.sh: run this from the Resumes/ repo root." >&2
  exit 2
fi

# Git identity must be LOCAL to this repo (CLAUDE.md §1.3). Confirm.
local_name="$(git config --local --get user.name || true)"
local_email="$(git config --local --get user.email || true)"

if [[ -z "$local_name" || -z "$local_email" ]]; then
  echo "run_commits_locally.sh: local git identity not set."
  echo "  Per CLAUDE.md §1.3, identity must be LOCAL — no --global:"
  echo "    git config user.name  'W.S. Gong'"
  echo "    git config user.email 'billygong@me.com'"
  echo "  Then re-run this script."
  exit 2
fi

echo "Committing as: ${local_name} <${local_email}>"
echo "On branch:     $(git rev-parse --abbrev-ref HEAD)"
echo

# Sanity check — we should be on a branch that's OK to land these commits on.
# Per CLAUDE.md §1.1, `main` is always submittable; if you're not sure,
# create a scaffold branch first and cherry-pick or merge it in later.
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
  # If nothing was staged (all paths skipped), skip the commit entirely.
  if git diff --cached --quiet; then
    echo "   (nothing staged — skipping commit)"
    return 0
  fi
  git commit -m "$msg"
}

# ─── Phase 1: spec, playbook, search infrastructure ────────────────────

commit_step "gitignore: extend for sqlite journal + seen.db binary" \
  .gitignore

commit_step "spec: initial draft of job-search-agent-spec.md" \
  job-search-agent-spec.md

commit_step "CLAUDE.md: phase 1 + phase 2 build playbook" \
  CLAUDE.md

commit_step "config: add criteria.yaml (targets, excludes, comp floor)" \
  config/criteria.yaml

commit_step "config: add sites.yaml (greenhouse/lever/ashby + hn)" \
  config/sites.yaml

commit_step "agents: add search-agent and fit-scorer prompts" \
  agents/search-agent.md \
  agents/fit-scorer.md

commit_step "search: driver + README" \
  search/run.py \
  search/README.md

commit_step "requirements: pin phase 1 + phase 2 deps" \
  requirements.txt

# ─── Phase 2: tailoring ────────────────────────────────────────────────

commit_step "build_resume: support --plan/--out with unpacked OOXML sibling" \
  build_resume.py

commit_step "bullets: closed-universe source of truth for resume claims" \
  bullets.yaml

commit_step "agents: add resume-tailor prompt" \
  agents/resume-tailor.md

commit_step "scripts: extract_bullets + bullets_lookup (planning helpers)" \
  scripts/extract_bullets.py \
  scripts/bullets_lookup.py

commit_step "scripts: docx_to_pdf + merge_pdfs (libreoffice + pypdf)" \
  scripts/docx_to_pdf.py \
  scripts/merge_pdfs.py

commit_step "scripts: lint_bullets (structural linter over bullets.yaml)" \
  scripts/lint_bullets.py

commit_step "scripts: check_provenance (closed-universe hallucination guard)" \
  scripts/check_provenance.py

commit_step "scripts: url_ingest (single-listing on-ramp)" \
  scripts/url_ingest.py

commit_step "scripts: backprop_edits (prompted bullets.yaml update)" \
  scripts/backprop_edits.py

commit_step "applications: add _template scaffold (phase 2)" \
  applications/_template/README.md \
  applications/_template/tracker.yaml \
  applications/_template/notes.md \
  applications/_template/listing.json \
  applications/_template/listing.md \
  applications/_template/resume-plan.yaml \
  applications/_template/fit-report.md \
  applications/_template/resume.provenance.yaml

# ─── Phase 3: cover letter writer ──────────────────────────────────────

commit_step "voice-corpus: seed with NVIDIA application answers + README" \
  voice-corpus/README.md \
  voice-corpus/nvidia-application-answers.md

commit_step "config: add voice.yaml (length, forbidden phrases, scheduling)" \
  config/voice.yaml

commit_step "agents: add cover-letter-writer prompt" \
  agents/cover-letter-writer.md

commit_step "build_cover_letter: render cover-letter.md to docx with letterhead" \
  build_cover_letter.py

commit_step "applications: extend _template with cover letter artifacts" \
  applications/_template/company-facts.md \
  applications/_template/cover-letter.md \
  applications/_template/cover-letter.provenance.yaml

# ─── Self-check ────────────────────────────────────────────────────────

echo
echo "All commits landed. Recent history:"
git log --oneline -20
echo
echo "Working tree status (should be clean except for ignored files):"
git status --short

# ─── Optional: install the provenance pre-commit hook ──────────────────

hook=.git/hooks/pre-commit
if [[ ! -x "$hook" ]]; then
  cat <<'EOF'

─── Optional: install the provenance pre-commit hook ───

Now that Phase 3 is landed, the recommended hook is --block mode: any
commit that touches a resume.md / cover-letter.md / replies/*.md without
a fully-sourced provenance sidecar is rejected, not merely warned.

Install (phase 3 recommended):

    cat > .git/hooks/pre-commit <<'HOOK'
    #!/usr/bin/env bash
    set -e
    python3 scripts/check_provenance.py --staged --block
    HOOK
    chmod +x .git/hooks/pre-commit

If you want a warning-only hook during early iteration, swap --block
for --warn. Per CLAUDE.md §6: never bypass the hook with --no-verify.
EOF
fi
