"""Versioned schema migrations (v1 through v13).

Each migration is an idempotent callable that receives a sqlite3.Connection.
Migrations run in order inside individual transactions — failure rolls back
only the failed migration.
"""

from __future__ import annotations

import logging
import sqlite3
from typing import Any

from minion.db.helpers import now_iso

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Migration helpers
# ---------------------------------------------------------------------------


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    """Return the set of column names for *table*."""
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {row[1] if isinstance(row, tuple) else row["name"] for row in rows}


# ---------------------------------------------------------------------------
# Versioned migrations (v1-v12)
# ---------------------------------------------------------------------------


def _migrate_v1(conn: sqlite3.Connection) -> None:
    """Add parent_id and flow_type to requirements table."""
    cols = _table_columns(conn, "requirements")
    if "parent_id" not in cols:
        conn.execute(
            "ALTER TABLE requirements ADD COLUMN parent_id INTEGER REFERENCES requirements(id)"
        )
    if "flow_type" not in cols:
        conn.execute(
            "ALTER TABLE requirements ADD COLUMN flow_type TEXT NOT NULL DEFAULT 'requirement'"
        )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_requirements_parent ON requirements(parent_id)"
    )


def _migrate_v2(conn: sqlite3.Connection) -> None:
    """Add parent_id and requirement_id to tasks table."""
    cols = _table_columns(conn, "tasks")
    if "parent_id" not in cols:
        conn.execute(
            "ALTER TABLE tasks ADD COLUMN parent_id INTEGER REFERENCES tasks(id)"
        )
    if "requirement_id" not in cols:
        conn.execute(
            "ALTER TABLE tasks ADD COLUMN requirement_id INTEGER REFERENCES requirements(id)"
        )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_tasks_parent ON tasks(parent_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_tasks_requirement ON tasks(requirement_id)"
    )


def _migrate_v3(conn: sqlite3.Connection) -> None:
    """Rename tasks.task_type to tasks.flow_type via table rebuild.

    SQLite doesn't reliably support ALTER TABLE RENAME COLUMN on all versions,
    so we rebuild: create tasks_new, copy data, drop old, rename new.
    """
    cols = _table_columns(conn, "tasks")

    # Already renamed — nothing to do (idempotency guard)
    if "flow_type" in cols and "task_type" not in cols:
        return

    # Build tasks_new with flow_type instead of task_type.
    # Column order and defaults must exactly match the current schema
    # (original CREATE TABLE + legacy _migrate + v2 additions).
    conn.execute("""
        CREATE TABLE tasks_new (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            title           TEXT NOT NULL,
            task_file       TEXT NOT NULL,
            project         TEXT DEFAULT NULL,
            zone            TEXT DEFAULT NULL,
            status          TEXT NOT NULL DEFAULT 'open',
            blocked_by      TEXT DEFAULT NULL,
            assigned_to     TEXT DEFAULT NULL,
            created_by      TEXT NOT NULL,
            files           TEXT DEFAULT NULL,
            progress        TEXT DEFAULT NULL,
            class_required  TEXT DEFAULT NULL,
            flow_type       TEXT DEFAULT 'bugfix',
            activity_count  INTEGER NOT NULL DEFAULT 0,
            result_file     TEXT DEFAULT NULL,
            created_at      TEXT NOT NULL,
            updated_at      TEXT NOT NULL,
            requirement_path TEXT DEFAULT NULL,
            parent_id       INTEGER REFERENCES tasks(id),
            requirement_id  INTEGER REFERENCES requirements(id)
        )
    """)

    # Copy data — map task_type -> flow_type
    conn.execute("""
        INSERT INTO tasks_new (
            id, title, task_file, project, zone, status,
            blocked_by, assigned_to, created_by, files, progress,
            class_required, flow_type, activity_count, result_file,
            created_at, updated_at, requirement_path, parent_id, requirement_id
        )
        SELECT
            id, title, task_file, project, zone, status,
            blocked_by, assigned_to, created_by, files, progress,
            class_required, task_type, activity_count, result_file,
            created_at, updated_at, requirement_path, parent_id, requirement_id
        FROM tasks
    """)

    conn.execute("DROP TABLE tasks")
    conn.execute("ALTER TABLE tasks_new RENAME TO tasks")

    # Recreate all indexes (original schema had none, but v2 added two)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_tasks_parent ON tasks(parent_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_tasks_requirement ON tasks(requirement_id)"
    )


def _migrate_v4(conn: sqlite3.Connection) -> None:
    """Create the transition_log table — unified audit log for state transitions."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS transition_log (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_id     INTEGER NOT NULL,
            entity_type   TEXT NOT NULL,
            from_status   TEXT,
            to_status     TEXT NOT NULL,
            outcome       TEXT,
            context_path  TEXT,
            triggered_by  TEXT,
            created_at    TEXT NOT NULL
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_transition_entity ON transition_log(entity_id, entity_type)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_transition_created ON transition_log(created_at)"
    )


def _migrate_v5(conn: sqlite3.Connection) -> None:
    """Backfill tasks.requirement_id from tasks.requirement_path."""
    result = conn.execute("""
        UPDATE tasks SET requirement_id = (
            SELECT r.id FROM requirements r
            WHERE r.file_path = tasks.requirement_path
        )
        WHERE requirement_path IS NOT NULL
          AND requirement_id IS NULL
    """)
    backfilled = result.rowcount

    # Count orphans: requirement_path set but no matching requirement
    orphan_row = conn.execute("""
        SELECT COUNT(*) FROM tasks
        WHERE requirement_path IS NOT NULL
          AND requirement_id IS NULL
    """).fetchone()
    orphans = orphan_row[0] if orphan_row else 0

    log.info(
        "v5 backfill: %d rows linked, %d orphans (requirement_path with no matching requirement)",
        backfilled, orphans,
    )
    if orphans > 0:
        log.warning("v5: %d tasks have requirement_path but no matching requirement row", orphans)


def _migrate_v6(conn: sqlite3.Connection) -> None:
    """Copy task_history and transitions rows into transition_log."""
    # Check if task_history exists and copy
    th_count = 0
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }

    if "task_history" in tables:
        result = conn.execute("""
            INSERT INTO transition_log
                (entity_id, entity_type, from_status, to_status, triggered_by, created_at)
            SELECT task_id, 'task', from_status, to_status, agent, timestamp
            FROM task_history
        """)
        th_count = result.rowcount
        log.info("v6: copied %d rows from task_history into transition_log", th_count)

    # Copy from transitions (if it exists and has rows), deduplicating
    tr_count = 0
    if "transitions" in tables:
        result = conn.execute("""
            INSERT INTO transition_log
                (entity_id, entity_type, from_status, to_status, triggered_by, created_at)
            SELECT task_id, 'task', from_status, to_status, agent, created_at
            FROM transitions
            WHERE NOT EXISTS (
                SELECT 1 FROM transition_log tl
                WHERE tl.entity_id = transitions.task_id
                  AND tl.entity_type = 'task'
                  AND tl.from_status IS transitions.from_status
                  AND tl.to_status = transitions.to_status
                  AND tl.created_at = transitions.created_at
            )
        """)
        tr_count = result.rowcount
        log.info("v6: copied %d rows from transitions into transition_log (deduplicated)", tr_count)

    log.info("v6 totals: %d from task_history + %d from transitions", th_count, tr_count)


def _migrate_v7(conn: sqlite3.Connection) -> None:
    """Drop the old task_history and transitions audit tables."""
    conn.execute("DROP TABLE IF EXISTS task_history")
    conn.execute("DROP TABLE IF EXISTS transitions")
    log.info("v7: dropped task_history and transitions tables")


def _migrate_v8(conn: sqlite3.Connection) -> None:
    """Create the backlog table — pre-triage items before they become requirements or tasks."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS backlog (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path   TEXT UNIQUE NOT NULL,
            type        TEXT NOT NULL,
            title       TEXT NOT NULL,
            priority    TEXT DEFAULT 'unset',
            status      TEXT DEFAULT 'open',
            source      TEXT,
            promoted_to TEXT,
            created_by  TEXT,
            created_at  TEXT NOT NULL,
            updated_at  TEXT NOT NULL
        )
    """)
    log.info("v8: created backlog table")


def _migrate_v9(conn: sqlite3.Connection) -> None:
    """Create the task_comments table for mid-flight context injection."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS task_comments (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id     INTEGER NOT NULL REFERENCES tasks(id),
            agent_name  TEXT NOT NULL,
            phase       TEXT,
            comment     TEXT NOT NULL,
            files_read  TEXT,
            created_at  TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_comments_task ON task_comments(task_id)")
    log.info("v9: created task_comments table")


def _migrate_v10(conn: sqlite3.Connection) -> None:
    """Mark task_type->flow_type migration complete.

    The actual fix is in application code: all INSERT/SELECT now reference
    flow_type instead of task_type. The orphan task_type column is harmless
    and SQLite can't DROP COLUMN inside a transaction with FK constraints.
    """
    log.info("v10: task_type->flow_type references fixed in application code")


def _migrate_v11(conn: sqlite3.Connection) -> None:
    """Create intel_docs and intel_links tables — queryable index over .work/intel/."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS intel_docs (
            slug         TEXT PRIMARY KEY,
            doc_path     TEXT NOT NULL,
            tags         TEXT DEFAULT '[]',
            description  TEXT DEFAULT '',
            created_by   TEXT,
            created_at   TEXT NOT NULL,
            updated_at   TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS intel_links (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            intel_slug   TEXT NOT NULL REFERENCES intel_docs(slug),
            entity_type  TEXT NOT NULL,
            entity_id    INTEGER NOT NULL,
            UNIQUE(intel_slug, entity_type, entity_id)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_intel_links_slug ON intel_links(intel_slug)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_intel_links_entity ON intel_links(entity_type, entity_id)")
    log.info("v11: created intel_docs and intel_links tables")


def _migrate_v12(conn: sqlite3.Connection) -> None:
    """Add flow_hint to backlog — lets agents know which DAG to use when promoting."""
    try:
        conn.execute("ALTER TABLE backlog ADD COLUMN flow_hint TEXT DEFAULT NULL")
    except sqlite3.OperationalError:
        pass  # column already exists (re-run safe)
    log.info("v12: added flow_hint column to backlog table")


def _migrate_v13(conn: sqlite3.Connection) -> None:
    """Add promoted_by to backlog — records which agent promoted the item."""
    try:
        conn.execute("ALTER TABLE backlog ADD COLUMN promoted_by TEXT DEFAULT NULL")
    except sqlite3.OperationalError:
        pass  # column already exists (re-run safe)
    log.info("v13: added promoted_by column to backlog table")


def _migrate_v14(conn: sqlite3.Connection) -> None:
    """Add msg_type to messages — typed message taxonomy (backlog #66).

    Valid types: order, sitrep, query, response, alert, system.
    Default NULL for backward compat — existing untyped messages stay untyped.
    """
    try:
        conn.execute("ALTER TABLE messages ADD COLUMN msg_type TEXT DEFAULT NULL")
    except sqlite3.OperationalError:
        pass  # column already exists (re-run safe)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_msg_type ON messages(msg_type)")
    log.info("v14: added msg_type column and index to messages table")


# Ordered list of (version, description, callable) tuples.
# Each callable receives a sqlite3.Connection and runs DDL/DML for that version.
_MIGRATIONS: list[tuple[int, str, Any]] = [
    (1, "Add parent_id and flow_type to requirements", _migrate_v1),
    (2, "Add parent_id and requirement_id to tasks", _migrate_v2),
    (3, "Rename tasks.task_type to tasks.flow_type", _migrate_v3),
    (4, "Create transition_log table", _migrate_v4),
    (5, "Backfill requirement_id from requirement_path", _migrate_v5),
    (6, "Migrate task_history and transitions into transition_log", _migrate_v6),
    (7, "Drop task_history and transitions tables", _migrate_v7),
    (8, "Create backlog table", _migrate_v8),
    (9, "Create task_comments table", _migrate_v9),
    (10, "Drop orphan task_type column from tasks", _migrate_v10),
    (11, "Create intel_docs and intel_links tables", _migrate_v11),
    (12, "Add flow_hint column to backlog table", _migrate_v12),
    (13, "Add promoted_by column to backlog table", _migrate_v13),
    (14, "Add msg_type column to messages table", _migrate_v14),
]


def _get_current_schema_version(conn: sqlite3.Connection) -> int:
    """Return the highest applied schema version, or 0 if no migrations yet."""
    row = conn.execute(
        "SELECT MAX(version) FROM schema_version"
    ).fetchone()
    return row[0] if row[0] is not None else 0


def _run_migrations(conn: sqlite3.Connection) -> None:
    """Apply all pending versioned migrations in order.

    Each migration runs in its own transaction. On failure the single
    migration is rolled back and the error propagates — later migrations
    are skipped so the DB stays at the last successful version.
    """
    if not _MIGRATIONS:
        return

    current = _get_current_schema_version(conn)

    for version, description, migrate_fn in sorted(_MIGRATIONS):
        if version <= current:
            continue
        try:
            # Each migration gets its own transaction
            conn.execute("BEGIN")
            migrate_fn(conn)
            conn.execute(
                "INSERT INTO schema_version (version, applied_at, description) "
                "VALUES (?, ?, ?)",
                (version, now_iso(), description),
            )
            conn.execute("COMMIT")
            log.info("Applied schema migration v%d: %s", version, description)
        except Exception:
            conn.execute("ROLLBACK")
            log.exception("Schema migration v%d failed, rolled back", version)
            raise


def _migrate(conn: sqlite3.Connection) -> None:
    """Add columns that may be missing in older databases."""
    # Agents table migrations
    cursor = conn.execute("PRAGMA table_info(agents)")
    agent_cols = {row["name"] for row in cursor.fetchall()}
    for col, typedef in [
        ("hp_turn_input", "INTEGER DEFAULT NULL"),
        ("hp_turn_output", "INTEGER DEFAULT NULL"),
        ("hp_alerts_fired", "TEXT DEFAULT NULL"),
        ("pid", "INTEGER DEFAULT NULL"),
        ("crew", "TEXT DEFAULT NULL"),
        ("session_id", "TEXT DEFAULT NULL"),
        ("rss_bytes", "INTEGER DEFAULT NULL"),
        ("scope_mode", "TEXT DEFAULT 'project'"),
    ]:
        if col not in agent_cols:
            conn.execute(f"ALTER TABLE agents ADD COLUMN {col} {typedef}")

    # Tasks table migrations
    cursor = conn.execute("PRAGMA table_info(tasks)")
    task_cols = {row["name"] for row in cursor.fetchall()}
    for col, typedef in [
        ("class_required", "TEXT DEFAULT NULL"),
        # task_type was renamed to flow_type in v3; only add task_type on
        # pre-v3 databases where flow_type doesn't exist yet.
        ("task_type", "TEXT DEFAULT 'bugfix'"),
        ("requirement_path", "TEXT DEFAULT NULL"),
    ]:
        if col not in task_cols:
            # Skip re-adding task_type if v3 already renamed it to flow_type
            if col == "task_type" and "flow_type" in task_cols:
                continue
            conn.execute(f"ALTER TABLE tasks ADD COLUMN {col} {typedef}")

    conn.commit()
