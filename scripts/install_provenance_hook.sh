#!/usr/bin/env bash
# install_provenance_hook.sh — one-time per-clone setup that points git at
# the tracked hooks under .githooks/.
#
# After this runs, `git commit` invokes .githooks/pre-commit, which gates
# every commit through scripts/check_provenance.py --staged --block plus
# the bullets and resume linters. See spec §8.8.
#
# Run from the repo root:
#     bash scripts/install_provenance_hook.sh
set -euo pipefail

REPO="$(git rev-parse --show-toplevel)"
cd "$REPO"

if [ ! -d ".githooks" ] || [ ! -f ".githooks/pre-commit" ]; then
  echo "install_provenance_hook.sh: .githooks/pre-commit not found." >&2
  echo "  Run from the repo root after a fresh clone." >&2
  exit 1
fi

chmod +x .githooks/pre-commit
git config core.hooksPath .githooks

echo "Installed: core.hooksPath = .githooks"
echo
echo "Next commit will run .githooks/pre-commit."
echo "To uninstall: git config --unset core.hooksPath"
