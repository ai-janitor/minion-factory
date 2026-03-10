"""Tests for TaskDB post-close guard — every public method raises TaskDBClosedError.

Purpose: Verify that calling any public TaskDB method after close() raises
         TaskDBClosedError with a meaningful message, not a raw AttributeError.
Rationale: Task #140 / Backlog #99 — TaskDB connection is None after close(),
           methods must guard against that with a clear error.
Responsibility: Test coverage for TaskDB lifecycle guards (_ensure_open).
Organization: One test per public method, plus context manager tests."""

from __future__ import annotations

import pytest

from minion.db import init_db, reset_db_path
from minion.tasks.db import TaskDB, TaskDBClosedError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Each test gets its own .work/ tree and isolated DB."""
    work_dir = tmp_path / ".work"
    work_dir.mkdir(parents=True, exist_ok=True)

    db_path = str(work_dir / "minion.db")
    monkeypatch.setenv("MINION_DB_PATH", db_path)
    reset_db_path()
    init_db()

    monkeypatch.chdir(tmp_path)
    yield tmp_path

    reset_db_path()


@pytest.fixture()
def closed_db():
    """Return a TaskDB instance that has already been closed."""
    db = TaskDB()
    db.close()
    return db


# ---------------------------------------------------------------------------
# Guard tests — every public method must raise TaskDBClosedError after close
# ---------------------------------------------------------------------------


class TestPostCloseGuard:
    """Every public method on TaskDB must raise TaskDBClosedError after close()."""

    def test_create_project_raises(self, closed_db):
        with pytest.raises(TaskDBClosedError, match="closed"):
            closed_db.create_project("proj-1", "test project")

    def test_get_project_raises(self, closed_db):
        with pytest.raises(TaskDBClosedError, match="closed"):
            closed_db.get_project("proj-1")

    def test_list_projects_raises(self, closed_db):
        with pytest.raises(TaskDBClosedError, match="closed"):
            closed_db.list_projects()

    def test_list_projects_with_status_raises(self, closed_db):
        with pytest.raises(TaskDBClosedError, match="closed"):
            closed_db.list_projects(status="active")

    def test_create_task_raises(self, closed_db):
        with pytest.raises(TaskDBClosedError, match="closed"):
            closed_db.create_task("t-1", "proj-1", "bugfix", "test task")

    def test_get_task_raises(self, closed_db):
        with pytest.raises(TaskDBClosedError, match="closed"):
            closed_db.get_task("t-1")

    def test_list_tasks_raises(self, closed_db):
        with pytest.raises(TaskDBClosedError, match="closed"):
            closed_db.list_tasks()

    def test_list_tasks_with_filters_raises(self, closed_db):
        with pytest.raises(TaskDBClosedError, match="closed"):
            closed_db.list_tasks(project_id="proj-1", status="open")

    def test_transition_task_raises(self, closed_db):
        with pytest.raises(TaskDBClosedError, match="closed"):
            closed_db.transition_task("t-1", "in_progress", agent="coder-1")

    def test_complete_raises(self, closed_db):
        with pytest.raises(TaskDBClosedError, match="closed"):
            closed_db.complete("t-1", "coder-1")

    def test_get_transitions_raises(self, closed_db):
        with pytest.raises(TaskDBClosedError, match="closed"):
            closed_db.get_transitions("t-1")


# ---------------------------------------------------------------------------
# Context manager tests
# ---------------------------------------------------------------------------


class TestContextManager:
    """TaskDB used as context manager should close on exit and guard after."""

    def test_context_manager_closes_on_exit(self):
        db = TaskDB()
        with db:
            # Should work inside the context
            db.list_projects()
        # Should be closed after exiting
        assert db._closed is True

    def test_context_manager_raises_after_exit(self):
        db = TaskDB()
        with db:
            pass
        with pytest.raises(TaskDBClosedError, match="closed"):
            db.list_projects()


# ---------------------------------------------------------------------------
# Double-close safety
# ---------------------------------------------------------------------------


class TestDoubleClose:
    """Calling close() twice should not raise."""

    def test_double_close_is_safe(self):
        db = TaskDB()
        db.close()
        db.close()  # Should not raise
        assert db._closed is True


# ---------------------------------------------------------------------------
# Error message quality
# ---------------------------------------------------------------------------


class TestErrorMessage:
    """TaskDBClosedError message should guide the user to create a new instance."""

    def test_error_message_is_helpful(self, closed_db):
        with pytest.raises(TaskDBClosedError) as exc_info:
            closed_db.get_task("t-1")
        msg = str(exc_info.value)
        assert "closed" in msg.lower()
        assert "new TaskDB" in msg
