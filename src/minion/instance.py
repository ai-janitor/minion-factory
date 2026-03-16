"""Instance ID resolution — unique identifiers for multi-instance daemon spawns.

Purpose: Generate and resolve instance IDs so multiple daemons of the same agent
template can coexist with isolated PID files, state files, log files, and poll processes.
Rationale: Centralizes instance naming logic so spawn.py, recruit.py, daemon.py, and
polling.py all use the same scheme.
Responsibility: Instance ID generation and agent-name-to-file-key resolution.
NOT responsible for: spawning daemons, writing PID files, or managing state.

ASSUMPTIONS:
- Instance IDs are numeric suffixes: agent-2, agent-3, etc. The first instance has no
  suffix (bare name = instance 1, implicit).
- Scanning for existing instances uses PID file glob in .work/.minion-poll/ and state
  file glob in .minion-swarm/state/. Both directories may not exist (fresh project).
- The "alive" check uses os.kill(pid, 0) which is best-effort on macOS (same caveat
  as polling.py orphan detection).
- Instance ID assignment is NOT atomic — two concurrent spawns could race. This is
  acceptable because spawn-party serializes daemon starts with 0.25s sleep between them.
"""

from __future__ import annotations

import glob
import json
import os
import re


def resolve_file_key(agent: str, instance_id: str | None = None) -> str:
    """Return the file-system key for an agent instance.

    Examples:
        resolve_file_key("redmage-jr") -> "redmage-jr"
        resolve_file_key("redmage-jr", "2") -> "redmage-jr-2"
        resolve_file_key("redmage-jr", None) -> "redmage-jr"
        resolve_file_key("redmage-jr", "") -> "redmage-jr"

    This key is used for PID files, state files, log files, and poll pidfiles.
    Backward compatible: None/empty instance_id returns bare agent name.
    """
    if instance_id:
        return f"{agent}-{instance_id}"
    return agent


def next_instance_id(agent: str, runtime_dir: str) -> str:
    """Scan runtime directories for existing instances and return next numeric suffix.

    Scans:
      - {runtime_dir}/.minion-poll/{agent}*.pid  (poll PID files)
      - {runtime_dir}/.minion-swarm/state/{agent}*.json  (daemon state files)

    Returns "2" if only the bare agent exists, "3" if agent-2 exists, etc.
    Returns "2" if no instances exist at all (caller wants a second instance;
    the first is the bare-name instance).

    Args:
        agent: Base agent name (without any instance suffix).
        runtime_dir: Project root directory (contains .work/ and .minion-swarm/).
    """
    existing: set[int] = {1}  # bare name = implicit instance 1

    # Scan poll PID files: .work/.minion-poll/{agent}*.pid
    poll_dir = os.path.join(runtime_dir, ".work", ".minion-poll")
    for pidfile in glob.glob(os.path.join(poll_dir, f"{agent}*.pid")):
        _extract_instance_number(os.path.basename(pidfile), agent, ".pid", existing)

    # Scan daemon state files: .minion-swarm/state/{agent}*.json
    state_dir = os.path.join(runtime_dir, ".minion-swarm", "state")
    for statefile in glob.glob(os.path.join(state_dir, f"{agent}*.json")):
        _extract_instance_number(os.path.basename(statefile), agent, ".json", existing)

    # Find next available number
    n = 2
    while n in existing:
        n += 1
    return str(n)


def _extract_instance_number(
    filename: str, agent: str, suffix: str, existing: set[int]
) -> None:
    """Parse an instance number from a runtime filename and add to existing set.

    Handles:
      - "{agent}.pid" -> instance 1 (bare name)
      - "{agent}-3.pid" -> instance 3
      - "{agent}-foo.pid" -> ignored (non-numeric suffix, different agent)
    """
    base = filename
    if base.endswith(suffix):
        base = base[: -len(suffix)]

    if base == agent:
        existing.add(1)
        return

    # Check for {agent}-{N} pattern
    prefix = agent + "-"
    if base.startswith(prefix):
        tail = base[len(prefix):]
        if tail.isdigit():
            existing.add(int(tail))


def is_instance_alive(agent: str, instance_id: str | None, runtime_dir: str) -> bool:
    """Check if a specific agent instance has an alive process.

    Checks both the poll PID file and the daemon state file for a running PID.
    Returns True if ANY of them has an alive process.
    """
    file_key = resolve_file_key(agent, instance_id)

    # Check poll PID file
    poll_pidfile = os.path.join(runtime_dir, ".work", ".minion-poll", f"{file_key}.pid")
    if _pid_alive_in_file(poll_pidfile):
        return True

    # Check daemon state file
    state_file = os.path.join(runtime_dir, ".minion-swarm", "state", f"{file_key}.json")
    if os.path.exists(state_file):
        try:
            with open(state_file) as f:
                state = json.loads(f.read())
            pid = state.get("pid")
            if pid and isinstance(pid, int):
                os.kill(pid, 0)  # signal 0 = check alive
                return True
        except (OSError, json.JSONDecodeError, ProcessLookupError, PermissionError, ValueError):
            pass

    return False


def _pid_alive_in_file(pidfile: str) -> bool:
    """Read a PID from a file and check if the process is alive."""
    if not os.path.exists(pidfile):
        return False
    try:
        with open(pidfile) as f:
            pid = int(f.read().strip())
        os.kill(pid, 0)  # signal 0 = check alive
        return True
    except (ValueError, ProcessLookupError, PermissionError, OSError):
        return False
