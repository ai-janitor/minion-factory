"""Coordinator DB — global agent registry at ~/.minion/coordinator.db.
Manages the coordinator schema, initialization, activity tracking,
and auto-pruning of stale agents across projects.

Purpose: Coordinator DB — global agent registry at ~/.minion/coordinator.db.
Rationale: Extracted into own module for single-responsibility database access.
Responsibility: Coordinator DB — global agent registry at ~/.minion/coordinator.db. NOT responsible for unrelated concerns.
Organization: Standalone functions and/or a single class. See source."""

from __future__ import annotations

import logging

from minion.db.connection import get_coordinator_db, get_db
from minion.db.timestamp_and_agent_registry import now_iso
from minion.db.schema import _COORDINATOR_SCHEMA_SQL

log = logging.getLogger(__name__)

_STALE_HOURS = 6
_last_prune_check: float = 0.0


def init_coordinator_db() -> None:
    """Create the coordinator DB schema if it doesn't exist."""
    conn = get_coordinator_db()
    try:
        conn.executescript(_COORDINATOR_SCHEMA_SQL)
        # Migrate: add columns missing in older DBs
        cols = {row[1] for row in conn.execute("PRAGMA table_info(agents)").fetchall()}
        if "last_active" not in cols:
            conn.execute("ALTER TABLE agents ADD COLUMN last_active TEXT")
        if "scope_mode" not in cols:
            conn.execute("ALTER TABLE agents ADD COLUMN scope_mode TEXT DEFAULT 'project'")
        conn.commit()
    finally:
        conn.close()


def _prune_local_stale_agents(cutoff: str) -> None:
    """Remove agents from the local .work/minion.db whose last_seen is older than cutoff."""
    try:
        local = get_db()
        try:
            stale = local.execute(
                "SELECT name FROM agents WHERE last_seen IS NOT NULL AND last_seen < ?",
                (cutoff,),
            ).fetchall()
            if stale:
                # Don't prune agents with open/assigned/in_progress tasks
                busy = set()
                for row in stale:
                    count = local.execute(
                        "SELECT COUNT(*) FROM tasks WHERE assigned_to = ? AND status IN ('open', 'assigned', 'in_progress')",
                        (row["name"],),
                    ).fetchone()[0]
                    if count > 0:
                        busy.add(row["name"])
                names = [row["name"] for row in stale if row["name"] not in busy]
                if names:
                    local.execute(
                        f"DELETE FROM agents WHERE name IN ({','.join('?' * len(names))})",
                        names,
                    )
                    local.commit()
        finally:
            local.close()
    except Exception:
        pass


def touch_coordinator_activity(agent_name: str) -> None:
    """Bump last_active for an agent in the coordinator DB. Best-effort, never raises.

    Auto-prunes agents inactive for 6+ hours, checked at most once per 10 minutes.
    """
    import time as _time
    global _last_prune_check
    try:
        conn = get_coordinator_db()
        try:
            import os as _os
            now = now_iso()
            conn.execute(
                """INSERT INTO agents (name, project_path, last_active, last_seen, registered_at, status)
                   VALUES (?, ?, ?, ?, ?, 'active')
                   ON CONFLICT(name) DO UPDATE SET last_active = excluded.last_active""",
                (agent_name, _os.getcwd(), now, now, now),
            )
            # Auto-prune stale agents (at most once per 10 minutes)
            wall = _time.monotonic()
            if wall - _last_prune_check > 600:
                _last_prune_check = wall
                import datetime as _dt
                cutoff = (_dt.datetime.now() - _dt.timedelta(hours=_STALE_HOURS)).isoformat()
                # Prune coordinator DB
                stale = conn.execute(
                    "SELECT name, project_path FROM agents WHERE last_active IS NOT NULL AND last_active < ?",
                    (cutoff,),
                ).fetchall()
                if stale:
                    import os as _os
                    for row in stale:
                        if row["project_path"]:
                            roster = _os.path.join(row["project_path"], ".work", ".minion-agents", row["name"])
                            if _os.path.exists(roster):
                                _os.remove(roster)
                    names = [row["name"] for row in stale]
                    conn.execute(
                        f"DELETE FROM agents WHERE name IN ({','.join('?' * len(names))})",
                        names,
                    )
                # Prune local DB — same 6-hour threshold on last_seen
                _prune_local_stale_agents(cutoff)
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass
