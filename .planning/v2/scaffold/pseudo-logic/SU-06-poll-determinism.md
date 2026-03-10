# SU-06 Pseudo-Logic: Terminal Agent Poll Determinism Hardening

## File: `scripts/poll-on-stop.sh`

```bash
# Edge case guards to add at top of script:

# Guard 1: MINION_AGENT_NAME must be set
# if [ -z "$MINION_AGENT_NAME" ]; then exit 0; fi  # fail-open

# Guard 2: MINION_HOOKS_BYPASS kill switch
# if [ "$MINION_HOOKS_BYPASS" = "1" ]; then exit 0; fi

# Guard 3: minion CLI must be in PATH
# if ! command -v minion &>/dev/null; then exit 0; fi  # fail-open

# Guard 4: .work/minion.db must exist
# if [ ! -f "$MINION_PROJECT_DIR/.work/minion.db" ]; then exit 0; fi

# Guard 5: 5-second timeout on inbox check
# inbox_count=$(timeout 5 minion comms check-inbox --agent "$MINION_AGENT_NAME" --count-only 2>/dev/null)
# if [ $? -ne 0 ]; then exit 0; fi  # fail-open on timeout or error

# Guard 6: stop_hook_active marker reset
# Verify marker file is created per-invocation, not persistent across sessions
# marker_file="/tmp/minion_stop_hook_${MINION_AGENT_NAME}"
# if [ -f "$marker_file" ]; then rm "$marker_file"; exit 0; fi  # one extra cycle max
# touch "$marker_file"
```

## File: `src/minion/polling.py` — new function

```python
def poll_status(agent_name: str) -> dict:
    """Diagnostic: report poll health for an agent.

    # 1. Check PID file: ~/.minion/poll-<agent_name>.pid
    #    - If file exists: read PID, check if process alive (os.kill(pid, 0))
    #    - Report: pid_file_exists, pid_alive, pid_value
    #
    # 2. Check last poll heartbeat: query coordinator DB
    #    - SELECT last_seen FROM agents WHERE name = agent_name
    #    - Report: last_heartbeat, seconds_since_heartbeat
    #
    # 3. Check Stop hook installed:
    #    - Read ~/.claude/settings.json
    #    - Check hooks.Stop contains poll-on-stop.sh reference
    #    - Report: hook_installed, hook_path
    #
    # Return: {"pid_file": bool, "pid_alive": bool, "last_heartbeat": str,
    #          "stale": bool (>5min since heartbeat), "hook_installed": bool}
    """
```

## File: `src/minion/tasks/update_task.py` — in `complete_phase()`

```python
# After successful phase completion (existing return dict):
# Add to result: "poll_reminder": f"Run: minion poll --agent {agent_name}"
# This is advisory — the caller can ignore it
```

## File: `src/minion/lifecycle.py` — `install_hooks()`

```python
# Idempotency verification:
# 1. Read ~/.claude/settings.json (or create empty {} if missing)
# 2. Check if hooks.Stop already contains our script path
# 3. If already present with correct config: return {"status": "already installed"}
# 4. If present with different config: WARN, don't overwrite
# 5. If absent: add hook config, write file
# 6. Verify scripts/poll-on-stop.sh exists and is executable
```
