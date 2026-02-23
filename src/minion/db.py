"""SQLite database — unified schema, connection, and helpers.

Merges commsv2/db.py (comms tables) + minion-tasks/db.py (DAG tables)
into a single schema. One DB file, one connection helper.
"""

from __future__ import annotations

import datetime
import logging
import os
import sqlite3
from typing import Any

log = logging.getLogger(__name__)

from minion.defaults import resolve_db_path, resolve_docs_dir

# ---------------------------------------------------------------------------
# Paths — lazy resolution so env vars and cwd are read at call time, not import
# ---------------------------------------------------------------------------

_db_path: str | None = None
DOCS_DIR = resolve_docs_dir()


def _get_db_path() -> str:
    global _db_path
    if _db_path is None:
        _db_path = resolve_db_path()
    return _db_path


def reset_db_path() -> None:
    """Clear cached DB path so next access re-resolves from env/cwd."""
    global _db_path
    _db_path = None


def get_runtime_dir() -> str:
    return os.path.dirname(_get_db_path())


# Lazy module-level attributes — fs.py imports RUNTIME_DIR, comms.py uses DB_PATH
def __getattr__(name: str) -> Any:
    if name == "DB_PATH":
        return _get_db_path()
    if name == "RUNTIME_DIR":
        return get_runtime_dir()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------


def get_db() -> sqlite3.Connection:
    """Open a WAL-mode connection with row factory."""
    db_path = _get_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ---------------------------------------------------------------------------
# Schema — comms tables
# ---------------------------------------------------------------------------

_COMMS_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS agents (
    name                TEXT PRIMARY KEY,
    agent_class         TEXT NOT NULL DEFAULT 'coder',
    model               TEXT DEFAULT NULL,
    registered_at       TEXT,
    last_seen           TEXT,
    last_inbox_check    TEXT,
    context_updated_at  TEXT DEFAULT NULL,
    description         TEXT DEFAULT NULL,
    status              TEXT DEFAULT 'waiting for work',
    context_summary     TEXT DEFAULT NULL,
    transport           TEXT DEFAULT 'terminal',
    current_zone        TEXT DEFAULT NULL,
    current_role        TEXT DEFAULT NULL,
    spawned_from        TEXT DEFAULT NULL,
    hp_input_tokens     INTEGER DEFAULT NULL,
    hp_output_tokens    INTEGER DEFAULT NULL,
    hp_tokens_limit     INTEGER DEFAULT NULL,
    hp_turn_input       INTEGER DEFAULT NULL,
    hp_turn_output      INTEGER DEFAULT NULL,
    hp_updated_at       TEXT DEFAULT NULL,
    files_read          TEXT DEFAULT NULL,
    hp_alerts_fired     TEXT DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    from_agent      TEXT,
    to_agent        TEXT,
    content_file    TEXT,
    timestamp       TEXT,
    read_flag       INTEGER DEFAULT 0,
    is_cc           INTEGER DEFAULT 0,
    cc_original_to  TEXT DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS broadcast_reads (
    agent_name  TEXT,
    message_id  INTEGER,
    PRIMARY KEY (agent_name, message_id)
);

CREATE TABLE IF NOT EXISTS battle_plan (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    set_by      TEXT NOT NULL,
    plan_file   TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'active',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS raid_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_name  TEXT NOT NULL,
    entry_file  TEXT NOT NULL,
    priority    TEXT NOT NULL DEFAULT 'normal',
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS file_claims (
    file_path   TEXT PRIMARY KEY,
    agent_name  TEXT NOT NULL,
    claimed_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS file_waitlist (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path   TEXT NOT NULL,
    agent_name  TEXT NOT NULL,
    added_at    TEXT NOT NULL,
    UNIQUE(file_path, agent_name)
);

CREATE TABLE IF NOT EXISTS fenix_down_records (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_name  TEXT NOT NULL,
    files       TEXT NOT NULL DEFAULT '[]',
    manifest    TEXT DEFAULT '',
    consumed    INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS flags (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    set_by      TEXT NOT NULL,
    set_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_retire (
    agent_name  TEXT PRIMARY KEY,
    set_at      TEXT NOT NULL,
    set_by      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS invocation_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_name      TEXT NOT NULL,
    pid             INTEGER NOT NULL,
    model           TEXT,
    generation      INTEGER,
    rss_bytes       INTEGER,
    input_tokens    INTEGER,
    output_tokens   INTEGER,
    exit_code       INTEGER,
    timed_out       INTEGER DEFAULT 0,
    interrupted     INTEGER DEFAULT 0,
    compacted       INTEGER DEFAULT 0,
    started_at      TEXT NOT NULL,
    ended_at        TEXT
);

CREATE TABLE IF NOT EXISTS compaction_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_name      TEXT NOT NULL,
    model           TEXT,
    pid             INTEGER,
    rss_pre_bytes   INTEGER,
    rss_post_bytes  INTEGER,
    tokens_pre      INTEGER,
    tokens_post     INTEGER,
    generation      INTEGER,
    compacted_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_interrupt (
    agent_name  TEXT PRIMARY KEY,
    set_at      TEXT NOT NULL,
    set_by      TEXT NOT NULL
);
"""

# ---------------------------------------------------------------------------
# Schema — task tables (unified from commsv2 + minion-tasks)
# ---------------------------------------------------------------------------

_REQUIREMENTS_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS requirements (
    id          INTEGER PRIMARY KEY,
    file_path   TEXT UNIQUE NOT NULL,
    origin      TEXT NOT NULL,
    stage       TEXT NOT NULL DEFAULT 'seed',
    created_by  TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

_TASKS_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS projects (
    id          TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    status      TEXT NOT NULL DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS tasks (
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
    task_type       TEXT DEFAULT 'bugfix',
    activity_count  INTEGER NOT NULL DEFAULT 0,
    result_file     TEXT DEFAULT NULL,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

"""


# ---------------------------------------------------------------------------
# Schema versioning — tracks which migrations have been applied
# ---------------------------------------------------------------------------

_SCHEMA_VERSION_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER PRIMARY KEY,
    applied_at  TEXT NOT NULL,
    description TEXT
);
"""

# ---------------------------------------------------------------------------
# Migration helpers
# ---------------------------------------------------------------------------


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    """Return the set of column names for *table*."""
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {row[1] if isinstance(row, tuple) else row["name"] for row in rows}


# ---------------------------------------------------------------------------
# Versioned migrations (v1–v4)
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


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------


def init_db() -> None:
    """Create all tables if they don't exist, then run pending migrations."""
    conn = get_db()
    conn.executescript(_COMMS_SCHEMA_SQL)
    conn.executescript(_TASKS_SCHEMA_SQL)
    conn.executescript(_REQUIREMENTS_SCHEMA_SQL)
    conn.executescript(_SCHEMA_VERSION_SQL)
    _migrate(conn)
    _run_migrations(conn)
    conn.close()


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
    ]:
        if col not in agent_cols:
            conn.execute(f"ALTER TABLE agents ADD COLUMN {col} {typedef}")

    # Tasks table migrations
    cursor = conn.execute("PRAGMA table_info(tasks)")
    task_cols = {row["name"] for row in cursor.fetchall()}
    for col, typedef in [
        ("class_required", "TEXT DEFAULT NULL"),
        ("task_type", "TEXT DEFAULT 'bugfix'"),
        ("requirement_path", "TEXT DEFAULT NULL"),
    ]:
        if col not in task_cols:
            conn.execute(f"ALTER TABLE tasks ADD COLUMN {col} {typedef}")

    conn.commit()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def now_iso() -> str:
    return datetime.datetime.now().isoformat()


def get_lead(cursor: sqlite3.Cursor) -> str | None:
    """Return the name of the first registered lead agent, or None."""
    cursor.execute("SELECT name FROM agents WHERE agent_class = 'lead' LIMIT 1")
    row = cursor.fetchone()
    return row[0] if row else None


def hp_summary(
    input_tokens: int | None,
    output_tokens: int | None,
    limit: int | None,
    turn_input: int | None = None,
    turn_output: int | None = None,
) -> str:
    """Human-readable HP string from daemon-observed token counts.

    Uses per-turn values for HP% when available (actual context pressure),
    falls back to cumulative. Shows cumulative as session total.
    """
    if not limit:
        return "HP unknown"

    if turn_input is not None:
        used = turn_input
    else:
        used = min(input_tokens or 0, limit)

    if used == 0:
        return "HP unknown"

    pct_used = used / limit * 100
    hp_pct = max(0.0, 100 - pct_used)
    status = "Healthy" if hp_pct > 50 else ("Wounded" if hp_pct > 25 else "CRITICAL")

    return f"{hp_pct:.0f}% HP [{used // 1000}k/{limit // 1000}k] — {status}"


def enrich_agent_row(row: sqlite3.Row, now: datetime.datetime) -> dict[str, Any]:
    """Add HP, staleness, and last_seen_mins_ago to an agent row dict."""
    # Import here to avoid circular dependency with auth
    from minion.auth import CLASS_STALENESS_SECONDS

    a: dict[str, Any] = dict(row)

    a["hp"] = hp_summary(
        a.get("hp_input_tokens"), a.get("hp_output_tokens"), a.get("hp_tokens_limit"),
        turn_input=a.get("hp_turn_input"), turn_output=a.get("hp_turn_output"),
    )

    threshold = CLASS_STALENESS_SECONDS.get(a.get("agent_class", ""))
    stale = False
    if threshold and a.get("context_updated_at"):
        try:
            updated = datetime.datetime.fromisoformat(a["context_updated_at"])
            stale = (now - updated).total_seconds() > threshold
        except ValueError:
            import sys
            print(f"WARNING: corrupt context_updated_at for {a.get('name')}: {a['context_updated_at']!r}", file=sys.stderr)
    elif threshold and not a.get("context_updated_at"):
        stale = True
    a["context_stale"] = stale

    if a.get("last_seen"):
        try:
            ls = datetime.datetime.fromisoformat(a["last_seen"])
            a["last_seen_mins_ago"] = int((now - ls).total_seconds() // 60)
        except ValueError:
            import sys
            print(f"WARNING: corrupt last_seen for {a.get('name')}: {a['last_seen']!r}", file=sys.stderr)

    return a


def staleness_check(cursor: sqlite3.Cursor, agent_name: str) -> tuple[bool, str]:
    """Check if agent's context is stale per class threshold.

    Returns (is_stale, message). is_stale=True means BLOCKED.
    """
    from minion.auth import CLASS_STALENESS_SECONDS

    cursor.execute(
        "SELECT agent_class, context_updated_at FROM agents WHERE name = ?",
        (agent_name,),
    )
    row = cursor.fetchone()
    if not row:
        return False, ""

    agent_class: str = row["agent_class"]
    context_updated_at: str | None = row["context_updated_at"]

    threshold = CLASS_STALENESS_SECONDS.get(agent_class)
    if threshold is None:
        return False, ""

    if not context_updated_at:
        return (
            True,
            f"BLOCKED: Context not set. Call set-context before sending. "
            f"({agent_class} threshold: {threshold // 60} min)",
        )

    try:
        updated = datetime.datetime.fromisoformat(context_updated_at)
    except ValueError:
        import sys
        print(f"WARNING: corrupt context_updated_at for {agent_name}: {context_updated_at!r}", file=sys.stderr)
        return False, ""

    age_seconds = (datetime.datetime.now() - updated).total_seconds()
    if age_seconds > threshold:
        mins = int(age_seconds // 60)
        return (
            True,
            f"BLOCKED: Context stale ({mins}m old, threshold {threshold // 60}m for {agent_class}). "
            f"Call set-context to update your metrics before sending.",
        )

    return False, ""


def load_onboarding(agent_class: str) -> str:
    """Load protocol + class profile docs from runtime directory."""
    parts: list[str] = []

    protocol_path = os.path.join(DOCS_DIR, "protocol-common.md")
    if os.path.exists(protocol_path):
        with open(protocol_path) as f:
            parts.append(f.read())

    if agent_class:
        class_path = os.path.join(DOCS_DIR, f"protocol-{agent_class}.md")
        if os.path.exists(class_path):
            with open(class_path) as f:
                parts.append(f.read())

    return "\n\n---\n\n".join(parts) if parts else ""


def scan_triggers(message: str) -> list[str]:
    """Return trigger words found in message text.

    Only matches deliberate !!trigger!! pattern — not casual mentions.
    """
    from minion.auth import TRIGGER_WORDS
    lower = message.lower()
    return [word for word in TRIGGER_WORDS if f"!!{word}!!" in lower]


def format_trigger_codebook() -> str:
    """Format the trigger word codebook for display."""
    from minion.auth import TRIGGER_WORDS
    lines = ["## Trigger Words (Brevity Codes)", ""]
    lines.append("Wrap in `!!` to activate: `!!stand_down!!`. Bare mentions are ignored.")
    lines.append("")
    lines.append("| Code | Meaning |")
    lines.append("|---|---|")
    for word, meaning in TRIGGER_WORDS.items():
        lines.append(f"| `{word}` | {meaning} |")
    return "\n".join(lines)
