"""Tests for formal state machines — daemon and agent status transitions.

Purpose: Verify backlog #83 — explicit state machines reject invalid transitions.
Responsibility: Test DAEMON_TRANSITIONS, AGENT_STATUS_TRANSITIONS, validate_transition().
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit

from minion.state_machines import (
    AGENT_STATUS_TRANSITIONS,
    DAEMON_TRANSITIONS,
    InvalidTransition,
    transition,
    validate_transition,
)


# ── Daemon State Machine ─────────────────────────────────────────────


class TestDaemonTransitions:
    def test_idle_to_working(self):
        assert validate_transition(DAEMON_TRANSITIONS, "daemon", "idle", "working")

    def test_working_to_idle(self):
        assert validate_transition(DAEMON_TRANSITIONS, "daemon", "working", "idle")

    def test_working_to_error(self):
        assert validate_transition(DAEMON_TRANSITIONS, "daemon", "working", "error")

    def test_working_to_phoenix_down(self):
        assert validate_transition(DAEMON_TRANSITIONS, "daemon", "working", "phoenix_down")

    def test_error_to_idle(self):
        assert validate_transition(DAEMON_TRANSITIONS, "daemon", "error", "idle")

    def test_stopped_is_terminal(self):
        with pytest.raises(InvalidTransition):
            validate_transition(DAEMON_TRANSITIONS, "daemon", "stopped", "idle")

    def test_invalid_idle_to_phoenix_down(self):
        """Cannot go directly from idle to phoenix_down — must be working first."""
        with pytest.raises(InvalidTransition):
            validate_transition(DAEMON_TRANSITIONS, "daemon", "idle", "phoenix_down")

    def test_phoenix_down_to_idle(self):
        """Auto-respawn: phoenix_down -> idle."""
        assert validate_transition(DAEMON_TRANSITIONS, "daemon", "phoenix_down", "idle")

    def test_unknown_source_state_allowed(self):
        """Unknown source state is allowed (backward compat)."""
        assert validate_transition(DAEMON_TRANSITIONS, "daemon", "unknown_state", "idle")


# ── Agent Status State Machine ────────────────────────────────────────


class TestAgentStatusTransitions:
    def test_waiting_to_working(self):
        assert validate_transition(AGENT_STATUS_TRANSITIONS, "agent", "waiting for work", "working")

    def test_working_to_stood_down(self):
        assert validate_transition(AGENT_STATUS_TRANSITIONS, "agent", "working", "stood_down")

    def test_stood_down_to_working(self):
        assert validate_transition(AGENT_STATUS_TRANSITIONS, "agent", "stood_down", "working")

    def test_invalid_waiting_to_error(self):
        """Cannot go from waiting directly to error."""
        with pytest.raises(InvalidTransition):
            validate_transition(AGENT_STATUS_TRANSITIONS, "agent", "waiting for work", "error")

    def test_retired_can_reregister(self):
        assert validate_transition(AGENT_STATUS_TRANSITIONS, "agent", "retired", "waiting for work")

    def test_working_to_phoenix_down(self):
        """Agent can go from working to phoenix_down (terminal agent context death)."""
        assert validate_transition(AGENT_STATUS_TRANSITIONS, "agent", "working", "phoenix_down")

    def test_phoenix_down_to_waiting(self):
        """Agent can re-register from phoenix_down back to waiting for work."""
        assert validate_transition(AGENT_STATUS_TRANSITIONS, "agent", "phoenix_down", "waiting for work")

    def test_phoenix_down_to_deregistered(self):
        """Agent can be deregistered from phoenix_down."""
        assert validate_transition(AGENT_STATUS_TRANSITIONS, "agent", "phoenix_down", "deregistered")

    def test_invalid_waiting_to_phoenix_down(self):
        """Cannot go from waiting directly to phoenix_down — must be working first."""
        with pytest.raises(InvalidTransition):
            validate_transition(AGENT_STATUS_TRANSITIONS, "agent", "waiting for work", "phoenix_down")

    def test_busy_is_not_valid_state(self):
        """'busy' is not a valid agent status — use 'working' instead."""
        # 'busy' was an old ad-hoc status in create_task.py, replaced by 'working'
        assert "busy" not in AGENT_STATUS_TRANSITIONS

    def test_all_states_have_transitions(self):
        """Every state defined in the machine has at least an entry (even if empty set)."""
        # Collect all states referenced as targets
        all_targets = set()
        for targets in AGENT_STATUS_TRANSITIONS.values():
            all_targets.update(targets)
        # Every target should be a defined state (except deregistered which is terminal-ish)
        for target in all_targets:
            assert target in AGENT_STATUS_TRANSITIONS, f"Target state '{target}' has no transition entry"


# ── Transition helper ────────────────────────────────────────────────


class TestTransitionHelper:
    def test_returns_to_state(self):
        result = transition(DAEMON_TRANSITIONS, "daemon", "idle", "working")
        assert result == "working"

    def test_raises_on_invalid(self):
        with pytest.raises(InvalidTransition):
            transition(DAEMON_TRANSITIONS, "daemon", "stopped", "working")


# ── InvalidTransition exception ───────────────────────────────────────


class TestInvalidTransitionException:
    def test_message_includes_valid_targets(self):
        exc = InvalidTransition("daemon", "idle", "phoenix_down", {"working", "stopped"})
        assert "phoenix_down" in str(exc)
        assert "daemon" in str(exc)
        assert "idle" in str(exc)

    def test_attributes(self):
        exc = InvalidTransition("test", "a", "b", {"c", "d"})
        assert exc.machine_name == "test"
        assert exc.from_state == "a"
        assert exc.to_state == "b"
        assert exc.valid_targets == {"c", "d"}
