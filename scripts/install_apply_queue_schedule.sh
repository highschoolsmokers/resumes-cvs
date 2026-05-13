#!/usr/bin/env bash
# install_apply_queue_schedule.sh — one-time setup that registers the
# apply-queue drainer with the scheduled-tasks MCP.
#
# The drainer runs every 30 min by default and invokes Claude Code in
# headless mode (`claude -p '/apply <url>'`) for each queued URL. URLs land
# in queue.jsonl via `scripts/queue_add.py`.
#
# Why this is a shell script rather than Python: the scheduled-tasks MCP
# is a Claude Code MCP — easiest to register from a Claude Code session.
# Run this once from inside an interactive Claude Code session:
#
#     bash scripts/install_apply_queue_schedule.sh
#
# Claude will then call the scheduled-tasks tool to register the task.

set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
INTERVAL_MINUTES="${INTERVAL_MINUTES:-30}"

cat <<EOF
Apply-queue scheduled-task setup
================================

Run this command **inside an interactive Claude Code session** (not from a
shell directly — the MCP is only callable from Claude):

    Register a scheduled task using mcp__scheduled-tasks__create_scheduled_task:
      name:        apply-queue-drainer
      interval:    every ${INTERVAL_MINUTES} minutes
      command:     cd ${REPO} && python3 scripts/apply_queue.py --once

To verify after install:
    list current scheduled tasks (mcp__scheduled-tasks__list_scheduled_tasks)
    you should see one named "apply-queue-drainer" with the interval above.

To uninstall:
    delete the task by name (mcp__scheduled-tasks__delete_scheduled_task).
EOF
