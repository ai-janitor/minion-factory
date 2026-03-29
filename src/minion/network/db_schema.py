"""Network DB schema SQL + migration for composite PK and 16 new agent columns.

Purpose: Define the full network coordinator DB schema and provide a migration
         path from the old name-only PK to composite (machine_id, project_path, name)
         PK, plus the expanded column set with identity, environment, trust, routing.
Rationale: The schema was previously inline in server.py's _init_server_db.
           Extracting it allows: (a) the migration to be tested independently,
           (b) other modules to reference column names, (c) future schema changes
           to be versioned here. The composite PK prevents agent name collisions
           across machines/projects in the network registry.
Responsibility: Schema DDL, migration SQL, schema version tracking, PK migration.
Organization: SCHEMA_SQL constant for fresh installs, MIGRATION_COLUMNS for column
              additions, migrate_db() for column upgrades, migrate_to_composite_pk()
              for the destructive PK change (create-copy-swap pattern).

Implementation order: 1st (foundation — must exist before any DB reads/writes).
"""

from __future__ import annotations

import sqlite3

from minion.db.connection import connect as _connect

# --- Full schema for fresh installs ---

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS agents (
    -- Core identity (composite PK: machine_id/project_path/name)
    name                  TEXT NOT NULL,
    agent_class           TEXT NOT NULL DEFAULT 'coder',
    host                  TEXT,
    project_path          TEXT NOT NULL DEFAULT 'unknown',
    machine_id            TEXT NOT NULL DEFAULT 'unknown',
    registered_at         TEXT,
    last_seen             TEXT,

    -- Stable durable identity — survives restarts, rejoin, channel changes
    agent_uuid            TEXT,

    -- Identity & Capability
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
    heartbeat_latency_ms  INTEGER,

    PRIMARY KEY (machine_id, project_path, name)
);

CREATE TABLE IF NOT EXISTS messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    from_agent      TEXT NOT NULL,
    to_agent        TEXT NOT NULL,
    from_agent_uuid TEXT,          -- stable identity for routing/history
    to_agent_uuid   TEXT,          -- stable identity for routing/history
    content         TEXT NOT NULL,
    timestamp       TEXT NOT NULL,
    read_flag       INTEGER DEFAULT 0,
    channel_id      INTEGER REFERENCES channels(id)  -- NULL = direct message
);

CREATE INDEX IF NOT EXISTS idx_msg_to_unread ON messages(to_agent, read_flag);

-- Channels: first-class collaboration scopes (projects/topics agents join)
CREATE TABLE IF NOT EXISTS channels (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,       -- e.g. "llama-metal"
    created_at  TEXT NOT NULL,
    description TEXT,
    created_by  TEXT,                       -- agent name that created the channel
    git_remote  TEXT,                       -- canonical git remote URL (e.g., github.com/org/repo.git)
    git_branch  TEXT                        -- default branch (e.g., "main")
);

-- Channel membership: which agents belong to which channels
CREATE TABLE IF NOT EXISTS channel_members (
    channel_id  INTEGER NOT NULL REFERENCES channels(id),
    agent_name  TEXT NOT NULL,
    machine_id  TEXT NOT NULL DEFAULT 'unknown',
    joined_at   TEXT NOT NULL,
    role        TEXT DEFAULT 'member',      -- 'member' or 'lead'
    PRIMARY KEY (channel_id, agent_name, machine_id)
);

CREATE INDEX IF NOT EXISTS idx_channel_members_agent ON channel_members(agent_name);
CREATE INDEX IF NOT EXISTS idx_msg_channel_unread ON messages(channel_id, to_agent, read_flag);
"""

# --- Migration SQL for existing DBs (add columns if missing) ---
# Uses ALTER TABLE ADD COLUMN which is safe — SQLite ignores if column exists (via try/except).

MIGRATION_COLUMNS = [
    # (column_name, column_def)
    ("agent_uuid", "TEXT"),  # Stable durable identity — survives restarts, rejoin, channel changes
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
    conn = _connect(db_path)
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()


def _has_composite_pk(conn: sqlite3.Connection) -> bool:
    """Check if the agents table already uses the composite primary key.

    Inspects the table_info pragma to determine if name is the sole PK
    (old schema) or if machine_id, project_path, name form a composite PK.
    """
    # PSEUDO: cursor = conn.execute("PRAGMA table_info(agents)")
    # PSEUDO: pk_cols = [row for row in cursor if row["pk"] > 0]
    # PSEUDO: return len(pk_cols) == 3 (composite) vs 1 (name-only)
    rows = conn.execute("PRAGMA table_info(agents)").fetchall()
    pk_cols = [r for r in rows if r[5] > 0]  # column index 5 is 'pk'
    return len(pk_cols) >= 3


def migrate_to_composite_pk(db_path: str) -> dict:
    """Migrate agents table from name-only PK to composite PK (machine_id, project_path, name).

    Uses create-copy-swap pattern:
    1. Check if already migrated (idempotent)
    2. Create agents_new with composite PK
    3. Copy all rows, backfilling NULL machine_id/project_path with 'unknown'
    4. Drop old table, rename new table
    5. Recreate indexes

    Returns dict with migration status and row count.
    """
    # PSEUDO: conn = sqlite3.connect(db_path)
    # PSEUDO: if _has_composite_pk(conn): return {"status": "already_migrated"}
    # PSEUDO: get column list from PRAGMA table_info(agents)
    # PSEUDO: CREATE TABLE agents_new with composite PK (same columns)
    # PSEUDO: INSERT INTO agents_new SELECT ... COALESCE(machine_id, 'unknown'), COALESCE(project_path, 'unknown') ...
    # PSEUDO: DROP TABLE agents; ALTER TABLE agents_new RENAME TO agents
    # PSEUDO: return {"status": "migrated", "rows": count}
    conn = _connect(db_path)

    if _has_composite_pk(conn):
        conn.close()
        return {"status": "already_migrated"}

    # Get existing column names
    cols_info = conn.execute("PRAGMA table_info(agents)").fetchall()
    col_names = [r[1] for r in cols_info]

    # Build the new table DDL from SCHEMA_SQL (which has the composite PK)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS agents_new (
            name                  TEXT NOT NULL,
            agent_class           TEXT NOT NULL DEFAULT 'coder',
            host                  TEXT,
            project_path          TEXT NOT NULL DEFAULT 'unknown',
            machine_id            TEXT NOT NULL DEFAULT 'unknown',
            registered_at         TEXT,
            last_seen             TEXT,
            model                 TEXT,
            capabilities          TEXT,
            crew_name             TEXT,
            local_lead            TEXT,
            machine_specs         TEXT,
            runtimes              TEXT,
            os_platform           TEXT,
            session_count         INTEGER,
            compaction_count      INTEGER,
            crash_rate            REAL,
            total_input_tokens    INTEGER,
            total_output_tokens   INTEGER,
            last_task_completed_at TEXT,
            autonomous_delegation INTEGER DEFAULT 0,
            heartbeat_latency_ms  INTEGER,
            PRIMARY KEY (machine_id, project_path, name)
        );
    """)

    # Copy data, backfilling NULLs for machine_id and project_path
    # Build SELECT list: for each column in agents_new, pull from old table
    # with COALESCE for machine_id and project_path
    new_cols_info = conn.execute("PRAGMA table_info(agents_new)").fetchall()
    new_col_names = [r[1] for r in new_cols_info]

    select_parts = []
    for col in new_col_names:
        if col == "machine_id":
            select_parts.append("COALESCE(machine_id, 'unknown')")
        elif col == "project_path":
            select_parts.append("COALESCE(project_path, 'unknown')")
        elif col in col_names:
            select_parts.append(col)
        else:
            select_parts.append("NULL")

    insert_sql = f"INSERT OR IGNORE INTO agents_new ({', '.join(new_col_names)}) SELECT {', '.join(select_parts)} FROM agents"
    conn.execute(insert_sql)

    row_count = conn.execute("SELECT COUNT(*) FROM agents_new").fetchone()[0]

    conn.execute("DROP TABLE agents")
    conn.execute("ALTER TABLE agents_new RENAME TO agents")
    conn.commit()
    conn.close()
    return {"status": "migrated", "rows": row_count}


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
    conn = _connect(db_path)
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


def migrate_channels(db_path: str) -> dict:
    """Add channels tables and seed from existing project_path data (idempotent).

    1. Create channels + channel_members tables (IF NOT EXISTS)
    2. Add channel_id column to messages (if missing)
    3. Seed channels from distinct project_paths in agents table
    4. Auto-join existing agents to their project's channel

    Returns dict with migration status and counts.
    """
    import os
    from datetime import datetime

    conn = _connect(db_path)

    # Create tables (idempotent)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS channels (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL UNIQUE,
            created_at  TEXT NOT NULL,
            description TEXT,
            created_by  TEXT
        );
        CREATE TABLE IF NOT EXISTS channel_members (
            channel_id  INTEGER NOT NULL REFERENCES channels(id),
            agent_name  TEXT NOT NULL,
            machine_id  TEXT NOT NULL DEFAULT 'unknown',
            joined_at   TEXT NOT NULL,
            role        TEXT DEFAULT 'member',
            PRIMARY KEY (channel_id, agent_name, machine_id)
        );
        CREATE INDEX IF NOT EXISTS idx_channel_members_agent ON channel_members(agent_name);
    """)

    # Add channel_id to messages if missing
    try:
        conn.execute("ALTER TABLE messages ADD COLUMN channel_id INTEGER REFERENCES channels(id)")
    except sqlite3.OperationalError:
        pass  # column already exists

    # Create index for channel-scoped message queries
    conn.execute("CREATE INDEX IF NOT EXISTS idx_msg_channel_unread ON messages(channel_id, to_agent, read_flag)")

    # Seed channels from existing agent project_paths
    now = datetime.now().isoformat()
    rows = conn.execute(
        "SELECT DISTINCT project_path FROM agents WHERE project_path IS NOT NULL AND project_path != 'unknown'"
    ).fetchall()

    channels_created = 0
    members_added = 0

    for row in rows:
        project_path = row[0]
        channel_name = os.path.basename(project_path.rstrip("/"))
        if not channel_name:
            continue

        # Create channel if it doesn't exist
        existing = conn.execute("SELECT id FROM channels WHERE name = ?", (channel_name,)).fetchone()
        if not existing:
            conn.execute(
                "INSERT INTO channels (name, created_at, description, created_by) VALUES (?, ?, ?, ?)",
                (channel_name, now, f"Auto-created from project_path: {project_path}", "migration"),
            )
            channels_created += 1

        # Get channel id
        channel_id = conn.execute("SELECT id FROM channels WHERE name = ?", (channel_name,)).fetchone()[0]

        # Auto-join agents with this project_path
        agents = conn.execute(
            "SELECT name, machine_id, agent_class, registered_at FROM agents WHERE project_path = ?",
            (project_path,),
        ).fetchall()

        for agent in agents:
            role = "lead" if agent["agent_class"] == "lead" else "member"
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO channel_members (channel_id, agent_name, machine_id, joined_at, role) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (channel_id, agent["name"], agent["machine_id"], agent["registered_at"] or now, role),
                )
                members_added += 1
            except sqlite3.IntegrityError:
                pass  # already a member

    conn.commit()
    conn.close()
    return {"status": "migrated", "channels_created": channels_created, "members_added": members_added}


def migrate_channel_git(db_path: str) -> None:
    """Add git_remote and git_branch columns to channels table (idempotent)."""
    conn = _connect(db_path)
    for col in ("git_remote TEXT", "git_branch TEXT"):
        try:
            conn.execute(f"ALTER TABLE channels ADD COLUMN {col}")
        except sqlite3.OperationalError:
            pass
    conn.commit()
    conn.close()


def migrate_message_uuids(db_path: str) -> None:
    """Add from_agent_uuid and to_agent_uuid columns to messages table (idempotent)."""
    conn = _connect(db_path)
    for col in ("from_agent_uuid", "to_agent_uuid"):
        try:
            conn.execute(f"ALTER TABLE messages ADD COLUMN {col} TEXT")
        except sqlite3.OperationalError:
            pass  # column already exists
    conn.commit()
    conn.close()


def migrate_agent_uuids(db_path: str) -> dict:
    """Backfill agent_uuid for existing agents that don't have one (idempotent).

    Generates a stable UUID4 for each agent missing one. The UUID persists
    across restarts and rejoin — it's the durable identity handle.
    """
    import uuid

    conn = _connect(db_path)

    # Add column if missing
    try:
        conn.execute("ALTER TABLE agents ADD COLUMN agent_uuid TEXT")
    except sqlite3.OperationalError:
        pass  # column already exists

    # Backfill any agents missing a UUID
    rows = conn.execute("SELECT name, machine_id FROM agents WHERE agent_uuid IS NULL").fetchall()
    count = 0
    for row in rows:
        conn.execute(
            "UPDATE agents SET agent_uuid = ? WHERE name = ? AND machine_id = ?",
            (str(uuid.uuid4()), row["name"], row["machine_id"]),
        )
        count += 1

    conn.commit()
    conn.close()
    return {"status": "migrated", "uuids_backfilled": count}
