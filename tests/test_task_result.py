"""Tests for create_result() — result file creation + phase advancement fix.

The fix in result.py: after submit_result(), complete_phase() is called to
advance the task status through the DAG. These tests verify the combined
behavior: result_file is set AND status advances past 'assigned'.
"""

from __future__ import annotations

import os
import sqlite3

import pytest

from minion.db import init_db, reset_db_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _setup_project(tmp_path) -> tuple[str, str]:
    """Create .work/ tree, initialize DB, return (work_dir, db_path)."""
    work = tmp_path / ".work"
    work.mkdir()
    db_path = str(work / "minion.db")
    os.environ["MINION_DB_PATH"] = db_path
    reset_db_path()
    init_db()
    return str(work), db_path


def _insert_agent(db_path: str, name: str, agent_class: str = "coder") -> None:
    """Register a minimal agent row."""
    from minion.db import now_iso
    now = now_iso()
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT OR IGNORE INTO agents (name, agent_class, registered_at, last_seen) VALUES (?, ?, ?, ?)",
        (name, agent_class, now, now),
    )
    conn.commit()
    conn.close()


def _insert_task(db_path: str, title: str, status: str, agent: str, task_file: str, flow_type: str = "bugfix") -> int:
    """Insert a task row and return its id."""
    from minion.db import now_iso
    now = now_iso()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO tasks
               (title, task_file, status, assigned_to, created_by,
                flow_type, activity_count, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)""",
        (title, task_file, status, agent, agent, flow_type, now, now),
    )
    task_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return task_id


def _task_status(db_path: str, task_id: int) -> str:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT status FROM tasks WHERE id = ?", (task_id,)).fetchone()
    conn.close()
    return row["status"]


def _task_result_file(db_path: str, task_id: int) -> str | None:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT result_file FROM tasks WHERE id = ?", (task_id,)).fetchone()
    conn.close()
    return row["result_file"]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolated_db(tmp_path):
    """Each test gets its own .work/ and DB; env var is restored after."""
    original = os.environ.get("MINION_DB_PATH")
    yield tmp_path
    if original is None:
        os.environ.pop("MINION_DB_PATH", None)
    else:
        os.environ["MINION_DB_PATH"] = original
    reset_db_path()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCreateResult:
    """create_result() writes a result file and advances the DAG status."""

    def _setup(self, tmp_path) -> tuple[str, str, int, str]:
        """Bootstrap project, agent, and task. Returns (work_dir, db_path, task_id, agent)."""
        work_dir, db_path = _setup_project(tmp_path)
        agent = "coder-1"
        _insert_agent(db_path, agent, "coder")

        # Task must be in assigned status — that's what complete_phase() advances from
        task_file = str(tmp_path / "TASK-1.md")
        with open(task_file, "w") as f:
            f.write("# Task 1\n")
        task_id = _insert_task(db_path, "Fix the bug", "assigned", agent, task_file)
        return work_dir, db_path, task_id, agent

    def test_status_advances_past_assigned(self, isolated_db):
        """After create_result() on an assigned task, status is no longer 'assigned'."""
        work_dir, db_path, task_id, agent = self._setup(isolated_db)

        from minion.tasks.result import create_result
        result = create_result(agent, task_id, summary="Fixed the null pointer crash")

        assert "error" not in result
        status = _task_status(db_path, task_id)
        assert status != "assigned", f"Expected status to advance past 'assigned', got '{status}'"

    def test_result_file_set_and_status_advanced(self, isolated_db):
        """result_file is written to disk and DB, AND the task status advances."""
        work_dir, db_path, task_id, agent = self._setup(isolated_db)

        from minion.tasks.result import create_result
        result = create_result(
            agent,
            task_id,
            summary="Patched race condition in audio pipeline",
            files_changed="src/audio.py, src/pipeline.py",
            notes="Required adding a lock around the shared buffer.",
        )

        assert "error" not in result

        # result_file must be persisted to DB
        stored_result_file = _task_result_file(db_path, task_id)
        assert stored_result_file is not None, "result_file not written to DB"
        assert os.path.exists(stored_result_file), f"result_file path does not exist on disk: {stored_result_file}"

        # Status must have advanced — assigned -> in_progress is the DAG next for bugfix
        status = _task_status(db_path, task_id)
        assert status != "assigned", f"Status did not advance, still '{status}'"

    def test_response_includes_result_file_and_phase_advanced(self, isolated_db):
        """Return dict contains both result_file path and phase_advanced from DAG."""
        work_dir, db_path, task_id, agent = self._setup(isolated_db)

        from minion.tasks.result import create_result
        result = create_result(agent, task_id, summary="Rewrote the scheduler loop")

        assert "error" not in result
        # result_file path is returned by submit_result
        assert "result_file" in result, f"Missing 'result_file' in result: {result}"
        assert result["result_file"].endswith(f"TASK-{task_id}-result.md")
        # phase_advanced is set by the complete_phase() call added in the fix
        assert "phase_advanced" in result, (
            f"Missing 'phase_advanced' key — complete_phase() may not have been called. Result: {result}"
        )

    def test_status_advances_to_in_progress_for_bugfix(self, isolated_db):
        """For bugfix flow, assigned -> complete_phase(passed=True) -> in_progress."""
        work_dir, db_path, task_id, agent = self._setup(isolated_db)

        from minion.tasks.result import create_result
        create_result(agent, task_id, summary="Squashed the memory leak")

        status = _task_status(db_path, task_id)
        # bugfix DAG: assigned.next = in_progress
        assert status == "in_progress", f"Expected 'in_progress', got '{status}'"

    def test_unknown_agent_returns_error_no_phase_advance(self, isolated_db):
        """If agent is not registered, submit_result errors and complete_phase is not called."""
        work_dir, db_path, task_id, agent = self._setup(isolated_db)

        from minion.tasks.result import create_result
        result = create_result("ghost-agent", task_id, summary="Should not work")

        assert "error" in result
        # Status must remain assigned — no phase should have advanced
        status = _task_status(db_path, task_id)
        assert status == "assigned"
