"""Small utility functions — timestamps, agent registration.

Shared helpers that don't fit neatly into agents/messages/connection but
are used across the codebase.
"""

from __future__ import annotations

import datetime


def now_iso() -> str:
    return datetime.datetime.now().isoformat()


def parse_iso_to_naive_local(ts: str) -> datetime.datetime:
    """Parse an ISO timestamp to a naive local-time datetime.

    Handles both naive timestamps (from now_iso()) and timezone-aware
    timestamps (from utc_now_iso()). Aware timestamps are converted to
    local time then stripped of tzinfo so they can be safely subtracted
    from datetime.datetime.now() without TypeError.
    """
    dt = datetime.datetime.fromisoformat(ts)
    if dt.tzinfo is not None:
        # Convert UTC (or any tz) to local time, then strip tzinfo
        dt = dt.astimezone().replace(tzinfo=None)
    return dt


def register_agent_db(name: str, agent_class: str, model: str | None = None) -> None:
    """Insert or replace an agent row without filesystem side effects.

    Use this in tests and tooling that need an agent record in the DB but
    must avoid comms.register() side effects (reading onboarding files,
    creating inbox dirs, broadcasting messages).
    """
    from minion.db.connection import get_db

    conn = get_db()
    now = now_iso()
    try:
        conn.execute(
            """INSERT OR REPLACE INTO agents
                (name, agent_class, model, registered_at, last_seen)
            VALUES (?, ?, ?, ?, ?)""",
            (name, agent_class, model or None, now, now),
        )
        conn.commit()
    finally:
        conn.close()
