#!/bin/bash
# poll-on-stop.sh — Claude Code Stop hook that enforces polling discipline
#
# Purpose: When a minion agent finishes responding, check if there are unread
#          messages in their inbox. If yes, block the stop and force the agent
#          to poll. This makes polling mechanical — agents cannot go idle when
#          messages are waiting.
#
# Hook type: Stop (fires when Claude finishes responding)
# Can block: Yes — returns {"decision":"block","reason":"..."} to force continuation
#
# Gating: Only activates when MINION_AGENT_NAME env var is set.
#         No env var = regular terminal session = hook is a no-op.
#
# Safety:
#   - stop_hook_active: if true, we're in a continuation loop — allow stop
#   - MINION_HOOKS_BYPASS=1: instant kill switch, disables all enforcement
#   - If minion CLI fails or inbox check errors, allow stop (fail-open)
#
# PSEUDO: read JSON from stdin
# PSEUDO: if MINION_HOOKS_BYPASS=1 → exit 0 (allow stop)
# PSEUDO: if no MINION_AGENT_NAME → exit 0 (not a minion agent)
# PSEUDO: if stop_hook_active=true → exit 0 (prevent infinite loop)
# PSEUDO: count = minion check-inbox --agent $NAME --count-only
# PSEUDO: if count > 0 → output {"decision":"block","reason":"..."}
# PSEUDO: else → exit 0 (allow stop)

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

# Read JSON payload from stdin
INPUT=$(cat)

# Safety: prevent infinite loop — if we already blocked once, allow stop
STOP_HOOK_ACTIVE=$(echo "$INPUT" | jq -r '.stop_hook_active // false')
if [ "$STOP_HOOK_ACTIVE" = "true" ]; then
    exit 0
fi

# Determine project directory — use MINION_PROJECT_DIR if set, else cwd
PROJECT_DIR="${MINION_PROJECT_DIR:-$(pwd)}"
PROJECT_FLAG=""
if [ -n "$PROJECT_DIR" ]; then
    PROJECT_FLAG="-C $PROJECT_DIR"
fi

# Check inbox for unread messages via direct DB query (READ-ONLY — do not consume messages)
# Using check-inbox would mark messages as read, eating them before the agent sees them.
DB_PATH="$PROJECT_DIR/.work/minion.db"
if [ ! -f "$DB_PATH" ]; then
    exit 0  # No DB = no messages to check
fi
INBOX_COUNT=$(sqlite3 "$DB_PATH" \
    "SELECT COUNT(*) FROM messages WHERE to_agent = '$AGENT_NAME' AND read_flag = 0;" 2>/dev/null) || INBOX_COUNT=0

if [ "$INBOX_COUNT" -gt 0 ]; then
    # Messages waiting — block the stop, force agent to poll
    cat <<EOF
{
    "decision": "block",
    "reason": "You have $INBOX_COUNT unread message(s) in your inbox. Run: minion -C $PROJECT_DIR poll --agent $AGENT_NAME"
}
EOF
else
    # Also check for open tasks assigned to this agent
    TASK_COUNT=$(minion $PROJECT_FLAG task list 2>/dev/null \
        | jq -r "[.tasks[] | select(.assigned_to == \"$AGENT_NAME\")] | length // 0" 2>/dev/null) || TASK_COUNT=0

    if [ "$TASK_COUNT" -gt 0 ]; then
        cat <<EOF
{
    "decision": "block",
    "reason": "You have $TASK_COUNT open task(s) assigned to you. Run: minion -C $PROJECT_DIR poll --agent $AGENT_NAME"
}
EOF
    else
        # No messages, no tasks — allow stop
        exit 0
    fi
fi
