# SU-06: Terminal Agent Poll Determinism Hardening

**Wave:** 2 (parallel correctness cluster)
**Requirements:** 1.6
**Dependencies:** None
**Dependents:** None

---

## Purpose

Harden the Stop hook and poll-on-stop mechanism so terminal agents (claude-code sessions) deterministically resume polling after completing work. This is the single biggest operational issue — agents go deaf after finishing a task.

## Requirements Traceability

- **1.6 (Terminal Agent Poll Determinism):** "Terminal agents don't deterministically poll after completing work."

## Dependencies

None.

## Behavior

### Current State
- Stop hook mechanism exists: `scripts/poll-on-stop.sh` checks inbox on agent stop
- Hook fires via Claude Code's Stop hook (configured in `~/.claude/settings.json`)
- `minion install-hooks` installs the hook
- Env vars `MINION_AGENT_NAME` and `MINION_PROJECT_DIR` are set at spawn time
- poll-on-stop.sh: checks inbox count, blocks stop if messages waiting, injects "You have N unread message(s). Poll now."
- Safety: `stop_hook_active=true` marker prevents infinite loops (one extra cycle max)

### Target Hardening

**Hardening 1: Verify Stop hook installation is robust**
- `minion install-hooks` must be idempotent — running it twice produces the same result
- If `~/.claude/settings.json` doesn't exist, create it with the hook
- If it exists but has no hooks section, add one
- If it exists with a different Stop hook, warn (don't overwrite silently)
- Verify: `scripts/poll-on-stop.sh` is executable and at the expected path

**Hardening 2: poll-on-stop.sh edge cases**
- If `minion` CLI is not installed (uv tool not in PATH), fail-open (allow stop)
- If `.work/minion.db` doesn't exist in MINION_PROJECT_DIR, fail-open
- If MINION_AGENT_NAME is empty or unset, fail-open
- If the `minion comms check-inbox` command itself errors, fail-open (never trap the agent)
- Timeout: if inbox check takes more than 5 seconds, fail-open
- The `stop_hook_active` marker must be reset after each cycle — verify it doesn't persist across sessions

**Hardening 3: Poll auto-restart consideration**
- Current: agents are told to poll via prompt discipline + Stop hook nudge
- Enhancement: after `complete_phase()` returns success, include a `poll_reminder` field in the result: `"poll_reminder": "Run: minion poll --agent <name>"`
- Enhancement: `poll_loop()` in polling.py could detect if the agent's last action was a complete_phase and auto-trigger a brief inbox check before returning to poll
- Do NOT implement auto-restart as a background daemon — this creates zombie processes. The nudge pattern (hook + result field) is safer.

**Hardening 4: Diagnostic command**
- Add `minion poll-status --agent <name>` that reports: is a poll PID file present? Is the PID alive? When was the last poll heartbeat? Is the Stop hook installed?
- This is diagnostic only — helps leads identify deaf agents

### Inputs/Outputs
- `install-hooks`: reads/writes `~/.claude/settings.json` — idempotent
- `poll-on-stop.sh`: reads `MINION_AGENT_NAME`, `MINION_PROJECT_DIR` env vars — returns exit code 0 (allow stop) or non-zero (block stop)
- `poll-status`: reads PID file, coordinator DB — returns status dict

## Constraints

- Stop hook must NEVER trap an agent permanently — fail-open on any error
- The `stop_hook_active` guard must prevent infinite hook loops
- No background processes spawned — nudge only, never force
- Must work on macOS (darwin) — bash script must be POSIX-compatible

## Edge Cases

1. **Multiple Claude Code sessions:** Each session has its own Stop hook invocation. The PID file prevents duplicate polls. If two sessions share an agent name, the second session's poll kills the first (by PID file) — this is expected.
2. **Agent deregistered but session alive:** Stop hook checks inbox — deregistered agent has no inbox. fail-open (allow stop). The hook should not error on deregistered agents.
3. **MINION_HOOKS_BYPASS=1:** Environment kill switch. If set, all hooks are no-ops. This is documented in CLAUDE.md.
4. **Hook script moved/deleted:** If `scripts/poll-on-stop.sh` is not at the path referenced in settings.json, Claude Code logs an error but continues. The hook is a soft enhancement, not a hard gate.
5. **Context compaction:** After compaction, agents lose memory of the poll loop. The Stop hook is the mechanical backup that doesn't depend on agent memory.

## Current State

- Stop hook exists and is partially functional
- poll-on-stop.sh exists
- install-hooks CLI command exists
- Main gap: edge case hardening and diagnostic tooling

## Test Contract

- **Test 1:** Run `minion install-hooks` twice. Assert `~/.claude/settings.json` has exactly one Stop hook entry (idempotent).
- **Test 2:** Simulate poll-on-stop.sh with MINION_AGENT_NAME unset. Assert exit code 0 (fail-open).
- **Test 3:** Simulate poll-on-stop.sh with messages in inbox. Assert exit code non-zero (block stop).
- **Test 4:** Simulate poll-on-stop.sh with `minion` CLI not in PATH. Assert exit code 0 (fail-open).
- **Test 5:** `complete_phase()` result includes `poll_reminder` field after successful phase completion.
