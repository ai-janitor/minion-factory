"""Small utility functions — timestamps, agent registration.
Shared helpers that don't fit neatly into agents/messages/connection but
are used across the codebase.

Purpose: Small utility functions — timestamps, agent registration.
Rationale: Extracted into own module for single-responsibility database access.
Responsibility: Small utility functions — timestamps, agent registration. NOT responsible for unrelated concerns.
Organization: Standalone functions and/or a single class. See source."""

from __future__ import annotations

import datetime


def now_iso() -> str:
    return datetime.datetime.now().isoformat()


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
