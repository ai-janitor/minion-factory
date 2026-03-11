"""SQL schema definitions for all tables.
Contains the CREATE TABLE statements for comms, tasks, requirements,
schema versioning, and coordinator tables. No runtime logic — just DDL strings.

Purpose: SQL schema definitions for all tables.
Rationale: Extracted into own module for single-responsibility database access.
Responsibility: SQL schema definitions for all tables. NOT responsible for unrelated concerns.
Organization: Standalone functions and/or a single class. See source.

ASSUMPTIONS:
- SQLite is the only backend. All DDL uses SQLite syntax (TEXT for timestamps,
  INTEGER PRIMARY KEY AUTOINCREMENT, CREATE TABLE IF NOT EXISTS).
- Timestamps are stored as ISO-8601 TEXT, not SQLite DATETIME. All readers must
  parse with datetime.fromisoformat(). Timezone is UTC but not always explicit —
  some columns use datetime('now') (UTC) while others use now_iso() (explicit UTC).
- agent.name is a globally unique TEXT primary key — no UUID, no auto-increment.
  Callers must ensure uniqueness before INSERT. Re-registration reuses the same name.
- messages.content_file stores an absolute filesystem path, not the message content
  itself. The file must exist and be readable at that path when the message is consumed.
  If the file is deleted or moved, the message content is lost.
- file_claims uses os.path.abspath() normalized paths as the PRIMARY KEY. All claim
  operations must normalize paths identically or lookups will silently miss.
- The coordinator schema (agents table in ~/.minion/coordinator.db) is a SEPARATE
  database from the project-local agents table. Same table name, different columns,
  different DB file. Do not confuse them.
- tasks.blocked_by is a comma-separated string of task IDs, not a foreign key or
  junction table. Parsing is done by callers with split(',').
- tasks.files and tasks.progress are JSON-encoded TEXT fields. Callers must
  json.loads()/json.dumps() them. NULL means empty, not '[]'.
- Schema migrations (migrations.py) assume forward-only — no rollback support.
  The schema_version table tracks applied migrations monotonically.
"""

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
    hp_alerts_fired     TEXT DEFAULT NULL,
    scope_mode          TEXT DEFAULT 'project'
);

CREATE TABLE IF NOT EXISTS messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    from_agent      TEXT,
    to_agent        TEXT,
    content_file    TEXT,
    timestamp       TEXT,
    read_flag       INTEGER DEFAULT 0,
    is_cc           INTEGER DEFAULT 0,
    cc_original_to  TEXT DEFAULT NULL,
    msg_type        TEXT DEFAULT NULL
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
    checklist_path  TEXT DEFAULT NULL,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

"""

_SCHEMA_VERSION_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER PRIMARY KEY,
    applied_at  TEXT NOT NULL,
    description TEXT
);
"""

_COORDINATOR_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS agents (
    name            TEXT PRIMARY KEY,
    agent_class     TEXT NOT NULL DEFAULT 'coder',
    model           TEXT DEFAULT NULL,
    project_path    TEXT,
    registered_at   TEXT,
    last_seen       TEXT,
    last_active     TEXT,
    description     TEXT DEFAULT NULL,
    status          TEXT DEFAULT 'waiting for work',
    transport       TEXT DEFAULT 'terminal',
    scope_mode      TEXT DEFAULT 'project'
);
"""
