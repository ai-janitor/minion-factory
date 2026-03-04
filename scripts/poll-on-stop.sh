#!/bin/bash
# poll-on-stop.sh — Claude Code Stop hook that enforces polling discipline
#
# Purpose: When a minion agent finishes responding, check if there are unread
#          messages. If yes, block the stop and force the agent into poll.
#          If inbox is empty, allow stop — poll is already running in background
#          and will catch new messages.
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
# PSEUDO: check inbox for unread messages
# PSEUDO: if inbox empty → exit 0 (allow stop, poll catches new messages)
# PSEUDO: if inbox has messages → block stop, force agent into poll

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

# Determine project directory — use MINION_PROJECT_DIR if set, else walk up from cwd
# If walk-up finds nothing, use cwd as fallback — minion auto-inits .work/ on first run
PROJECT_DIR="${MINION_PROJECT_DIR:-}"
if [ -z "$PROJECT_DIR" ]; then
    # Walk up from cwd looking for .work/minion.db
    DIR="$(pwd)"
    while [ "$DIR" != "/" ]; do
        if [ -f "$DIR/.work/minion.db" ]; then
            PROJECT_DIR="$DIR"
            break
        fi
        DIR="$(dirname "$DIR")"
    done
fi

# Fallback: use cwd — minion will auto-init .work/ when poll runs
if [ -z "$PROJECT_DIR" ]; then
    PROJECT_DIR="$(pwd)"
fi

# Check inbox for unread messages — if empty, allow stop (poll catches new messages)
# Use direct sqlite3 for speed — avoid full CLI overhead
DB_PATH="$PROJECT_DIR/.work/minion.db"
if [ -f "$DB_PATH" ]; then
    # Count unread direct messages + unread broadcasts
    UNREAD=$(sqlite3 "$DB_PATH" "
        SELECT COUNT(*) FROM messages WHERE to_agent = '$AGENT_NAME' AND read_flag = 0
    " 2>/dev/null || echo "0")

    UNREAD_BROADCAST=$(sqlite3 "$DB_PATH" "
        SELECT COUNT(*) FROM messages
        WHERE to_agent = 'all' AND from_agent != '$AGENT_NAME'
        AND id NOT IN (SELECT message_id FROM broadcast_reads WHERE agent_name = '$AGENT_NAME')
    " 2>/dev/null || echo "0")

    TOTAL_UNREAD=$((UNREAD + UNREAD_BROADCAST))

    # Inbox empty → allow stop (poll is running and will catch new messages)
    if [ "$TOTAL_UNREAD" -eq 0 ]; then
        exit 0
    fi
fi

# Unread messages exist — block stop, force agent into poll
cat <<EOF
{
    "decision": "block",
    "reason": "You have $TOTAL_UNREAD unread message(s). Run: minion -C $PROJECT_DIR poll --agent $AGENT_NAME"
}
EOF
