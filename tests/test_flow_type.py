"""Tests for the flow_type column — covers the task_type→flow_type rename.

Background: v3 migration renamed tasks.task_type to tasks.flow_type. A legacy
migration path (_migrate) was re-adding task_type after v3 ran. Application
code (create_task) always writes to flow_type, so tests verify that the column
used for storage is flow_type and that flow_type carries the correct value.
"""

from __future__ import annotations

import os
import sqlite3
import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from minion.cli import cli


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _setup_project(tmp_path: Path) -> tuple[Path, str]:
    """Create a .work/ tree and initialize the DB via the CLI.

    Returns (project_dir, db_path_str).
    """
    work = tmp_path / ".work"
    work.mkdir()
    db_path = str(work / "minion.db")
    runner = CliRunner()
    result = runner.invoke(cli, ["-C", str(tmp_path), "agent", "--help"])
    # The -C flag triggers init_db() in cli(); --help exits 0 without side effects
    assert result.exit_code == 0, result.output
    return tmp_path, db_path


def _columns(db_path: str, table: str) -> set[str]:
    """Return the set of column names for *table*."""
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        return {row[1] for row in rows}
    finally:
        conn.close()


def _register_lead(db_path: str, name: str = "test-lead") -> None:
    """Insert a lead agent directly into the DB."""
    import datetime
    now = datetime.datetime.now().isoformat()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        "INSERT OR REPLACE INTO agents (name, agent_class, registered_at, last_seen) "
        "VALUES (?, 'lead', ?, ?)",
        (name, now, now),
    )
    conn.commit()
    conn.close()


def _insert_battle_plan(db_path: str, agent: str = "test-lead") -> None:
    """Insert an active battle plan so create_task() won't block."""
    import datetime
    now = datetime.datetime.now().isoformat()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        "INSERT INTO battle_plan (set_by, plan_file, status, created_at, updated_at) "
        "VALUES (?, ?, 'active', ?, ?)",
        (agent, "plan.md", now, now),
    )
    conn.commit()
    conn.close()


def _run(runner: CliRunner, project_dir: Path, *args: str):
    return runner.invoke(cli, ["-C", str(project_dir)] + list(args))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def project_dir(tmp_path):
    """Temp project dir with DB fully initialized via CLI."""
    project, _ = _setup_project(tmp_path)
    return project


@pytest.fixture
def db_path(project_dir):
    return str(project_dir / ".work" / "minion.db")


@pytest.fixture
def runner():
    return CliRunner()


# ---------------------------------------------------------------------------
# Tests: schema shape
# ---------------------------------------------------------------------------


class TestFlowTypeSchema:
    def test_fresh_db_has_flow_type_column(self, db_path):
        """After init_db, tasks table must have flow_type."""
        cols = _columns(db_path, "tasks")
        assert "flow_type" in cols

    def test_fresh_db_no_task_type_column(self, db_path):
        """After init_db + all migrations, tasks table must not have task_type.

        The _migrate() legacy path re-added task_type on old DBs. This test
        confirms a fresh init does NOT produce a duplicate task_type column.
        """
        cols = _columns(db_path, "tasks")
        # task_type column should not exist after v3 migration has been applied
        assert "task_type" not in cols, (
            "tasks table still has task_type column after full migration run. "
            "The _migrate() legacy path may be re-adding it."
        )

    def test_schema_version_at_least_v3(self, db_path):
        """Schema version table must show v3 (task_type→flow_type rename) applied."""
        conn = sqlite3.connect(db_path)
        try:
            row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
            assert row[0] is not None and row[0] >= 3, (
                f"Expected schema version >= 3, got {row[0]}"
            )
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Tests: create_task() writes to flow_type
# ---------------------------------------------------------------------------


class TestCreateTaskFlowType:
    def _make_task_file(self, project_dir: Path, name: str = "task.md") -> str:
        task_file = project_dir / ".work" / name
        task_file.write_text(f"# Task: {name}\n")
        return str(task_file)

    def test_create_task_with_feature_type_stores_flow_type(self, db_path, project_dir):
        """create_task(task_type='feature') must write 'feature' to flow_type column."""
        from minion.tasks.create_task import create_task

        _register_lead(db_path, "alpha")
        _insert_battle_plan(db_path, "alpha")
        task_file = self._make_task_file(project_dir)

        # Redirect get_db() to our test DB
        os.environ["MINION_DB_PATH"] = db_path
        from minion.db import reset_db_path
        reset_db_path()

        result = create_task(
            agent_name="alpha",
            title="My Feature",
            task_file=task_file,
            task_type="feature",
        )
        assert "error" not in result, result
        task_id = result["task_id"]

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        conn.close()

        assert row is not None
        assert row["flow_type"] == "feature", (
            f"Expected flow_type='feature', got {dict(row)}"
        )

    def test_create_task_with_bugfix_type_stores_flow_type(self, db_path, project_dir):
        """create_task(task_type='bugfix') must write 'bugfix' to flow_type column."""
        from minion.tasks.create_task import create_task

        _register_lead(db_path, "bravo")
        _insert_battle_plan(db_path, "bravo")
        task_file = self._make_task_file(project_dir, "bugfix-task.md")

        os.environ["MINION_DB_PATH"] = db_path
        from minion.db import reset_db_path
        reset_db_path()

        result = create_task(
            agent_name="bravo",
            title="A Bugfix",
            task_file=task_file,
            task_type="bugfix",
        )
        assert "error" not in result, result
        task_id = result["task_id"]

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        conn.close()

        assert row["flow_type"] == "bugfix"

    def test_create_task_chore_type_no_battle_plan_required(self, db_path, project_dir):
        """Chore tasks bypass the battle-plan gate and use flow_type for storage."""
        from minion.tasks.create_task import create_task

        _register_lead(db_path, "charlie")
        # Deliberately skip _insert_battle_plan — chores must not require it
        task_file = self._make_task_file(project_dir, "chore-task.md")

        os.environ["MINION_DB_PATH"] = db_path
        from minion.db import reset_db_path
        reset_db_path()

        result = create_task(
            agent_name="charlie",
            title="A Chore",
            task_file=task_file,
            task_type="chore",
        )
        assert "error" not in result, result
        task_id = result["task_id"]

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        conn.close()

        assert row["flow_type"] == "chore"

    def test_flow_type_value_readable_by_column_name(self, db_path, project_dir):
        """Rows inserted via create_task() must be queryable by flow_type column."""
        from minion.tasks.create_task import create_task

        _register_lead(db_path, "delta")
        _insert_battle_plan(db_path, "delta")
        task_file = self._make_task_file(project_dir, "readable.md")

        os.environ["MINION_DB_PATH"] = db_path
        from minion.db import reset_db_path
        reset_db_path()

        create_task(
            agent_name="delta",
            title="Readable Task",
            task_file=task_file,
            task_type="feature",
        )

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        # Query specifically on flow_type — if the column is missing this raises OperationalError
        rows = conn.execute(
            "SELECT id, flow_type FROM tasks WHERE flow_type = 'feature'"
        ).fetchall()
        conn.close()

        assert len(rows) >= 1
        assert all(r["flow_type"] == "feature" for r in rows)


# ---------------------------------------------------------------------------
# Tests: legacy migration idempotency
# ---------------------------------------------------------------------------


class TestLegacyMigrationIdempotency:
    def test_init_db_twice_does_not_duplicate_columns(self, db_path):
        """Calling init_db() a second time must not re-add task_type."""
        from minion.db import init_db, reset_db_path

        os.environ["MINION_DB_PATH"] = db_path
        reset_db_path()

        init_db()  # second call on already-initialized DB
        cols = _columns(db_path, "tasks")

        assert "flow_type" in cols
        assert "task_type" not in cols, (
            "Second init_db() call re-added task_type column — "
            "legacy _migrate() is not guarded against v3+ schemas."
        )

    def test_v3_migration_applied_exactly_once(self, db_path):
        """schema_version must record v3 exactly once (no duplicate migration rows)."""
        conn = sqlite3.connect(db_path)
        try:
            rows = conn.execute(
                "SELECT COUNT(*) FROM schema_version WHERE version = 3"
            ).fetchone()
            assert rows[0] == 1, (
                f"Expected exactly 1 row for v3 in schema_version, got {rows[0]}"
            )
        finally:
            conn.close()
