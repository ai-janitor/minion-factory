"""List backlog items with optional type/priority/status filters."""

from __future__ import annotations

from typing import Any

from minion.db import get_db
from minion.backlog._helpers import VALID_TYPES, VALID_PRIORITIES, VALID_STATUSES


def list_items(
    type: str | None = None,
    priority: str | None = None,
    status: str | None = "open",
    db: str | None = None,
) -> list[dict[str, Any]]:
    """Return backlog rows matching the given filters.

    All filters are optional. status defaults to 'open' so callers get active
    items by default; pass status=None to skip the status filter entirely.
    """
    if type is not None and type not in VALID_TYPES:
        return [{"error": f"Invalid type '{type}'. Valid: {', '.join(sorted(VALID_TYPES))}"}]
    if priority is not None and priority not in VALID_PRIORITIES:
        return [{"error": f"Invalid priority '{priority}'. Valid: {', '.join(sorted(VALID_PRIORITIES))}"}]
    if status is not None and status not in VALID_STATUSES:
        return [{"error": f"Invalid status '{status}'. Valid: {', '.join(sorted(VALID_STATUSES))}"}]

    conn = get_db() if db is None else __import__("sqlite3").connect(db)
    if db is not None:
        conn.row_factory = __import__("sqlite3").Row
    try:
        query = "SELECT * FROM backlog WHERE 1=1"
        params: list[Any] = []

        if type is not None:
            query += " AND type = ?"
            params.append(type)
        if priority is not None:
            query += " AND priority = ?"
            params.append(priority)
        if status is not None:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY created_at DESC"
        cursor = conn.cursor()
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()
