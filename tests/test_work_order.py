"""Tests for generate_work_order() — deterministic work order file generation.

Purpose: Tests for generate_work_order() — deterministic work order file generation.
Rationale: Test coverage for the work order module (backlog #274).
Responsibility: Verify that work order files are generated correctly with
  structured sections, lead-only access, and proper file paths.
Organization: One TestClass per concern, or standalone test functions."""

from __future__ import annotations

import os
import sqlite3

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.db]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _setup_project(tmp_path) -> tuple[str, str]:
    """Return (work_dir, db_path) — DB is already initialized by conftest.isolated_db."""
    work = tmp_path / ".work"
    return str(work), str(work / "minion.db")


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


def _insert_task(
    db_path: str,
    title: str,
    status: str,
    agent: str,
    task_file: str,
    flow_type: str = "bugfix",
    requirement_path: str = "",
) -> int:
    """Insert a task row and return its id."""
    from minion.db import now_iso
    now = now_iso()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO tasks
               (title, task_file, status, assigned_to, created_by,
                flow_type, activity_count, requirement_path, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?)""",
        (title, task_file, status, agent, agent, flow_type,
         requirement_path or None, now, now),
    )
    task_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return task_id


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _use_isolated_db(isolated_db):
    """Delegate to conftest.isolated_db; autouse ensures every test gets DB isolation."""


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGenerateWorkOrder:
    """generate_work_order() creates a structured order file at .work/orders/."""

    def _setup(self, tmp_path) -> tuple[str, str, int, str]:
        """Bootstrap project, agents, and task. Returns (work_dir, db_path, task_id, lead)."""
        work_dir, db_path = _setup_project(tmp_path)
        lead = "test-lead"
        _insert_agent(db_path, lead, "lead")
        _insert_agent(db_path, "worker-1", "coder")

        # Create task spec file
        task_file = str(tmp_path / "TASK-1.md")
        with open(task_file, "w") as f:
            f.write("# Fix the bug\n\nFix the null pointer in parser.py\n")
        task_id = _insert_task(db_path, "Fix the null pointer", "assigned", "worker-1", task_file)
        return work_dir, db_path, task_id, lead

    def test_order_file_created(self, isolated_db):
        """Order file is created at .work/orders/worker-<name>-task-<id>.md."""
        work_dir, db_path, task_id, lead = self._setup(isolated_db)

        from minion.tasks.work_order import generate_work_order
        result = generate_work_order(lead, task_id, "worker-1")

        assert "error" not in result
        assert result["status"] == "order_generated"
        assert os.path.exists(result["order_file"])
        assert f"worker-worker-1-task-{task_id}.md" in result["order_file"]

    def test_order_file_has_structured_sections(self, isolated_db):
        """Order file contains all required sections."""
        work_dir, db_path, task_id, lead = self._setup(isolated_db)

        from minion.tasks.work_order import generate_work_order
        result = generate_work_order(
            lead, task_id, "worker-1",
            files_to_modify="src/parser.py, src/lexer.py",
            fix_description="Fix null pointer dereference in parse_token()",
            test_command="uv run pytest tests/test_parser.py",
            commit_message="fix: null pointer in parse_token()",
        )

        assert "error" not in result
        with open(result["order_file"]) as f:
            content = f.read()

        assert "## Fix Description" in content
        assert "## Files to Modify" in content
        assert "## Test Command" in content
        assert "## Commit Message Format" in content
        assert "src/parser.py" in content
        assert "src/lexer.py" in content
        assert "uv run pytest tests/test_parser.py" in content
        assert "fix: null pointer in parse_token()" in content

    def test_order_file_contains_worker_prompt_instruction(self, isolated_db):
        """Order file ends with the deterministic worker instruction."""
        work_dir, db_path, task_id, lead = self._setup(isolated_db)

        from minion.tasks.work_order import generate_work_order
        result = generate_work_order(lead, task_id, "worker-1")

        assert "error" not in result
        with open(result["order_file"]) as f:
            content = f.read()

        assert "Do exactly what it says" in content
        assert "Write CHECKLIST.md first" in content
        assert "Do not improvise" in content

    def test_worker_prompt_returned(self, isolated_db):
        """Return dict includes the worker_prompt for direct use."""
        work_dir, db_path, task_id, lead = self._setup(isolated_db)

        from minion.tasks.work_order import generate_work_order
        result = generate_work_order(lead, task_id, "worker-1")

        assert "worker_prompt" in result
        assert "Read " in result["worker_prompt"]
        assert "Do exactly what it says" in result["worker_prompt"]

    def test_non_lead_blocked(self, isolated_db):
        """Non-lead agents cannot generate work orders."""
        work_dir, db_path, task_id, lead = self._setup(isolated_db)

        from minion.tasks.work_order import generate_work_order
        result = generate_work_order("worker-1", task_id, "worker-1")

        assert "error" in result
        assert "BLOCKED" in result["error"]

    def test_unknown_agent_blocked(self, isolated_db):
        """Unregistered agent gets an error."""
        work_dir, db_path, task_id, lead = self._setup(isolated_db)

        from minion.tasks.work_order import generate_work_order
        result = generate_work_order("ghost", task_id, "worker-1")

        assert "error" in result

    def test_unknown_task_returns_error(self, isolated_db):
        """Non-existent task ID returns error."""
        work_dir, db_path, task_id, lead = self._setup(isolated_db)

        from minion.tasks.work_order import generate_work_order
        result = generate_work_order(lead, 99999, "worker-1")

        assert "error" in result
        assert "not found" in result["error"]

    def test_defaults_applied_when_no_explicit_args(self, isolated_db):
        """Without explicit files/fix/test/commit, defaults are used from task spec."""
        work_dir, db_path, task_id, lead = self._setup(isolated_db)

        from minion.tasks.work_order import generate_work_order
        result = generate_work_order(lead, task_id, "worker-1")

        assert "error" not in result
        with open(result["order_file"]) as f:
            content = f.read()

        # Default test command
        assert "uv run pytest" in content
        # Task title used in default commit message
        assert "Fix the null pointer" in content

    def test_requirement_context_included(self, isolated_db):
        """When task has a requirement_path, requirement README is included."""
        work_dir, db_path = _setup_project(isolated_db)
        lead = "test-lead"
        _insert_agent(db_path, lead, "lead")
        _insert_agent(db_path, "worker-1", "coder")

        # Create requirement README
        req_path = "bugs/test-bug"
        req_dir = os.path.join(work_dir, "requirements", req_path)
        os.makedirs(req_dir, exist_ok=True)
        with open(os.path.join(req_dir, "README.md"), "w") as f:
            f.write("# Test Bug\n\nThis is the requirement context.\n")

        task_file = str(isolated_db / "TASK-req.md")
        with open(task_file, "w") as f:
            f.write("# Task with requirement\n")
        task_id = _insert_task(
            db_path, "Task with req context", "assigned", "worker-1",
            task_file, requirement_path=req_path,
        )

        from minion.tasks.work_order import generate_work_order
        result = generate_work_order(lead, task_id, "worker-1")

        assert "error" not in result
        with open(result["order_file"]) as f:
            content = f.read()

        assert "## Requirement Context" in content
        assert "This is the requirement context" in content
