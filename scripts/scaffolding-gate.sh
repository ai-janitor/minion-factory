#!/bin/bash
# scaffolding-gate.sh — Git pre-commit hook that enforces scaffolding-before-implementation
#
# Purpose: Block code file commits when the agent's assigned task has not yet
#          passed the scaffolding (plan) phase. Enforces the CLAUDE.md mandate:
#          "No implementation code until scaffolding is complete."
#
# Hook type: Git pre-commit (.git/hooks/pre-commit)
# Can block: Yes — exits non-zero to abort the commit
#
# Gating: Only activates when MINION_AGENT_NAME env var is set.
#         No env var = regular terminal session = hook is a no-op.
#
# Safety:
#   - MINION_HOOKS_BYPASS=1: instant kill switch, disables all enforcement
#   - If DB query fails, allow commit (fail-open)
#   - Only blocks on 'implementation' flow_type tasks in pre-plan phases
#
# Code extensions that trigger the check:
#   .py .ts .tsx .js .jsx .go .rs .c .cpp .h .java
#
# Always allowed (scaffolding artifacts):
#   .md .yaml .yml .json .toml .cfg .ini .txt .sh
#
# Install: minion install-hooks (symlinks into .git/hooks/pre-commit)
#   or manually: ln -sf ../../scripts/scaffolding-gate.sh .git/hooks/pre-commit

set -euo pipefail

# Safety: bypass kill switch
if [ "${MINION_HOOKS_BYPASS:-0}" = "1" ]; then
    exit 0
fi

# Gate: only activate for registered minion agents
AGENT_NAME="${MINION_AGENT_NAME:-}"
if [ -z "$AGENT_NAME" ]; then
    exit 0
fi

# Determine project directory
PROJECT_DIR="${MINION_PROJECT_DIR:-$(pwd)}"
DB_PATH="$PROJECT_DIR/.work/minion.db"

# If no DB, nothing to enforce
if [ ! -f "$DB_PATH" ]; then
    exit 0
fi

# Check if any staged files are code files
CODE_FILES=$(git diff --cached --name-only 2>/dev/null | grep -E '\.(py|ts|tsx|js|jsx|go|rs|c|cpp|h|java)$' || true)
if [ -z "$CODE_FILES" ]; then
    # No code files staged — scaffolding/config only, always allowed
    exit 0
fi

# Query DB for agent's implementation tasks in pre-scaffolding phases
# Pre-scaffolding = open, assigned, spec (before the plan phase which has gate:scaffolding)
BLOCKING_TASKS=$(sqlite3 "$DB_PATH" \
    "SELECT id FROM tasks
     WHERE assigned_to = '$AGENT_NAME'
       AND flow_type = 'implementation'
       AND status IN ('open', 'assigned', 'spec')
       AND status NOT IN ('closed', 'abandoned', 'stale', 'obsolete')" 2>/dev/null) || BLOCKING_TASKS=""

if [ -n "$BLOCKING_TASKS" ]; then
    TASK_LIST=$(echo "$BLOCKING_TASKS" | tr '\n' ',' | sed 's/,$//')
    echo "SCAFFOLDING GATE BLOCKED" >&2
    echo "Task(s) #$TASK_LIST have flow_type=implementation but have not completed the plan (scaffolding) phase." >&2
    echo "Complete the spec and plan phases before writing implementation code." >&2
    echo "Use: minion -C $PROJECT_DIR task complete-phase --task-id <ID> --agent $AGENT_NAME" >&2
    exit 1
fi

# All implementation tasks are past scaffolding, or no implementation tasks
exit 0
