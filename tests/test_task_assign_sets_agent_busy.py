"""Tests for assign_task setting the assigned agent's status to 'busy'.

Purpose: Verify that when a lead assigns a task via assign_task(), the assigned
         agent's status column is updated to 'busy' in the agents table.
Rationale: Backlog #102 — the dashboard should reflect that an agent is busy
           immediately after task assignment. This was implemented in commit
           a5e973c but lacked test coverage.
Responsibility: Only tests the agent-status side effect of assign_task.
                Task status transitions are tested elsewhere.
Organization: Uses isolated_db fixture from conftest; local helpers for setup.
"""

from __future__ import annotations

import sqlite3

import pytest

from minion.db import now_iso
from minion.tasks.create_task import assign_task

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Local helpers — insert rows directly via sqlite3
# ---------------------------------------------------------------------------


def _insert_agent(db_path: str, name: str, agent_class: str) -> None:
    """Insert a minimal agent row."""
    now = now_iso()
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT OR REPLACE INTO agents (name, agent_class, registered_at, last_seen) "
        "VALUES (?, ?, ?, ?)",
        (name, agent_class, now, now),
    )
    conn.commit()
    conn.close()


def _insert_open_task(db_path: str, title: str, flow_type: str = "bugfix") -> int:
    """Insert an open task and return its ID."""
    now = now_iso()
    conn = sqlite3.connect(db_path)
    cur = conn.execute(
        "INSERT INTO tasks (title, task_file, created_by, status, created_at, updated_at, flow_type) "
        "VALUES (?, ?, 'atlas', 'open', ?, ?, ?)",
        (title, f".work/tasks/{title.lower().replace(' ', '-')}.md", now, now, flow_type),
    )
    task_id = cur.lastrowid
    conn.commit()
    conn.close()
    return task_id


# ---------------------------------------------------------------------------
# Core: assign_task sets agent status to busy
# ---------------------------------------------------------------------------


def test_assign_task_sets_agent_status_to_busy(isolated_db):
    """After assign_task(), the assigned agent's status should be 'busy'."""
    db_path = str(isolated_db / ".work" / "minion.db")

    # Register a lead and a coder
    _insert_agent(db_path, "atlas", "lead")
    _insert_agent(db_path, "coder-1", "coder")

    # Create an open task
    task_id = _insert_open_task(db_path, "Fix the widget", "bugfix")

    # Verify agent is NOT busy before assignment
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT status FROM agents WHERE name = 'coder-1'").fetchone()
    conn.close()
    assert row is None or row[0] != "busy", "Agent should not be busy before assignment"

    # Assign the task
    result = assign_task("atlas", task_id, "coder-1")
    assert "error" not in result, f"assign_task failed: {result}"

    # Verify agent status is now 'busy'
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT status FROM agents WHERE name = 'coder-1'").fetchone()
    conn.close()
    assert row is not None, "Agent row should exist"
    assert row[0] == "busy", f"Expected agent status 'busy', got '{row[0]}'"


def test_assign_task_at_review_stage_also_sets_busy(isolated_db):
    """Even when reassigning at a review stage, the agent should be set to busy."""
    db_path = str(isolated_db / ".work" / "minion.db")

    _insert_agent(db_path, "atlas", "lead")
    _insert_agent(db_path, "reviewer-1", "coder")

    # Create a task and move it to a review stage manually
    task_id = _insert_open_task(db_path, "Review task", "bugfix")
    conn = sqlite3.connect(db_path)
    conn.execute(
        "UPDATE tasks SET status = 'in_review', assigned_to = 'atlas' WHERE id = ?",
        (task_id,),
    )
    conn.commit()
    conn.close()

    # Assign to reviewer
    result = assign_task("atlas", task_id, "reviewer-1")
    assert "error" not in result, f"assign_task failed: {result}"

    # Verify reviewer is busy
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT status FROM agents WHERE name = 'reviewer-1'").fetchone()
    conn.close()
    assert row is not None, "Agent row should exist"
    assert row[0] == "busy", f"Expected agent status 'busy', got '{row[0]}'"
