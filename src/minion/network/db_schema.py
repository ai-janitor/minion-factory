"""Network DB schema SQL + migration for 16 new agent columns.

Purpose: Define the full network coordinator DB schema and provide a migration
         path from the current 7-column agents table to the expanded 23-column
         version with identity, environment, trust, and routing fields.
Rationale: The schema was previously inline in server.py's _init_server_db.
           Extracting it allows: (a) the migration to be tested independently,
           (b) other modules to reference column names, (c) future schema changes
           to be versioned here.
Responsibility: Schema DDL, migration SQL, schema version tracking.
Organization: SCHEMA_SQL constant for fresh installs, MIGRATION_SQL for upgrades,
              init_db() and migrate_db() functions.

Implementation order: 1st (foundation — must exist before any DB reads/writes).
"""

from __future__ import annotations

import sqlite3

# --- Full schema for fresh installs ---

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS agents (
    -- Core (existing 7 columns)
    name                  TEXT PRIMARY KEY,
    agent_class           TEXT NOT NULL DEFAULT 'coder',
    host                  TEXT,
    project_path          TEXT,
    machine_id            TEXT,
    registered_at         TEXT,
    last_seen             TEXT,

    -- Identity & Capability (new)
    model                 TEXT,
    capabilities          TEXT,            -- JSON array: ["code","build","test"]
    crew_name             TEXT,
    local_lead            TEXT,

    -- Environment (reported at registration)
    machine_specs         TEXT,            -- JSON: {"gpu":"A100","ram_gb":64}
    runtimes              TEXT,            -- JSON array: ["python3.13","node22"]
    os_platform           TEXT,            -- e.g. "darwin-arm64"

    -- Trust & History (updated per heartbeat)
    session_count         INTEGER,
    compaction_count      INTEGER,
    crash_rate            REAL,
    total_input_tokens    INTEGER,
    total_output_tokens   INTEGER,
    last_task_completed_at TEXT,

    -- Routing
    autonomous_delegation INTEGER DEFAULT 0,
    heartbeat_latency_ms  INTEGER
);

CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    from_agent  TEXT NOT NULL,
    to_agent    TEXT NOT NULL,
    content     TEXT NOT NULL,
    timestamp   TEXT NOT NULL,
    read_flag   INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_msg_to_unread ON messages(to_agent, read_flag);
"""

# --- Migration SQL for existing DBs (add columns if missing) ---
# Uses ALTER TABLE ADD COLUMN which is safe — SQLite ignores if column exists (via try/except).

MIGRATION_COLUMNS = [
    # (column_name, column_def)
    ("model", "TEXT"),
    ("capabilities", "TEXT"),
    ("crew_name", "TEXT"),
    ("local_lead", "TEXT"),
    ("machine_specs", "TEXT"),
    ("runtimes", "TEXT"),
    ("os_platform", "TEXT"),
    ("session_count", "INTEGER"),
    ("compaction_count", "INTEGER"),
    ("crash_rate", "REAL"),
    ("total_input_tokens", "INTEGER"),
    ("total_output_tokens", "INTEGER"),
    ("last_task_completed_at", "TEXT"),
    ("autonomous_delegation", "INTEGER DEFAULT 0"),
    ("heartbeat_latency_ms", "INTEGER"),
]


def init_db(db_path: str) -> None:
    """Initialize the network DB with the full schema.

    Safe to call on existing DBs — uses CREATE TABLE IF NOT EXISTS.
    For existing DBs that predate the expanded schema, call migrate_db() after.
    """
    # PSEUDO: conn = sqlite3.connect(db_path)
    # PSEUDO: conn.execute("PRAGMA journal_mode=WAL")
    # PSEUDO: conn.executescript(SCHEMA_SQL)
    # PSEUDO: conn.commit(); conn.close()
    conn = sqlite3.connect(db_path, timeout=5)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()


def migrate_db(db_path: str) -> list[str]:
    """Add new columns to an existing agents table (idempotent).

    Returns list of columns that were actually added (empty if already up-to-date).
    Uses ALTER TABLE ADD COLUMN in a try/except per column — SQLite raises
    'duplicate column name' if it already exists, which we catch and skip.
    """
    # PSEUDO: conn = sqlite3.connect(db_path)
    # PSEUDO: added = []
    # PSEUDO: for (col_name, col_def) in MIGRATION_COLUMNS:
    #   try: conn.execute(f"ALTER TABLE agents ADD COLUMN {col_name} {col_def}")
    #   except sqlite3.OperationalError: pass  # column already exists
    # PSEUDO: conn.commit(); conn.close(); return added
    conn = sqlite3.connect(db_path, timeout=5)
    added = []
    for col_name, col_def in MIGRATION_COLUMNS:
        try:
            conn.execute(f"ALTER TABLE agents ADD COLUMN {col_name} {col_def}")
            added.append(col_name)
        except sqlite3.OperationalError:
            pass  # column already exists
    conn.commit()
    conn.close()
    return added
