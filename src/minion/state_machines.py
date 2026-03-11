"""Formal state machines — valid transitions for daemon and agent statuses.

Purpose: Provide explicit state transition validation for daemon states and agent
lifecycle statuses. Reject invalid transitions with clear error messages.
Rationale: Backlog #83 — daemon and agent lifecycle transitions aren't formally
validated, allowing arbitrary status jumps.
Responsibility: Define valid transition dicts, provide validate_transition() and
transition() functions for both daemon and agent state machines.
Organization: Used by daemon/runner/_state.py (daemon states) and
db/agents.py + comms/register.py (agent statuses).

ASSUMPTIONS:
- Unknown source states are ALLOWED with a pass-through (validate_transition returns
  True). This is for backward compatibility — if a DB has a status value from a newer
  code version, older code won't crash. This means typos in from_state silently pass
  validation instead of raising errors.
- DAEMON_TRANSITIONS and AGENT_STATUS_TRANSITIONS are the ONLY two state machines.
  Both are static dicts defined at module level. If daemon or agent statuses need to
  be configurable (e.g., per-flow or per-provider), this module must be refactored.
- "stopped" is terminal for daemons (empty transition set). Once a daemon reaches
  "stopped", the only way back is to spawn a new process. The state machine does not
  model process restart — that's handled by crew/lifecycle.py.
- "deregistered" can transition to "waiting for work" to support re-registration.
  This means deregistration is not permanent — the same agent name can be reused.

Pseudo-logic:
  State machine = dict[str, set[str]] mapping current_state -> valid_next_states.
  validate_transition(machine, from_state, to_state):
    1. Look up from_state in machine
    2. If from_state unknown, raise InvalidTransition
    3. If to_state not in valid_next_states, raise InvalidTransition
    4. Return True
  transition(machine, from_state, to_state):
    1. Call validate_transition
    2. Return to_state (for assignment convenience)
"""

from __future__ import annotations


class InvalidTransition(Exception):
    """Raised when a state transition is not allowed by the state machine."""

    def __init__(self, machine_name: str, from_state: str, to_state: str, valid_targets: set[str]) -> None:
        self.machine_name = machine_name
        self.from_state = from_state
        self.to_state = to_state
        self.valid_targets = valid_targets
        super().__init__(
            f"Invalid {machine_name} transition: '{from_state}' -> '{to_state}'. "
            f"Valid targets from '{from_state}': {sorted(valid_targets)}"
        )


# ---------------------------------------------------------------------------
# Daemon state machine
# ---------------------------------------------------------------------------
# States: idle, working, error, stopped, phoenix_down, halted, stood_down
# These are the status values written by _write_state() in daemon/runner/_state.py.

DAEMON_TRANSITIONS: dict[str, set[str]] = {
    "idle":         {"working", "stopped", "halted", "stood_down", "error"},
    "working":      {"idle", "error", "stopped", "phoenix_down", "halted"},
    "error":        {"idle", "working", "stopped"},
    "stopped":      set(),  # Terminal — daemon process exited
    "phoenix_down": {"idle", "stopped"},  # Auto-respawn resets to idle
    "halted":       {"stopped"},  # Halt acknowledged — only exit
    "stood_down":   {"idle", "working", "stopped"},  # Wake from standdown
}

# ---------------------------------------------------------------------------
# Agent status state machine
# ---------------------------------------------------------------------------
# These are the status values stored in the agents.status DB column.
# Managed by comms/register.py set_status() and daemon state writes.

AGENT_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "waiting for work":  {"working", "stood_down", "retired", "deregistered"},
    "working":           {"waiting for work", "stood_down", "retired", "deregistered", "error", "phoenix_down"},
    "stood_down":        {"waiting for work", "working", "retired", "deregistered"},
    "error":             {"waiting for work", "working", "retired", "deregistered"},
    "phoenix_down":      {"waiting for work", "deregistered"},  # Terminal agent saved state, can re-register
    "retired":           {"deregistered", "waiting for work"},  # Can re-register
    "deregistered":      {"waiting for work"},  # Can re-register from scratch
}


def validate_transition(
    machine: dict[str, set[str]],
    machine_name: str,
    from_state: str,
    to_state: str,
) -> bool:
    """Validate that from_state -> to_state is allowed. Raises InvalidTransition if not.

    Precondition: machine must be a dict mapping states to sets of valid targets.
    Postcondition: Returns True only if transition is valid.

    Time complexity: O(1) — dict lookup + set membership check.
    """
    assert isinstance(machine, dict), f"machine must be a dict, got {type(machine)}"
    assert from_state, "from_state must not be empty"
    assert to_state, "to_state must not be empty"

    valid_targets = machine.get(from_state)
    if valid_targets is None:
        # Unknown source state — allow with warning (for backward compat)
        return True
    if to_state not in valid_targets:
        raise InvalidTransition(machine_name, from_state, to_state, valid_targets)
    return True


def transition(
    machine: dict[str, set[str]],
    machine_name: str,
    from_state: str,
    to_state: str,
) -> str:
    """Validate and return to_state. Convenience wrapper for assignment patterns.

    Usage: self.status = transition(DAEMON_TRANSITIONS, "daemon", old, new)
    """
    validate_transition(machine, machine_name, from_state, to_state)
    return to_state
