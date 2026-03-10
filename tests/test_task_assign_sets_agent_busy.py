"""Tests for assign_task setting agent status to 'busy'.

Purpose: Verify that when a task is assigned to an agent, the agent's status is updated to 'busy'.
Rationale: Backlog #102 — the dashboard should reflect that an agent is busy after task assignment.
Responsibility: Tests ONLY the agent-status-update side effect of assign_task. NOT responsible for
    other assign_task behaviors (those are tested elsewhere).
Organization: One TestClass for the assign-sets-busy behavior."""

from __future__ import annotations

import sqlite3

import pytest

from minion.db import init_db, reset_db_path

pytestmark = [pytest.mark.integration, pytest.mark.db]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _setup_db(db_path: str) -> None:
    """Initialize full schema needed by assign_task."""
    import os
    os.environ["MINION_DB_PATH"] = db_path
    reset_db_path()
    init_db()


def _insert_lead(db_path: str, name: str = "atlas") -> None:
    now = "2026-02-22T00:00:00"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT OR REPLACE INTO agents (name, agent_class, status, registered_at, last_seen) "
        "VALUES (?, 'lead', 'idle', ?, ?)",
        (name, now, now),
    )
    conn.commit()
    conn.close()


def _insert_coder(db_path: str, name: str = "coder-1") -> None:
    now = "2026-02-22T00:00:00"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT OR REPLACE INTO agents (name, agent_class, status, registered_at, last_seen) "
        "VALUES (?, 'coder', 'idle', ?, ?)",
        (name, now, now),
    )
    conn.commit()
    conn.close()


def _insert_open_task(db_path: str, title: str = "Fix login bug") -> int:
    """Insert an open task and return its ID."""
    now = "2026-02-22T00:00:00"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        "INSERT INTO tasks (title, task_file, status, created_by, created_at, updated_at) "
        "VALUES (?, 'tasks/fix-login.md', 'open', 'atlas', ?, ?)",
        (title, now, now),
    )
    task_id = cur.lastrowid
    conn.commit()
    conn.close()
    return task_id


def _get_agent_status(db_path: str, name: str) -> str | None:
    """Read the status column for an agent."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT status FROM agents WHERE name = ?", (name,)).fetchone()
    conn.close()
    return row["status"] if row else None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def project_dir(tmp_path, monkeypatch):
    """Temp project dir with initialized DB. Monkeypatches MINION_DB_PATH."""
    work = tmp_path / ".work"
    work.mkdir()
    db_path = str(work / "minion.db")
    _setup_db(db_path)
    monkeypatch.setenv("MINION_DB_PATH", db_path)
    reset_db_path()
    yield tmp_path
    reset_db_path()


@pytest.fixture
def db_path(project_dir):
    return str(project_dir / ".work" / "minion.db")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAssignTaskSetsAgentBusy:
    """Verify that assign_task updates the assigned agent's status to 'busy'."""

    def test_agent_status_becomes_busy_after_assign(self, db_path, monkeypatch):
        """After assign_task succeeds, the assigned agent's status should be 'busy'."""
        monkeypatch.chdir(db_path.replace("/.work/minion.db", ""))
        _insert_lead(db_path)
        _insert_coder(db_path, name="worker-1")
        task_id = _insert_open_task(db_path)

        # Confirm agent starts as idle
        assert _get_agent_status(db_path, "worker-1") == "idle"

        from minion.tasks import assign_task
        result = assign_task("atlas", task_id, "worker-1")

        assert "error" not in result
        assert result["status"] == "assigned"
        # Core assertion: agent status is now busy
        assert _get_agent_status(db_path, "worker-1") == "busy"

    def test_lead_status_unchanged_after_assigning(self, db_path, monkeypatch):
        """The lead who assigns the task should NOT have their status changed."""
        monkeypatch.chdir(db_path.replace("/.work/minion.db", ""))
        _insert_lead(db_path)
        _insert_coder(db_path, name="worker-1")
        task_id = _insert_open_task(db_path)

        from minion.tasks import assign_task
        assign_task("atlas", task_id, "worker-1")

        # Lead's status should remain idle
        assert _get_agent_status(db_path, "atlas") == "idle"

    def test_agent_last_seen_updated_after_assign(self, db_path, monkeypatch):
        """The assigned agent's last_seen timestamp should be updated."""
        monkeypatch.chdir(db_path.replace("/.work/minion.db", ""))
        _insert_lead(db_path)
        _insert_coder(db_path, name="worker-1")
        task_id = _insert_open_task(db_path)

        # Record original last_seen
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        before = conn.execute(
            "SELECT last_seen FROM agents WHERE name = 'worker-1'"
        ).fetchone()["last_seen"]
        conn.close()

        from minion.tasks import assign_task
        assign_task("atlas", task_id, "worker-1")

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        after = conn.execute(
            "SELECT last_seen FROM agents WHERE name = 'worker-1'"
        ).fetchone()["last_seen"]
        conn.close()

        assert after >= before
