"""Update priority and/or status of an existing backlog item."""

from __future__ import annotations

from typing import Any

from minion.db import get_db, now_iso
from minion.backlog._helpers import VALID_PRIORITIES, VALID_STATUSES


def update_item(
    file_path: str,
    priority: str | None = None,
    status: str | None = None,
    flow_hint: str | None = None,
    db: str | None = None,
) -> dict[str, Any]:
    """Patch mutable fields on a backlog item and bump updated_at.

    At least one of priority, status, or flow_hint must be provided. Priority
    and status are validated against vocabulary constants before any write.
    """
    if priority is None and status is None and flow_hint is None:
        return {"error": "Provide at least one field to update: priority, status, flow_hint."}
    if priority is not None and priority not in VALID_PRIORITIES:
        return {"error": f"Invalid priority '{priority}'. Valid: {', '.join(sorted(VALID_PRIORITIES))}"}
    if status is not None and status not in VALID_STATUSES:
        return {"error": f"Invalid status '{status}'. Valid: {', '.join(sorted(VALID_STATUSES))}"}

    conn = get_db() if db is None else __import__("sqlite3").connect(db)
    if db is not None:
        conn.row_factory = __import__("sqlite3").Row
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM backlog WHERE file_path = ?", (file_path,))
        row = cursor.fetchone()
        if not row:
            return {"error": f"Backlog item '{file_path}' not found."}

        now = now_iso()
        set_clauses: list[str] = ["updated_at = ?"]
        params: list[Any] = [now]

        if priority is not None:
            set_clauses.append("priority = ?")
            params.append(priority)
        if status is not None:
            set_clauses.append("status = ?")
            params.append(status)
        if flow_hint is not None:
            set_clauses.append("flow_hint = ?")
            params.append(flow_hint)

        params.append(file_path)
        cursor.execute(
            f"UPDATE backlog SET {', '.join(set_clauses)} WHERE file_path = ?",
            params,
        )
        conn.commit()

        cursor.execute("SELECT * FROM backlog WHERE file_path = ?", (file_path,))
        updated = cursor.fetchone()
        return dict(updated)
    finally:
        conn.close()
