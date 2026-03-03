"""Database connection management — path resolution, WAL-mode connections.

Handles lazy path resolution from env vars and cwd, plus the get_db() and
get_coordinator_db() connection factories with WAL mode and row factory.
"""

from __future__ import annotations

import os
import sqlite3

from minion.defaults import resolve_coordinator_db_path, resolve_db_path

# ---------------------------------------------------------------------------
# Paths — lazy resolution so env vars and cwd are read at call time, not import
# ---------------------------------------------------------------------------

_db_path: str | None = None


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


# ---------------------------------------------------------------------------
# Connection factories
# ---------------------------------------------------------------------------


def get_coordinator_db() -> sqlite3.Connection:
    """Open a WAL-mode connection to the global coordinator DB (~/.minion/coordinator.db)."""
    db_path = resolve_coordinator_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


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
# Init — create all tables and run migrations
# ---------------------------------------------------------------------------


def init_db() -> None:
    """Create all tables if they don't exist, then run pending migrations."""
    from minion.db.migrations import _migrate, _run_migrations
    from minion.db.schema import (
        _COMMS_SCHEMA_SQL,
        _REQUIREMENTS_SCHEMA_SQL,
        _SCHEMA_VERSION_SQL,
        _TASKS_SCHEMA_SQL,
    )

    conn = get_db()
    conn.executescript(_COMMS_SCHEMA_SQL)
    conn.executescript(_TASKS_SCHEMA_SQL)
    conn.executescript(_REQUIREMENTS_SCHEMA_SQL)
    conn.executescript(_SCHEMA_VERSION_SQL)
    _migrate(conn)
    _run_migrations(conn)
    conn.close()
