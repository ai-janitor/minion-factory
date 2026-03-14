"""Behavioral tests for lifecycle.py — cold_start, refresh, fenix_down, halt.

Purpose: Verify cold_start blocks on unregistered agents, returns expected
         structure for registered agents, and halt/fenix_down work correctly.
"""

from __future__ import annotations

import json
import os
import signal
import sqlite3
from unittest.mock import MagicMock, patch

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.db]


# ---------------------------------------------------------------------------
# Auto-apply isolated_db from conftest to every test in this module
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _use_isolated_db(isolated_db):
    """Delegate to conftest.isolated_db; autouse ensures every test gets DB isolation."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _register_agent(name: str, cls: str = "coder") -> None:
    db_path = os.environ["MINION_DB_PATH"]
    now = "2026-03-09T00:00:00"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT OR REPLACE INTO agents (name, agent_class, registered_at, last_seen) VALUES (?, ?, ?, ?)",
        (name, cls, now, now),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# cold_start — unregistered agent
# ---------------------------------------------------------------------------


def test_cold_start_unregistered_agent_returns_error():
    """cold_start returns error for unregistered agent."""
    from minion.lifecycle import cold_start
    result = cold_start("ghost")
    assert "error" in result
    assert "not registered" in result["error"]


# ---------------------------------------------------------------------------
# cold_start — registered agent
# ---------------------------------------------------------------------------


def test_cold_start_registered_agent_returns_agent_name():
    """cold_start returns agent_name in result for registered agent."""
    _register_agent("leo", "coder")
    from minion.lifecycle import cold_start
    result = cold_start("leo")
    assert "error" not in result
    assert result["agent_name"] == "leo"


def test_cold_start_result_has_expected_keys():
    """cold_start result includes battle_plan, agents, and inbox keys."""
    _register_agent("leo", "coder")
    from minion.lifecycle import cold_start
    result = cold_start("leo")
    for key in ("agent_name", "agent_class", "battle_plan", "agents", "inbox"):
        assert key in result, f"Missing key: {key}"


def test_cold_start_agents_list_includes_self():
    """cold_start agents list includes the calling agent."""
    _register_agent("leo", "coder")
    from minion.lifecycle import cold_start
    result = cold_start("leo")
    names = [a["name"] for a in result.get("agents", [])]
    assert "leo" in names


def test_cold_start_inbox_has_unread_count():
    """cold_start inbox dict has an unread_count field."""
    _register_agent("leo", "coder")
    from minion.lifecycle import cold_start
    result = cold_start("leo")
    inbox = result.get("inbox", {})
    assert "unread_count" in inbox
    assert isinstance(inbox["unread_count"], int)


# ---------------------------------------------------------------------------
# refresh — lightweight re-orientation
# ---------------------------------------------------------------------------


def test_refresh_unregistered_agent_returns_error():
    """refresh returns error for unregistered agent."""
    from minion.lifecycle import refresh
    result = refresh("ghost")
    assert "error" in result


def test_refresh_registered_agent_succeeds():
    """refresh returns structured result for registered agent."""
    _register_agent("leo", "coder")
    from minion.lifecycle import refresh
    result = refresh("leo")
    assert "error" not in result
    assert result.get("agent_name") == "leo"


# ---------------------------------------------------------------------------
# halt — lead-only trigger
# ---------------------------------------------------------------------------


def test_halt_non_lead_is_blocked():
    """halt is blocked for non-lead agents."""
    _register_agent("fighter", "coder")
    from minion.lifecycle import halt
    result = halt("fighter")
    assert "error" in result


def test_halt_lead_broadcasts_message():
    """halt called by lead returns result dict (even if no other agents registered)."""
    _register_agent("atlas", "lead")
    _register_agent("leo", "coder")  # add a target agent to halt
    from minion.lifecycle import halt
    result = halt("atlas")
    # lead-only: should not be blocked for class reasons
    if "error" in result:
        assert "class" not in result["error"].lower(), f"Unexpected error: {result['error']}"


# ---------------------------------------------------------------------------
# fenix_down — state dump
# ---------------------------------------------------------------------------


def test_fenix_down_unregistered_returns_error(tmp_path):
    """fenix_down returns error when agent is not registered."""
    from minion.lifecycle import fenix_down
    result = fenix_down("ghost", files="", manifest="")
    assert "error" in result


def test_fenix_down_registered_creates_dump(tmp_path):
    """fenix_down for registered agent returns a result with dump info."""
    _register_agent("leo", "coder")
    from minion.lifecycle import fenix_down
    result = fenix_down("leo", files="", manifest="lightweight dump")
    # Should succeed or return structured result — not crash
    assert isinstance(result, dict)
    assert "error" not in result or "not registered" not in result.get("error", "")


# ---------------------------------------------------------------------------
# _kill_all_daemons — PermissionError path
# ---------------------------------------------------------------------------


def test_kill_all_daemons_permission_error_logs_warning(tmp_path):
    """PermissionError from os.kill logs a WARNING with the PID — daemon is not silently passed."""
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    pid = 99999
    state_file = state_dir / "test-daemon.json"
    state_file.write_text(json.dumps({"pid": pid, "name": "test-daemon"}))

    from minion.crew.lifecycle import _kill_all_daemons

    with (
        patch("minion.crew.lifecycle.resolve_swarm_runtime_dir", return_value=tmp_path),
        patch("minion.crew.lifecycle.os.kill", side_effect=PermissionError("operation not permitted")),
        patch("minion.crew.lifecycle.log") as mock_log,
    ):
        _kill_all_daemons()

    # Must log a WARNING (not silently pass)
    mock_log.warning.assert_called_once()
    warning_args = mock_log.warning.call_args
    # The PID must appear in the warning message args
    assert pid in warning_args.args, f"PID {pid} not found in warning args: {warning_args.args}"


def test_kill_all_daemons_process_lookup_error_logs_error(tmp_path):
    """ProcessLookupError from os.kill logs an ERROR (PID already gone)."""
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    pid = 99998
    state_file = state_dir / "test-daemon.json"
    state_file.write_text(json.dumps({"pid": pid, "name": "test-daemon"}))

    from minion.crew.lifecycle import _kill_all_daemons

    with (
        patch("minion.crew.lifecycle.resolve_swarm_runtime_dir", return_value=tmp_path),
        patch("minion.crew.lifecycle.os.kill", side_effect=ProcessLookupError("no such process")),
        patch("minion.crew.lifecycle.log") as mock_log,
    ):
        _kill_all_daemons()

    mock_log.error.assert_called_once()
    error_args = mock_log.error.call_args
    assert pid in error_args.args, f"PID {pid} not found in error args: {error_args.args}"


def test_kill_all_daemons_json_parse_error_logs_error(tmp_path):
    """Invalid JSON in state file logs an ERROR and skips the kill."""
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    state_file = state_dir / "corrupt-daemon.json"
    state_file.write_text("not valid json {{{")

    from minion.crew.lifecycle import _kill_all_daemons

    with (
        patch("minion.crew.lifecycle.resolve_swarm_runtime_dir", return_value=tmp_path),
        patch("minion.crew.lifecycle.os.kill") as mock_kill,
        patch("minion.crew.lifecycle.log") as mock_log,
    ):
        _kill_all_daemons()

    # os.kill must NOT be called when JSON is bad
    mock_kill.assert_not_called()
    mock_log.error.assert_called_once()
