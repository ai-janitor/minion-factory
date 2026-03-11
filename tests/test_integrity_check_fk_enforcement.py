"""Tests for FK enforcement, integrity checking, and backlog close guard.

Purpose: Verify that PRAGMA foreign_keys=ON is active on all connections,
         that the integrity checker detects orphan rows, and that the
         clean_orphans function fixes them. Also tests the backlog close guard.
Rationale: Backlog #239 / task #157 — FK enforcement was added to connect(),
           and we need regression tests to ensure it stays enabled.
Responsibility: Test FK enforcement, integrity module, and business logic guards.
Organization: Grouped by concern — FK enforcement, integrity checker, backlog guard.
"""

from __future__ import annotations

import sqlite3

import pytest

from minion.db import get_db, init_db, reset_db_path
from minion.db.connection import connect
from minion.db.integrity_check_foreign_keys_and_orphans import (
    check_all_fk_integrity,
    clean_orphans,
    report,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def isolated_db(tmp_path, monkeypatch):
    """Each test gets its own .work/ tree and isolated SQLite DB."""
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
def db_path(isolated_db):
    """Return the DB file path string."""
    return str(isolated_db / ".work" / "minion.db")


# ---------------------------------------------------------------------------
# FK enforcement tests — connect() must enable PRAGMA foreign_keys=ON
# ---------------------------------------------------------------------------


class TestFKEnforcement:
    """Verify that foreign_keys pragma is ON for all connection types."""

    def test_connect_enables_fk(self, db_path):
        """connect() should set PRAGMA foreign_keys=ON."""
        conn = connect(db_path)
        try:
            fk_status = conn.execute("PRAGMA foreign_keys").fetchone()[0]
            assert fk_status == 1, "foreign_keys should be ON (1) after connect()"
        finally:
            conn.close()

    def test_get_db_enables_fk(self, isolated_db):
        """get_db() should have foreign_keys=ON (inherited from connect())."""
        conn = get_db()
        try:
            fk_status = conn.execute("PRAGMA foreign_keys").fetchone()[0]
            assert fk_status == 1, "foreign_keys should be ON (1) after get_db()"
        finally:
            conn.close()

    def test_fk_enforcement_blocks_bad_task_comment(self, isolated_db):
        """Inserting a task_comment with nonexistent task_id should raise IntegrityError."""
        conn = get_db()
        try:
            # task_comments.task_id REFERENCES tasks(id) — task 99999 doesn't exist
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO task_comments (task_id, agent_name, comment, created_at) "
                    "VALUES (99999, 'test-agent', 'orphan comment', '2025-01-01T00:00:00Z')"
                )
        finally:
            conn.close()

    def test_fk_enforcement_allows_valid_task_comment(self, isolated_db):
        """Inserting a task_comment with a valid task_id should succeed."""
        conn = get_db()
        try:
            # Create a valid task first
            from minion.db.timestamp_and_agent_registry import now_iso
            now = now_iso()
            conn.execute(
                "INSERT INTO tasks (title, task_file, created_by, status, created_at, updated_at) "
                "VALUES ('test task', '/tmp/test.md', 'tester', 'open', ?, ?)",
                (now, now),
            )
            task_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

            # This should succeed — valid FK reference
            conn.execute(
                "INSERT INTO task_comments (task_id, agent_name, comment, created_at) "
                "VALUES (?, 'test-agent', 'valid comment', ?)",
                (task_id, now),
            )
            conn.commit()

            # Verify the comment was inserted
            count = conn.execute("SELECT COUNT(*) FROM task_comments WHERE task_id = ?", (task_id,)).fetchone()[0]
            assert count == 1
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Integrity checker tests
# ---------------------------------------------------------------------------


class TestIntegrityChecker:
    """Tests for check_all_fk_integrity, clean_orphans, and report."""

    def test_clean_db_has_no_violations(self, isolated_db):
        """A fresh DB should have no FK violations."""
        conn = get_db()
        try:
            result = check_all_fk_integrity(conn)
            assert result["status"] == "clean"
            assert result["total_violations"] == 0
        finally:
            conn.close()

    def test_detects_orphan_requirement_id(self, isolated_db):
        """Tasks with requirement_id pointing to nonexistent requirement should be detected."""
        # Use raw sqlite3 to bypass FK enforcement and insert bad data
        db_file = str(isolated_db / ".work" / "minion.db")
        raw_conn = sqlite3.connect(db_file)
        raw_conn.execute("PRAGMA foreign_keys=OFF")
        from minion.db.timestamp_and_agent_registry import now_iso
        now = now_iso()
        raw_conn.execute(
            "INSERT INTO tasks (title, task_file, created_by, status, requirement_id, created_at, updated_at) "
            "VALUES ('orphan task', '/tmp/t.md', 'tester', 'open', 99999, ?, ?)",
            (now, now),
        )
        raw_conn.commit()
        raw_conn.close()

        # Now check with the integrity checker
        conn = get_db()
        try:
            result = check_all_fk_integrity(conn)
            assert result["status"] == "violations_found"
            assert result["total_violations"] >= 1
            assert "tasks.requirement_id" in result["violations"]
        finally:
            conn.close()

    def test_detects_orphan_parent_id(self, isolated_db):
        """Tasks with parent_id pointing to nonexistent task should be detected."""
        db_file = str(isolated_db / ".work" / "minion.db")
        raw_conn = sqlite3.connect(db_file)
        raw_conn.execute("PRAGMA foreign_keys=OFF")
        from minion.db.timestamp_and_agent_registry import now_iso
        now = now_iso()
        raw_conn.execute(
            "INSERT INTO tasks (title, task_file, created_by, status, parent_id, created_at, updated_at) "
            "VALUES ('child task', '/tmp/t.md', 'tester', 'open', 88888, ?, ?)",
            (now, now),
        )
        raw_conn.commit()
        raw_conn.close()

        conn = get_db()
        try:
            result = check_all_fk_integrity(conn)
            assert "tasks.parent_id" in result["violations"]
        finally:
            conn.close()

    def test_clean_orphans_dry_run(self, isolated_db):
        """Dry run should report but not modify."""
        db_file = str(isolated_db / ".work" / "minion.db")
        raw_conn = sqlite3.connect(db_file)
        raw_conn.execute("PRAGMA foreign_keys=OFF")
        from minion.db.timestamp_and_agent_registry import now_iso
        now = now_iso()
        raw_conn.execute(
            "INSERT INTO tasks (title, task_file, created_by, status, requirement_id, created_at, updated_at) "
            "VALUES ('orphan', '/tmp/t.md', 'tester', 'open', 99999, ?, ?)",
            (now, now),
        )
        raw_conn.commit()
        raw_conn.close()

        conn = get_db()
        try:
            result = clean_orphans(conn, dry_run=True)
            assert result["dry_run"] is True
            assert result["total_fixed"] >= 1

            # Verify the orphan is still there
            check = check_all_fk_integrity(conn)
            assert check["total_violations"] >= 1
        finally:
            conn.close()

    def test_clean_orphans_fix(self, isolated_db):
        """Fix mode should NULL orphan requirement_ids."""
        db_file = str(isolated_db / ".work" / "minion.db")
        raw_conn = sqlite3.connect(db_file)
        raw_conn.execute("PRAGMA foreign_keys=OFF")
        from minion.db.timestamp_and_agent_registry import now_iso
        now = now_iso()
        raw_conn.execute(
            "INSERT INTO tasks (title, task_file, created_by, status, requirement_id, created_at, updated_at) "
            "VALUES ('orphan', '/tmp/t.md', 'tester', 'open', 99999, ?, ?)",
            (now, now),
        )
        raw_conn.commit()
        raw_conn.close()

        conn = get_db()
        try:
            result = clean_orphans(conn, dry_run=False)
            assert result["dry_run"] is False
            assert result["total_fixed"] >= 1

            # Verify the orphan is gone
            check = check_all_fk_integrity(conn)
            assert check["status"] == "clean"
        finally:
            conn.close()

    def test_report_clean_db(self, isolated_db):
        """Report on clean DB should say so."""
        conn = get_db()
        try:
            r = report(conn)
            assert "clean" in r.lower() or "No orphan" in r
        finally:
            conn.close()

    def test_report_with_violations(self, isolated_db):
        """Report on DB with violations should list them."""
        db_file = str(isolated_db / ".work" / "minion.db")
        raw_conn = sqlite3.connect(db_file)
        raw_conn.execute("PRAGMA foreign_keys=OFF")
        from minion.db.timestamp_and_agent_registry import now_iso
        now = now_iso()
        raw_conn.execute(
            "INSERT INTO tasks (title, task_file, created_by, status, requirement_id, created_at, updated_at) "
            "VALUES ('orphan', '/tmp/t.md', 'tester', 'open', 99999, ?, ?)",
            (now, now),
        )
        raw_conn.commit()
        raw_conn.close()

        conn = get_db()
        try:
            r = report(conn)
            assert "violation" in r.lower()
            assert "tasks.requirement_id" in r
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Backlog close guard tests
# ---------------------------------------------------------------------------


class TestBacklogCloseGuard:
    """Test that closing a backlog item with open tasks is refused."""

    def test_close_backlog_refuses_with_open_tasks(self, isolated_db):
        """Closing a backlog item should fail if there are open tasks linked to its requirement."""
        from minion.backlog.update_item import update_item
        from minion.db.timestamp_and_agent_registry import now_iso
        now = now_iso()

        conn = get_db()
        try:
            # Create a backlog item that was promoted
            conn.execute(
                "INSERT INTO backlog (file_path, type, title, status, promoted_to, created_by, created_at, updated_at) "
                "VALUES ('test-item', 'bug', 'Test Bug', 'promoted', 'test-req', 'tester', ?, ?)",
                (now, now),
            )

            # Create the requirement it was promoted to
            conn.execute(
                "INSERT INTO requirements (file_path, origin, stage, created_by, created_at, updated_at) "
                "VALUES ('test-req', 'bug', 'seed', 'tester', ?, ?)",
                (now, now),
            )
            req_id = conn.execute("SELECT id FROM requirements WHERE file_path = 'test-req'").fetchone()[0]

            # Create an open task linked to that requirement
            conn.execute(
                "INSERT INTO tasks (title, task_file, created_by, status, requirement_id, created_at, updated_at) "
                "VALUES ('open task', '/tmp/t.md', 'tester', 'open', ?, ?, ?)",
                (req_id, now, now),
            )
            conn.commit()
        finally:
            conn.close()

        # Try to close the backlog item — should be refused
        result = update_item(file_path="test-item", status="closed")
        assert "error" in result
        assert "open" in result["error"].lower() or "task" in result["error"].lower()

    def test_close_backlog_allowed_when_all_tasks_closed(self, isolated_db):
        """Closing a backlog item should succeed if all linked tasks are closed."""
        from minion.backlog.update_item import update_item
        from minion.db.timestamp_and_agent_registry import now_iso
        now = now_iso()

        conn = get_db()
        try:
            # Create a backlog item that was promoted
            conn.execute(
                "INSERT INTO backlog (file_path, type, title, status, promoted_to, created_by, created_at, updated_at) "
                "VALUES ('test-item-2', 'bug', 'Test Bug 2', 'promoted', 'test-req-2', 'tester', ?, ?)",
                (now, now),
            )

            # Create the requirement it was promoted to
            conn.execute(
                "INSERT INTO requirements (file_path, origin, stage, created_by, created_at, updated_at) "
                "VALUES ('test-req-2', 'bug', 'seed', 'tester', ?, ?)",
                (now, now),
            )
            req_id = conn.execute("SELECT id FROM requirements WHERE file_path = 'test-req-2'").fetchone()[0]

            # Create a CLOSED task linked to that requirement
            conn.execute(
                "INSERT INTO tasks (title, task_file, created_by, status, requirement_id, created_at, updated_at) "
                "VALUES ('done task', '/tmp/t.md', 'tester', 'closed', ?, ?, ?)",
                (req_id, now, now),
            )
            conn.commit()
        finally:
            conn.close()

        # Close should succeed
        result = update_item(file_path="test-item-2", status="closed")
        assert "error" not in result

    def test_close_backlog_allowed_when_not_promoted(self, isolated_db):
        """Closing a non-promoted backlog item should always succeed."""
        from minion.backlog.update_item import update_item
        from minion.db.timestamp_and_agent_registry import now_iso
        now = now_iso()

        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO backlog (file_path, type, title, status, created_by, created_at, updated_at) "
                "VALUES ('test-item-3', 'bug', 'Test Bug 3', 'open', 'tester', ?, ?)",
                (now, now),
            )
            conn.commit()
        finally:
            conn.close()

        result = update_item(file_path="test-item-3", status="closed")
        assert "error" not in result


# ---------------------------------------------------------------------------
# Migration v16 test
# ---------------------------------------------------------------------------


class TestMigrationV16:
    """Verify migration v16 cleans orphan requirement_ids."""

    def test_v16_nulls_orphan_requirement_ids(self, tmp_path, monkeypatch):
        """v16 should NULL requirement_id values that don't match any requirement."""
        from minion.db.migrations import _migrate_v16

        db_file = str(tmp_path / "test.db")
        conn = sqlite3.connect(db_file)
        conn.row_factory = sqlite3.Row

        # Create minimal schema
        conn.execute("""
            CREATE TABLE requirements (
                id INTEGER PRIMARY KEY,
                file_path TEXT,
                origin TEXT,
                stage TEXT DEFAULT 'seed',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                task_file TEXT NOT NULL DEFAULT '',
                created_by TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'open',
                requirement_id INTEGER,
                created_at TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL DEFAULT ''
            )
        """)

        # Insert a valid requirement
        conn.execute("INSERT INTO requirements (id, file_path, origin) VALUES (1, 'req-1', 'bug')")

        # Insert task with valid requirement_id
        conn.execute("INSERT INTO tasks (title, requirement_id) VALUES ('good task', 1)")

        # Insert task with orphan requirement_id (backlog ID, not in requirements)
        conn.execute("INSERT INTO tasks (title, requirement_id) VALUES ('orphan task', 999)")

        conn.commit()

        # Run migration
        _migrate_v16(conn)
        conn.commit()

        # Check: orphan should be NULLed, valid should be preserved
        rows = conn.execute("SELECT title, requirement_id FROM tasks ORDER BY id").fetchall()
        assert rows[0]["requirement_id"] == 1, "Valid requirement_id should be preserved"
        assert rows[1]["requirement_id"] is None, "Orphan requirement_id should be NULLed"

        conn.close()
