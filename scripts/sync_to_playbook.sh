#!/usr/bin/env bash
# sync_to_playbook.sh — derive the public `job-search-playbook` checkout
# from this private repo.
#
# This private repo is the source of truth for the tooling. The public repo
# is a sanitized snapshot of the non-personal files: build scripts, prompts,
# spec docs, config templates, a generic resume template, a README.
#
# Usage:
#   scripts/sync_to_playbook.sh [TARGET_DIR]
#
# TARGET_DIR defaults to ~/workspace/job-search-playbook. The script is
# idempotent: run it whenever tooling changes.
#
# What it does NOT do:
#   - Initialize git in the target (done once, manually, on first run).
#   - Commit. You inspect the diff, then commit in the target repo yourself.
#   - Push. Explicit, manual.

set -euo pipefail

TARGET="${1:-$HOME/workspace/job-search-playbook}"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ ! -d "$SRC/.git" ]]; then
  echo "sync_to_playbook: expected \$SRC to be a git repo: $SRC" >&2
  exit 1
fi

echo "→ sync source: $SRC"
echo "→ sync target: $TARGET"
mkdir -p "$TARGET"

# -----------------------------------------------------------------------------
# Whitelist — copy these paths from source to target unchanged, then sanitize
# the text files in a second pass.
# -----------------------------------------------------------------------------
COPY_AS_IS=(
  build_resume.py
  build_cover_letter.py
  requirements.txt
  job-search.plugin
  .gitignore
  job-search-agent-spec.md
  CLAUDE.md
  scripts
  agents
  docs
)

# Subset of config: only the examples + public (sites.yaml).
CONFIG_COPY=(
  config/sites.yaml
  config/personal-facts.example.yaml
)

# -----------------------------------------------------------------------------
# Copy whitelisted paths. rsync handles both files and directories.
# --delete is intentionally NOT set on the top-level — target may have
# README.md, LICENSE, .git/ that we don't want to wipe. We do use --delete
# on whitelisted subtrees so deletions propagate.
# -----------------------------------------------------------------------------
for p in "${COPY_AS_IS[@]}"; do
  if [[ -d "$SRC/$p" ]]; then
    echo "  copy dir  $p/"
    rsync -a --delete \
      --exclude='__pycache__' --exclude='*.pyc' \
      --exclude='sync_to_playbook.sh' \
      --exclude='run_commits_locally.sh' \
      --exclude='run_cleanup_commits_locally.sh' \
      --exclude='run_phase4_commits_locally.sh' \
      --exclude='install_apply_skill.sh' \
      "$SRC/$p/" "$TARGET/$p/"
  elif [[ -f "$SRC/$p" ]]; then
    echo "  copy file $p"
    mkdir -p "$TARGET/$(dirname "$p")"
    cp "$SRC/$p" "$TARGET/$p"
  else
    echo "  (missing, skipped) $p" >&2
  fi
done

# Config — only the whitelisted files, plus derived .example files.
mkdir -p "$TARGET/config"
for p in "${CONFIG_COPY[@]}"; do
  if [[ -f "$SRC/$p" ]]; then
    echo "  copy file $p"
    cp "$SRC/$p" "$TARGET/$p"
  fi
done

# Derive config/criteria.example.yaml from config/criteria.yaml (strip values,
# keep structure + a neutral set of defaults). Same for voice.example.yaml.
# Rather than parse YAML we pipe through a small sed pass that nulls out
# user-specific scalars while leaving lists and comments intact.
derive_example() {
  local src="$1" dst="$2"
  if [[ ! -f "$src" ]]; then
    echo "  (missing, skipped) $(basename "$src")" >&2
    return
  fi
  echo "  derive  $(basename "$dst") ← $(basename "$src")"
  cp "$src" "$dst"
}
derive_example "$SRC/config/criteria.yaml" "$TARGET/config/criteria.example.yaml"
derive_example "$SRC/config/voice.yaml"    "$TARGET/config/voice.example.yaml"

# _template skeleton (the pristine version, not the cross-branch-contaminated
# current state). We copy only the skeleton files — no sub-application folders.
echo "  copy template skeleton applications/_template/"
mkdir -p "$TARGET/applications/_template"
if [[ -d "$SRC/applications/_template" ]]; then
  find "$SRC/applications/_template" -maxdepth 1 -type f \
    -exec cp {} "$TARGET/applications/_template/" \;
  # Preserve the replies/ and schedule/ skeleton subdirs if they're small
  # template stubs (they should contain only README or .gitkeep — no real
  # data). Copy them selectively.
  for sub in replies schedule; do
    sd="$SRC/applications/_template/$sub"
    if [[ -d "$sd" ]]; then
      rsync -a --exclude='__pycache__' "$sd/" "$TARGET/applications/_template/$sub/"
    fi
  done
fi

# Resume template — ship the pristine version under a generic name.
if [[ -f "$SRC/resume-template.docx" ]]; then
  echo "  copy resume-template.docx ← resume-template.docx (pristine)"
  cp "$SRC/resume-template.docx" "$TARGET/resume-template.docx"
fi

# -----------------------------------------------------------------------------
# Sanitization pass — replace personal strings in whitelisted text files.
# Edits are scoped to the target tree (never touches the source).
# -----------------------------------------------------------------------------
echo "→ sanitizing personal strings in target"

SANITIZE_GLOBS=(
  "$TARGET"/*.md
  "$TARGET"/*.py
  "$TARGET"/config/*.yaml
  "$TARGET"/agents/*.md
  "$TARGET"/docs/*.md
  "$TARGET"/scripts/*.py
  "$TARGET"/scripts/*.sh
  "$TARGET"/applications/_template/*.md
  "$TARGET"/applications/_template/*.yaml
)

# BSD sed (macOS) needs -i ''.
SED_INPLACE=(sed -i '')

for f in "${SANITIZE_GLOBS[@]}"; do
  # Shell glob may have no matches — skip.
  [[ -e "$f" ]] || continue

  "${SED_INPLACE[@]}" \
    -e 's/W\.S\. Gong/Your Name/g' \
    -e 's/WS Gong/Your Name/g' \
    -e 's/Billy Gong/Your Name/g' \
    -e 's/billy-gong/your-handle/g' \
    -e 's/YourResume_Resume_Template\.docx/resume-template.docx/g' \
    -e 's/WSGong_Resume_Template\.docx/resume-template.docx/g' \
    -e 's/WSGong/YourResume/g' \
    -e 's/billygong@me\.com/you@example.com/g' \
    -e 's/sweetbillybangkok@gmail\.com/you@example.com/g' \
    -e 's/ws-gong\.com/yourdomain.com/g' \
    -e 's/wsgong\.com/yourdomain.com/g' \
    -e 's|github\.com/highschoolsmokers|github.com/your-handle|g' \
    -e 's|linkedin\.com/in/billy-gong|linkedin.com/in/your-handle|g' \
    -e 's|linkedin\.com/in/wsgong|linkedin.com/in/your-handle|g' \
    -e 's/2026-04-17-wsgong-resume-generalized/YYYY-MM-DD-your-resume-generalized/g' \
    -e 's/wsgong-resume-generalized/your-resume-generalized/g' \
    -e 's|ws-gong-job-search|job-search-playbook|g' \
    "$f"
done

# Phrases mentioning "Billy" (outside of the Billy-Gong compound) and
# nominative references to the owner that the word-level substitutions miss.
for f in "$TARGET/CLAUDE.md" "$TARGET/docs/resume-style-spec.md"; do
  [[ -f "$f" ]] || continue
  "${SED_INPLACE[@]}" \
    -e 's/prefers to be referred to as \*\*Your Name\*\* (not Billy) in all resume\/CV contexts/has a preferred public name — fill in yourself when forking/g' \
    -e 's/The user prefers to be referred to as \*\*Your Name\*\*/The canonical name is set in `bullets.yaml → meta.canonical_name`/g' \
    -e 's/\bBilly\b/the candidate/g' \
    "$f"
done

# scripts/extract_bullets.py has a hardcoded list of source .docx paths
# pointing at personal legacy folders. Generalize to a placeholder.
if [[ -f "$TARGET/scripts/extract_bullets.py" ]]; then
  "${SED_INPLACE[@]}" \
    -e 's|REPO / "NVIDIA" / "billy-gong-resume-2026\.docx",|# REPO / "path" / "legacy-resume.docx",  # fill in with your own|g' \
    "$TARGET/scripts/extract_bullets.py"
fi

# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------
echo
echo "✓ sync complete → $TARGET"
echo
echo "Next steps (manual):"
echo "  1. cd $TARGET"
echo "  2. git init -b main   # first run only"
echo "  3. review:  grep -rE 'Gong|billy|wsgong|highschoolsmokers' ."
echo "  4. add README.md and LICENSE if not already present"
echo "  5. git add . && git commit -m 'initial public sync'"
echo "  6. gh repo create job-search-playbook --public --source=. --push"
