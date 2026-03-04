#!/bin/bash
# poll-on-stop.sh — Claude Code Stop hook that enforces polling discipline
#
# Purpose: When a minion agent finishes responding, ALWAYS block the stop and
#          force the agent back into minion poll. The agent never goes idle —
#          it's always either working or blocked inside poll waiting for the
#          next message.
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
# PSEUDO: ALWAYS block stop → force agent into minion poll
# PSEUDO: agent never goes idle — poll blocks waiting for next message

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

# ALWAYS block the stop — force agent back into poll
# Agent never goes idle. Poll blocks waiting for next message.
cat <<EOF
{
    "decision": "block",
    "reason": "Run: minion -C $PROJECT_DIR poll --agent $AGENT_NAME"
}
EOF
