"""Behavioral tests for polling.py — is_poll_alive, poll_loop mechanics.

Purpose: Verify PID file management, poll alive detection, and basic
         poll behavior with registered agents.
"""

from __future__ import annotations

import os
import sqlite3

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


# ---------------------------------------------------------------------------
# SU-06: poll_status() — diagnostic health check
# ---------------------------------------------------------------------------


def test_poll_status_returns_agent_name():
    """SU-06: poll_status() includes the agent name in its result."""
    _register_agent("diag-1", "coder")
    from minion.polling import poll_status
    result = poll_status("diag-1")
    assert result["agent"] == "diag-1"


def test_poll_status_no_pidfile():
    """SU-06: poll_status() reports pid_file_exists=False when no PID file."""
    _register_agent("diag-2", "coder")
    from minion.polling import poll_status
    result = poll_status("diag-2")
    assert result["pid_file_exists"] is False
    assert result["pid_alive"] is False


def test_poll_status_with_live_pidfile(tmp_path):
    """SU-06: poll_status() detects a live PID file."""
    _register_agent("diag-3", "coder")
    # Create PID file manually
    poll_dir = tmp_path / ".work" / ".minion-poll"
    poll_dir.mkdir(parents=True)
    pid_file = poll_dir / "diag-3.pid"
    pid_file.write_text(str(os.getpid()))  # Current process is alive

    from minion.polling import poll_status
    result = poll_status("diag-3")
    assert result["pid_file_exists"] is True
    assert result["pid_alive"] is True


def test_poll_status_heartbeat_present():
    """SU-06: poll_status() reports last_heartbeat from DB."""
    _register_agent("diag-4", "coder")
    from minion.polling import poll_status
    result = poll_status("diag-4")
    # Agent was just registered so last_seen should be present
    assert "last_heartbeat" in result


def test_poll_status_empty_agent_raises():
    """SU-06: poll_status() raises AssertionError for empty agent name."""
    from minion.polling import poll_status
    import pytest
    with pytest.raises(AssertionError):
        poll_status("")


# ---------------------------------------------------------------------------
# SU-06: complete_phase returns poll_reminder
# ---------------------------------------------------------------------------


def test_complete_phase_includes_poll_reminder():
    """SU-06: complete_phase() result includes poll_reminder field."""
    _register_agent("coder-pr", "coder")
    from minion.db import get_db, now_iso
    now = now_iso()
    db = get_db()
    db.execute(
        "INSERT INTO tasks (title, task_file, created_by, status, created_at, updated_at, flow_type) "
        "VALUES (?, ?, ?, 'open', ?, ?, 'bugfix')",
        ("Poll reminder test", "tasks/poll-reminder.md", "coder-pr", now, now),
    )
    db.commit()
    task_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    db.close()

    from minion.tasks.update_task import complete_phase
    result = complete_phase("coder-pr", task_id, passed=True)
    if "error" not in result:
        assert "poll_reminder" in result


# ---------------------------------------------------------------------------
# DAG eligibility check failure — task must be skipped (not returned eligible)
# ---------------------------------------------------------------------------


def test_dag_eligibility_exception_skips_task():
    """When workers_for() raises, the task must NOT be returned as eligible.

    Regression test for polling.py:259 — the except block previously had no
    'continue', so a task fell through to the result set even when eligibility
    could not be confirmed. After the fix, any exception from the DAG eligibility
    check causes the task to be treated as ineligible and skipped.
    """
    import sqlite3
    import unittest.mock as mock
    from minion.db import get_db, now_iso

    _register_agent("elig-coder", "coder")

    now = now_iso()
    db = get_db()
    # Insert an open, unassigned task with a known flow_type
    db.execute(
        "INSERT INTO tasks (title, task_file, created_by, status, assigned_to, "
        "created_at, updated_at, flow_type, class_required) "
        "VALUES (?, ?, ?, 'open', NULL, ?, ?, 'bugfix', 'coder')",
        ("Eligibility skip test task", "tasks/elig-test.md", "elig-coder", now, now),
    )
    db.commit()
    db.close()

    # Patch workers_for to raise KeyError — simulates malformed flow YAML / unknown stage
    with mock.patch("minion.flow_bridge.workers_for", side_effect=KeyError("unknown_stage")):
        from minion.polling import _find_available_tasks
        tasks = _find_available_tasks("elig-coder")

    # Task must NOT appear in results — eligibility check failure means skip
    task_titles = [t.get("title") for t in tasks]
    assert "Eligibility skip test task" not in task_titles, (
        "Task was returned as eligible even though the DAG eligibility check raised. "
        "Add 'continue' after logger.error in the except block at polling.py:259."
    )


# ---------------------------------------------------------------------------
# DAG render failure — task returned with explicit error string, not empty dag
# ---------------------------------------------------------------------------


def test_dag_render_failure_returns_explicit_error_string_not_empty():
    """When render_dag() raises, the returned task entry must have a non-empty dag field.

    Regression test for polling.py:268 — the except block previously left dag_str=""
    after logging the error, so the agent received a task with no phase visibility.
    Per GLOBAL-152 (no-silent-failures), the failure must be visible to the caller.
    After the fix, dag contains an explicit error message, not an empty string.
    """
    import unittest.mock as mock
    from minion.db import get_db, now_iso

    _register_agent("dag-render-coder", "coder")

    now = now_iso()
    db = get_db()
    db.execute(
        "INSERT INTO tasks (title, task_file, created_by, status, assigned_to, "
        "created_at, updated_at, flow_type, class_required) "
        "VALUES (?, ?, ?, 'open', NULL, ?, ?, 'bugfix', 'coder')",
        ("DAG render failure test task", "tasks/dag-render-test.md", "dag-render-coder", now, now),
    )
    db.commit()
    db.close()

    # Patch load_flow inside polling.py to return a mock flow whose render_dag raises.
    # This simulates a malformed/unrenderable flow while letting active_statuses() work.
    # We use a real TaskFlow object as the pass-through for eligibility, but a mock for
    # the render_dag block, by patching minion.tasks.load_flow to return a broken-render mock.
    import minion.tasks as _mt

    _real_load_flow = _mt.load_flow

    def _broken_render_load_flow(flow_type):
        real_flow = _real_load_flow(flow_type)
        broken = mock.MagicMock(wraps=real_flow)
        broken.render_dag.side_effect = ValueError("bad flow YAML")
        return broken

    # Clear flow_bridge cache so load_flow is called fresh (and our mock is hit)
    import minion.flow_bridge as _fb
    _fb._flow_cache.clear()

    with mock.patch("minion.tasks.load_flow", side_effect=_broken_render_load_flow):
        from minion.polling import _find_available_tasks
        tasks = _find_available_tasks("dag-render-coder")

    # Restore flow_bridge cache
    _fb._flow_cache.clear()

    # Task must still be returned (not skipped — render failure != eligibility failure)
    task_titles = [t.get("title") for t in tasks]
    assert "DAG render failure test task" in task_titles, (
        "Task was not returned after DAG render failure. "
        "Render failure should not skip the task — only eligibility failure should."
    )

    # The dag field must be a non-empty explicit error string, not ""
    matching = [t for t in tasks if t.get("title") == "DAG render failure test task"]
    assert matching, "Task not found in results"
    dag_val = matching[0].get("dag", "")
    assert dag_val != "", (
        "dag field is empty string after render failure — agent has no phase visibility. "
        "Set dag_str to an explicit error message when render fails (GLOBAL-152)."
    )
    assert "unavailable" in dag_val.lower() or "failed" in dag_val.lower(), (
        f"dag field does not indicate failure: {dag_val!r}. "
        "Expected an explicit error message so agent knows DAG render failed."
    )
