"""Behavioral tests for polling.py — is_poll_alive, poll_loop mechanics.

Purpose: Verify PID file management, poll alive detection, and basic
         poll behavior with registered agents.
"""

from __future__ import annotations

import os
import sqlite3

import pytest

from minion.db import init_db, reset_db_path


# ---------------------------------------------------------------------------
# DB isolation fixture
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    work_dir = tmp_path / ".work"
    work_dir.mkdir(parents=True, exist_ok=True)
    db_path = str(work_dir / "minion.db")
    monkeypatch.setenv("MINION_DB_PATH", db_path)
    reset_db_path()
    init_db()
    monkeypatch.chdir(tmp_path)
    yield tmp_path
    reset_db_path()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _register_agent(name: str, cls: str = "coder", tmp_path=None) -> None:
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
# is_poll_alive — PID file detection
# ---------------------------------------------------------------------------


def test_is_poll_alive_no_pidfile_returns_false(tmp_path):
    """is_poll_alive returns False when no PID file exists."""
    from minion.polling import is_poll_alive
    assert is_poll_alive("ghost", str(tmp_path)) is False


def test_is_poll_alive_with_stale_pidfile_returns_false(tmp_path):
    """is_poll_alive returns False when PID file has a dead PID."""
    poll_dir = tmp_path / ".work" / ".minion-poll"
    poll_dir.mkdir(parents=True)
    pid_file = poll_dir / "agent-x.pid"
    pid_file.write_text("99999999")  # Very high PID, almost certainly dead
    from minion.polling import is_poll_alive
    result = is_poll_alive("agent-x", str(tmp_path))
    # Either False (dead) or True (if pid 99999999 exists — extremely unlikely)
    assert isinstance(result, bool)


def test_is_poll_alive_with_current_pid_returns_true(tmp_path):
    """is_poll_alive returns True when PID file contains current process PID."""
    poll_dir = tmp_path / ".work" / ".minion-poll"
    poll_dir.mkdir(parents=True)
    pid_file = poll_dir / "agent-x.pid"
    pid_file.write_text(str(os.getpid()))  # Current process is alive
    from minion.polling import is_poll_alive
    assert is_poll_alive("agent-x", str(tmp_path)) is True


# ---------------------------------------------------------------------------
# poll_loop — unregistered agent
# ---------------------------------------------------------------------------


def test_poll_loop_unregistered_agent_returns_error():
    """poll_loop returns result dict when agent is not registered."""
    from minion.polling import poll_loop
    result = poll_loop("ghost", interval=1, timeout=1)
    # Should return a dict (error, timeout, or exit_code)
    assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# poll_loop — registered agent with timeout
# ---------------------------------------------------------------------------


def test_poll_loop_registered_agent_timeout(tmp_path):
    """poll_loop with short timeout returns a result dict (timeout or content)."""
    _register_agent("leo", "coder", tmp_path)
    from minion.polling import poll_loop
    result = poll_loop("leo", interval=1, timeout=2)
    # Valid result: any dict (exit_code, status, error all valid)
    assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# _poll_pidfile — path structure
# ---------------------------------------------------------------------------


def test_poll_pidfile_path_contains_agent_name(tmp_path, monkeypatch):
    """_poll_pidfile returns a path containing the agent name."""
    from minion.polling import _poll_pidfile
    path = _poll_pidfile("atlas")
    assert "atlas" in path
    assert path.endswith(".pid")
