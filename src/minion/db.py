"""SQLite database — unified schema, connection, and helpers.

Merges commsv2/db.py (comms tables) + minion-tasks/db.py (DAG tables)
into a single schema. One DB file, one connection helper.
"""

from __future__ import annotations

import datetime
import os
import sqlite3
from typing import Any

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
"""

# ---------------------------------------------------------------------------
# Schema — task tables (unified from commsv2 + minion-tasks)
# ---------------------------------------------------------------------------

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

CREATE TABLE IF NOT EXISTS task_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id     INTEGER NOT NULL,
    from_status TEXT,
    to_status   TEXT NOT NULL,
    agent       TEXT NOT NULL,
    timestamp   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS transitions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id     TEXT NOT NULL,
    from_status TEXT NOT NULL,
    to_status   TEXT NOT NULL,
    agent       TEXT,
    valid       INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------


def init_db() -> None:
    """Create all tables if they don't exist."""
    conn = get_db()
    conn.executescript(_COMMS_SCHEMA_SQL)
    conn.executescript(_TASKS_SCHEMA_SQL)
    _migrate(conn)
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
    ]:
        if col not in agent_cols:
            conn.execute(f"ALTER TABLE agents ADD COLUMN {col} {typedef}")

    # Tasks table migrations
    cursor = conn.execute("PRAGMA table_info(tasks)")
    task_cols = {row["name"] for row in cursor.fetchall()}
    for col, typedef in [
        ("class_required", "TEXT DEFAULT NULL"),
        ("task_type", "TEXT DEFAULT 'bugfix'"),
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
    """Return trigger words found in message text."""
    from minion.auth import TRIGGER_WORDS
    lower = message.lower()
    return [word for word in TRIGGER_WORDS if word in lower]


def format_trigger_codebook() -> str:
    """Format the trigger word codebook for display."""
    from minion.auth import TRIGGER_WORDS
    lines = ["## Trigger Words (Brevity Codes)", ""]
    lines.append("Short code words for fast coordination. Use in messages — comms recognizes them automatically.")
    lines.append("")
    lines.append("| Code | Meaning |")
    lines.append("|---|---|")
    for word, meaning in TRIGGER_WORDS.items():
        lines.append(f"| `{word}` | {meaning} |")
    return "\n".join(lines)
