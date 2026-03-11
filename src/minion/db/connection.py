"""Database connection management — path resolution, WAL-mode connections.

Handles lazy path resolution from env vars and cwd, plus the get_db() and
get_coordinator_db() connection factories with WAL mode and row factory.

Convention: use connect(db_path) anywhere you have an explicit path.
Use get_db() for the project-local DB. Use get_coordinator_db() for the global coordinator DB.
All three set WAL mode, busy_timeout=5000, and row_factory=sqlite3.Row.

ASSUMPTIONS:
- Every connection uses WAL journal mode. Callers must NOT switch to DELETE or
  TRUNCATE mode — concurrent readers (poll loops, dashboard) depend on WAL for
  snapshot isolation. Switching modes mid-session causes "database is locked" errors.
- busy_timeout=5000ms (5 seconds). If a write takes longer than 5s to acquire the
  lock, sqlite3.OperationalError is raised. This assumes write transactions are short
  (single INSERT/UPDATE). Long-running writes will cause timeout cascades.
- row_factory=sqlite3.Row is set on ALL connections. Every module that calls get_db()
  or connect() expects dict-like Row objects, not tuples. Removing this breaks all
  row["column_name"] access patterns across the entire codebase.
- _db_path is module-level cached after first resolution. Once resolved, it does NOT
  re-read env vars or re-walk the filesystem. If MINION_DB_PATH changes mid-process,
  call reset_db_path() to force re-resolution. Spawned subprocesses get a fresh cache.
- get_db() enables foreign_keys=ON; get_coordinator_db() and raw connect() do NOT.
  The coordinator DB has no foreign keys. If you add FK constraints to coordinator
  schema, you must enable them explicitly.
- init_db() is NOT idempotent for migrations — it's safe to call multiple times
  (CREATE IF NOT EXISTS), but migrations only run forward. Running init_db() on a
  newer schema (from a newer code version) with an older binary is undefined.
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


def connect(db_path: str | os.PathLike, *, timeout: float = 5) -> sqlite3.Connection:
    """Open a WAL-mode connection to any explicit db_path.

    Use this anywhere callers have a db_path in hand — avoids repeating
    PRAGMA boilerplate across 10+ modules. Sets WAL, busy_timeout=5000, row_factory.

    Big-O: O(1) — sqlite3.connect + 2 PRAGMA calls. makedirs is O(depth) but
    typically cached by OS. Hot path — called on every CLI command, every poll
    iteration, every dashboard cycle.
    """
    # SU-09: Precondition assertions
    assert db_path, "db_path must not be empty"
    # Purpose: single place for connection setup — WAL, busy_timeout, row_factory
    # Rationale: 27 direct sqlite3.connect() calls scattered across daemon, network,
    #            comms each re-implemented this setup; extract it here.
    os.makedirs(os.path.dirname(os.path.abspath(str(db_path))), exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=timeout)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def get_coordinator_db() -> sqlite3.Connection:
    """Open a WAL-mode connection to the global coordinator DB (~/.minion/coordinator.db)."""
    db_path = resolve_coordinator_db_path()
    return connect(db_path)


def get_db() -> sqlite3.Connection:
    """Open a WAL-mode connection to the project-local DB (.work/minion.db)."""
    db_path = _get_db_path()
    conn = connect(db_path)
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
