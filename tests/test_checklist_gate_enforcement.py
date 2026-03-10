"""Tests for mechanical checklist enforcement — Task #93.

Purpose: Verify the checklist gate on task update in_progress transitions.
Rationale: Agents skip writing CHECKLIST.md despite prompt instructions. This gate
           mechanically prevents transitioning to in_progress without registering a
           checklist file that exists on disk.
Responsibility: Test the 4 acceptance criteria for checklist enforcement. NOT
                responsible for testing other task update behaviors.
Organization: One test per acceptance criterion, plus edge case coverage.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest

from minion.db import init_db, reset_db_path, get_db

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers — minimal setup for task update tests
# ---------------------------------------------------------------------------


def _setup(tmp_path):
    """Create an isolated DB with a lead and a coder, plus an assigned task."""
    work_dir = tmp_path / ".work"
    work_dir.mkdir(parents=True, exist_ok=True)
    db_path = str(work_dir / "minion.db")
    os.environ["MINION_DB_PATH"] = db_path
    reset_db_path()
    init_db()

    now = "2026-03-10T00:00:00"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    # Register agents
    conn.execute(
        "INSERT INTO agents (name, agent_class, registered_at, last_seen) VALUES (?, 'lead', ?, ?)",
        ("atlas", now, now),
    )
    conn.execute(
        "INSERT INTO agents (name, agent_class, registered_at, last_seen) VALUES (?, 'coder', ?, ?)",
        ("coder-1", now, now),
    )
    # Create an assigned task (status=assigned so in_progress is a valid next step)
    conn.execute(
        """INSERT INTO tasks (title, task_file, status, assigned_to, created_by, flow_type, created_at, updated_at)
           VALUES (?, ?, 'assigned', ?, ?, 'feature', ?, ?)""",
        ("Test task", ".work/tasks/test.md", "coder-1", "atlas", now, now),
    )
    conn.commit()
    task_id = conn.execute("SELECT id FROM tasks ORDER BY id DESC LIMIT 1").fetchone()[0]
    conn.close()
    return db_path, task_id


# ---------------------------------------------------------------------------
# AC-1: in_progress WITHOUT --checklist → rejected with clear error
# ---------------------------------------------------------------------------


def test_in_progress_without_checklist_rejected(tmp_path, monkeypatch):
    """Transitioning to in_progress without --checklist must be blocked."""
    monkeypatch.chdir(tmp_path)
    db_path, task_id = _setup(tmp_path)

    from minion.tasks import update_task
    result = update_task("coder-1", task_id, status="in_progress")

    assert "error" in result
    assert "checklist" in result["error"].lower()
    assert "BLOCKED" in result["error"]


# ---------------------------------------------------------------------------
# AC-2: in_progress WITH --checklist pointing to existing file → succeeds
# ---------------------------------------------------------------------------


def test_in_progress_with_valid_checklist_succeeds(tmp_path, monkeypatch):
    """Transitioning to in_progress with a valid checklist file must succeed."""
    monkeypatch.chdir(tmp_path)
    db_path, task_id = _setup(tmp_path)

    # Create the checklist file
    checklist_path = tmp_path / "CHECKLIST.md"
    checklist_path.write_text("# Worker Checklist\n- [ ] Item 1\n")

    from minion.tasks import update_task
    result = update_task("coder-1", task_id, status="in_progress", checklist=str(checklist_path))

    assert "error" not in result
    assert result.get("new_status") == "in_progress"

    # Verify checklist_path stored in DB
    conn = get_db()
    row = conn.execute("SELECT checklist_path FROM tasks WHERE id = ?", (task_id,)).fetchone()
    conn.close()
    assert row["checklist_path"] == str(checklist_path)


# ---------------------------------------------------------------------------
# AC-3: in_progress WITH --checklist pointing to nonexistent file → rejected
# ---------------------------------------------------------------------------


def test_in_progress_with_nonexistent_checklist_rejected(tmp_path, monkeypatch):
    """Transitioning to in_progress with a missing checklist file must be blocked."""
    monkeypatch.chdir(tmp_path)
    db_path, task_id = _setup(tmp_path)

    from minion.tasks import update_task
    result = update_task("coder-1", task_id, status="in_progress", checklist="/nonexistent/path/CHECKLIST.md")

    assert "error" in result
    assert "not found" in result["error"].lower()
    assert "BLOCKED" in result["error"]


# ---------------------------------------------------------------------------
# AC-4: Non-gated transitions still work without --checklist
# ---------------------------------------------------------------------------


def test_non_gated_transition_works_without_checklist(tmp_path, monkeypatch):
    """Transitions to statuses other than in_progress must not require --checklist."""
    monkeypatch.chdir(tmp_path)
    db_path, task_id = _setup(tmp_path)

    # Update progress without changing status — no gate
    from minion.tasks import update_task
    result = update_task("coder-1", task_id, progress="working on it")

    assert "error" not in result
    assert result.get("status") == "updated"


# ---------------------------------------------------------------------------
# Edge case: relative checklist path resolved against MINION_PROJECT_DIR
# ---------------------------------------------------------------------------


def test_relative_checklist_path_resolved(tmp_path, monkeypatch):
    """A relative checklist path should be resolved against MINION_PROJECT_DIR."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MINION_PROJECT_DIR", str(tmp_path))
    db_path, task_id = _setup(tmp_path)

    # Create the checklist file at a relative path
    checklist_file = tmp_path / "CHECKLIST.md"
    checklist_file.write_text("# Checklist\n")

    from minion.tasks import update_task
    result = update_task("coder-1", task_id, status="in_progress", checklist="CHECKLIST.md")

    assert "error" not in result
    assert result.get("new_status") == "in_progress"


# ---------------------------------------------------------------------------
# Edge case: checklist stored in DB even for absolute paths
# ---------------------------------------------------------------------------


def test_checklist_path_stored_as_provided(tmp_path, monkeypatch):
    """The checklist path stored in DB should be the value the user provided (not resolved)."""
    monkeypatch.chdir(tmp_path)
    db_path, task_id = _setup(tmp_path)

    checklist_file = tmp_path / "CHECKLIST.md"
    checklist_file.write_text("# Checklist\n")

    from minion.tasks import update_task
    result = update_task("coder-1", task_id, status="in_progress", checklist=str(checklist_file))

    assert "error" not in result

    conn = get_db()
    row = conn.execute("SELECT checklist_path FROM tasks WHERE id = ?", (task_id,)).fetchone()
    conn.close()
    # Stored as-provided (the absolute path the user gave)
    assert row["checklist_path"] == str(checklist_file)
