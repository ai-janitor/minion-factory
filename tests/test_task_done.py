"""Tests for the done_task function — fast-close for externally completed tasks."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from minion.db import init_db, reset_db_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _setup_db(db_path: str) -> None:
    """Initialize full schema needed by done_task (agents, tasks, transition_log)."""
    import os
    os.environ["MINION_DB_PATH"] = db_path
    reset_db_path()
    init_db()


def _insert_lead(db_path: str, name: str = "atlas") -> None:
    now = "2026-02-22T00:00:00"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT OR REPLACE INTO agents (name, agent_class, registered_at, last_seen) VALUES (?, 'lead', ?, ?)",
        (name, now, now),
    )
    conn.commit()
    conn.close()


def _insert_coder(db_path: str, name: str = "coder-1") -> None:
    now = "2026-02-22T00:00:00"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT OR REPLACE INTO agents (name, agent_class, registered_at, last_seen) VALUES (?, 'coder', ?, ?)",
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


class TestDoneTaskBasic:
    def test_open_task_closes_successfully(self, db_path, monkeypatch):
        """done_task on an open task returns status=closed."""
        monkeypatch.chdir(db_path.replace("/.work/minion.db", ""))
        _insert_lead(db_path)
        task_id = _insert_open_task(db_path)

        from minion.tasks import done_task
        result = done_task("atlas", task_id)

        assert "error" not in result
        assert result["status"] == "closed"
        assert result["task_id"] == task_id
        assert result["from_status"] == "open"

    def test_close_sets_status_in_db(self, db_path, monkeypatch):
        """DB row reflects closed status after done_task."""
        monkeypatch.chdir(db_path.replace("/.work/minion.db", ""))
        _insert_lead(db_path)
        task_id = _insert_open_task(db_path, title="DB State Check")

        from minion.tasks import done_task
        done_task("atlas", task_id)

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT status FROM tasks WHERE id = ?", (task_id,)).fetchone()
        conn.close()
        assert row["status"] == "closed"

    def test_returns_task_title(self, db_path, monkeypatch):
        """Result dict includes the task title."""
        monkeypatch.chdir(db_path.replace("/.work/minion.db", ""))
        _insert_lead(db_path)
        task_id = _insert_open_task(db_path, title="My Important Task")

        from minion.tasks import done_task
        result = done_task("atlas", task_id)

        assert result["title"] == "My Important Task"

    def test_logs_transition(self, db_path, monkeypatch):
        """A transition_log entry is recorded for the closure."""
        monkeypatch.chdir(db_path.replace("/.work/minion.db", ""))
        _insert_lead(db_path)
        task_id = _insert_open_task(db_path)

        from minion.tasks import done_task
        done_task("atlas", task_id)

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM transition_log WHERE entity_id = ? AND entity_type = 'task'",
            (task_id,),
        ).fetchone()
        conn.close()
        assert row is not None
        assert row["to_status"] == "closed"
        assert row["from_status"] == "open"
        assert row["triggered_by"] == "atlas"


class TestDoneTaskWithSummary:
    def test_summary_creates_result_file(self, db_path, project_dir, monkeypatch):
        """When summary is provided, a result markdown file is written to .work/results/."""
        monkeypatch.chdir(str(project_dir))
        _insert_lead(db_path)
        task_id = _insert_open_task(db_path)

        from minion.tasks import done_task
        result = done_task("atlas", task_id, summary="Implemented OAuth2 flow.")

        assert "result_file" in result
        result_path = Path(result["result_file"])
        assert result_path.exists()
        content = result_path.read_text()
        assert f"Task #{task_id} Result" in content
        assert "Implemented OAuth2 flow." in content

    def test_summary_sets_result_file_in_db(self, db_path, project_dir, monkeypatch):
        """result_file column is set in the DB when summary is provided."""
        monkeypatch.chdir(str(project_dir))
        _insert_lead(db_path)
        task_id = _insert_open_task(db_path)

        from minion.tasks import done_task
        done_task("atlas", task_id, summary="Done!")

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT result_file FROM tasks WHERE id = ?", (task_id,)).fetchone()
        conn.close()
        assert row["result_file"] is not None
        assert f"TASK-{task_id}-result.md" in row["result_file"]

    def test_no_summary_no_result_file(self, db_path, monkeypatch):
        """Without a summary, no result_file key appears in the return dict."""
        monkeypatch.chdir(db_path.replace("/.work/minion.db", ""))
        _insert_lead(db_path)
        task_id = _insert_open_task(db_path)

        from minion.tasks import done_task
        result = done_task("atlas", task_id)

        assert "result_file" not in result

    def test_result_file_named_by_task_id(self, db_path, project_dir, monkeypatch):
        """Result file follows the TASK-<id>-result.md naming convention."""
        monkeypatch.chdir(str(project_dir))
        _insert_lead(db_path)
        task_id = _insert_open_task(db_path)

        from minion.tasks import done_task
        result = done_task("atlas", task_id, summary="Summary text.")

        assert result["result_file"].endswith(f"TASK-{task_id}-result.md")


class TestDoneTaskAlreadyClosed:
    def test_already_closed_returns_error(self, db_path, monkeypatch):
        """done_task on a task already closed returns an error dict."""
        monkeypatch.chdir(db_path.replace("/.work/minion.db", ""))
        _insert_lead(db_path)
        task_id = _insert_open_task(db_path)

        # Close it first
        conn = sqlite3.connect(db_path)
        conn.execute("UPDATE tasks SET status = 'closed' WHERE id = ?", (task_id,))
        conn.commit()
        conn.close()

        from minion.tasks import done_task
        result = done_task("atlas", task_id)

        assert "error" in result
        assert "already closed" in result["error"]

    def test_already_closed_twice_still_errors(self, db_path, project_dir, monkeypatch):
        """Calling done_task twice on the same task returns error on the second call."""
        monkeypatch.chdir(str(project_dir))
        _insert_lead(db_path)
        task_id = _insert_open_task(db_path)

        from minion.tasks import done_task
        done_task("atlas", task_id)
        result = done_task("atlas", task_id)

        assert "error" in result
        assert str(task_id) in result["error"]

    def test_nonexistent_task_returns_error(self, db_path, monkeypatch):
        """done_task with a task ID that does not exist returns an error."""
        monkeypatch.chdir(db_path.replace("/.work/minion.db", ""))
        _insert_lead(db_path)

        from minion.tasks import done_task
        result = done_task("atlas", 99999)

        assert "error" in result
        assert "not found" in result["error"]


class TestDoneTaskAgentClass:
    def test_requires_lead_class(self, db_path, monkeypatch):
        """done_task with a coder-class agent returns a BLOCKED error."""
        monkeypatch.chdir(db_path.replace("/.work/minion.db", ""))
        _insert_coder(db_path, name="coder-1")
        task_id = _insert_open_task(db_path)

        from minion.tasks import done_task
        result = done_task("coder-1", task_id)

        assert "error" in result
        assert "BLOCKED" in result["error"]
        assert "lead" in result["error"]

    def test_unregistered_agent_returns_error(self, db_path, monkeypatch):
        """done_task with an agent name not in the DB returns a BLOCKED error."""
        monkeypatch.chdir(db_path.replace("/.work/minion.db", ""))
        task_id = _insert_open_task(db_path)

        from minion.tasks import done_task
        result = done_task("ghost-agent", task_id)

        assert "error" in result
        assert "BLOCKED" in result["error"]
        assert "ghost-agent" in result["error"]

    def test_lead_class_agent_succeeds(self, db_path, monkeypatch):
        """A lead-class agent can close any open task."""
        monkeypatch.chdir(db_path.replace("/.work/minion.db", ""))
        _insert_lead(db_path, name="lead-1")
        task_id = _insert_open_task(db_path)

        from minion.tasks import done_task
        result = done_task("lead-1", task_id)

        assert "error" not in result
        assert result["status"] == "closed"
