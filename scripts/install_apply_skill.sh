#!/usr/bin/env bash
# install_apply_skill.sh — install the `apply` skill into the user-level
# Cowork skills directory so new Cowork sessions discover it.
#
# Why this script exists: project-level skills at Resumes/.claude/skills/
# are NOT discovered by new Cowork tasks (empirically verified —
# mnt/.claude/skills/ inside the sandbox is read-only / bundled skills
# only). The user-level discovery path lives outside the sandbox mount,
# parallel to ~/Documents/Claude/Scheduled/ where the scheduled-task MCP
# writes.
#
# Run this ONCE on your real machine from the Resumes/ repo root:
#
#     bash scripts/install_apply_skill.sh
#
# Then quit + reopen Cowork (or start a new task) — the `apply` skill
# should now appear in <available_skills> and trigger on "apply to <url>".

set -euo pipefail

SRC_DIR="$(pwd)/.claude/skills/apply"
PARENT="$HOME/Documents/Claude/Skills"
DEST_DIR="$PARENT/apply"

if [[ ! -d "$SRC_DIR" ]]; then
  echo "install_apply_skill.sh: cannot find $SRC_DIR"
  echo "  Run this from the Resumes/ repo root." >&2
  exit 2
fi

if [[ ! -d "$HOME/Documents/Claude" ]]; then
  echo "install_apply_skill.sh: $HOME/Documents/Claude does not exist."
  echo "  That's the Cowork user-data root — if it's missing, Cowork may"
  echo "  not be installed, or it stores user data elsewhere on your"
  echo "  machine. Open Cowork → Settings to find the right path, then"
  echo "  edit PARENT in this script."
  exit 2
fi

mkdir -p "$PARENT"
# cp -r the whole skill dir so any references / helper files travel too.
# Remove an existing install first to keep the destination clean.
rm -rf "$DEST_DIR"
cp -r "$SRC_DIR" "$DEST_DIR"

echo "Installed: $DEST_DIR"
echo
echo "Next: quit + reopen Cowork (or start a fresh task). The 'apply' skill"
echo "should show up in <available_skills> and trigger on phrases like"
echo "'apply to <url>' or 'prep this job <url>'."
