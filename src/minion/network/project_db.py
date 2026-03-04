"""LRU connection cache for per-project SQLite databases.

Purpose: Provide cached, read-only connections to project-local .work/minion.db
         files so that dashboard endpoints don't open/close connections per request.
Rationale: With 20+ endpoints potentially hitting multiple project DBs per request,
           open-close-per-request creates unacceptable overhead. An LRU cache with
           bounded size (max 10) and TTL (5 min) keeps file descriptor usage bounded
           while amortizing connection cost.
Responsibility: Connection lifecycle — open, cache, evict, close. All connections
                are read-only (sqlite3 URI mode ?mode=ro) so no locking needed.
Organization: Module-level LRU cache with get_project_db() as the public API.

Thread safety: Project DBs are opened read-only. SQLite WAL mode supports concurrent
               readers without locks. The LRU cache itself uses a threading.Lock for
               safe eviction, but connections can be used concurrently once obtained.

Implementation order: 2nd (after db_schema, before discovery and handlers).
"""

from __future__ import annotations

import os
import sqlite3
import threading
import time


# --- Configuration ---
MAX_CACHED_CONNECTIONS = 10
CONNECTION_TTL_SECONDS = 300  # 5 minutes


class _CacheEntry:
    """A cached DB connection with last-access timestamp."""

    def __init__(self, conn: sqlite3.Connection, project_path: str) -> None:
        self.conn = conn
        self.project_path = project_path
        self.last_accessed = time.monotonic()


# Module-level cache state
_cache: dict[str, _CacheEntry] = {}  # keyed by project_path
_cache_lock = threading.Lock()


def get_project_db(project_path: str) -> sqlite3.Connection | None:
    """Get a read-only connection to a project's .work/minion.db.

    Returns None if the DB file doesn't exist. Connections are cached with
    LRU eviction (max 10) and TTL (5 min). Expired entries are closed on access.

    Args:
        project_path: Absolute path to the project directory (e.g., /Users/hung/projects/foo).

    Returns:
        sqlite3.Connection in read-only mode, or None if DB not found.
    """
    db_file = os.path.join(project_path, ".work", "minion.db")
    if not os.path.exists(db_file):
        return None

    with _cache_lock:
        if project_path in _cache:
            entry = _cache[project_path]
            if time.monotonic() - entry.last_accessed > CONNECTION_TTL_SECONDS:
                try:
                    entry.conn.close()
                except Exception:
                    pass
                del _cache[project_path]
            else:
                entry.last_accessed = time.monotonic()
                return entry.conn

        # Evict LRU if at capacity
        if len(_cache) >= MAX_CACHED_CONNECTIONS:
            oldest_key = min(_cache, key=lambda k: _cache[k].last_accessed)
            try:
                _cache[oldest_key].conn.close()
            except Exception:
                pass
            del _cache[oldest_key]

        # Open new read-only connection
        conn = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True, timeout=5)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=3000")
        _cache[project_path] = _CacheEntry(conn, project_path)
        return conn


def close_all() -> None:
    """Close all cached connections. Call on server shutdown."""
    with _cache_lock:
        for entry in _cache.values():
            try:
                entry.conn.close()
            except Exception:
                pass
        _cache.clear()


def evict_expired() -> int:
    """Close and remove connections that have exceeded their TTL.

    Returns number of evicted connections. Can be called periodically
    from a maintenance thread or on each request.
    """
    now = time.monotonic()
    with _cache_lock:
        expired = [k for k, v in _cache.items()
                   if now - v.last_accessed > CONNECTION_TTL_SECONDS]
        for k in expired:
            try:
                _cache[k].conn.close()
            except Exception:
                pass
            del _cache[k]
        return len(expired)
