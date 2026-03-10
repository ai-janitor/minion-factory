"""Update priority and/or status of an existing backlog item.

Purpose: Update priority and/or status of an existing backlog item.
Rationale: Extracted into own module for single-responsibility backlog management.
Responsibility: Update priority and/or status of an existing backlog item. NOT responsible for unrelated concerns.
Organization: Standalone functions and/or a single class. See source."""

from __future__ import annotations

from typing import Any

from minion.db import get_db, now_iso
from minion.backlog.path_resolution_and_slug import VALID_PRIORITIES, VALID_STATUSES


def update_item(
    file_path: str | None = None,
    priority: str | None = None,
    status: str | None = None,
    flow_hint: str | None = None,
    db: str | None = None,
    item_id: int | None = None,
) -> dict[str, Any]:
    """Patch mutable fields on a backlog item and bump updated_at.

    Items can be looked up by file_path OR item_id (numeric backlog ID).
    At least one of priority, status, or flow_hint must be provided. Priority
    and status are validated against vocabulary constants before any write.
    This works regardless of the item's current status (open, deferred, etc.).
    """
    if file_path is None and item_id is None:
        return {"error": "Provide file_path or item_id to identify the backlog item."}
    if priority is None and status is None and flow_hint is None:
        return {"error": "Provide at least one field to update: priority, status, flow_hint."}
    if priority is not None and priority not in VALID_PRIORITIES:
        return {"error": f"Invalid priority '{priority}'. Valid: {', '.join(sorted(VALID_PRIORITIES))}"}
    if status is not None and status not in VALID_STATUSES:
        return {"error": f"Invalid status '{status}'. Valid: {', '.join(sorted(VALID_STATUSES))}"}
    # Block status=promoted via update — must use 'backlog promote' command instead
    if status == "promoted":
        return {"error": "Cannot set status to 'promoted' via update. Use 'minion backlog promote' instead — it requires lead auth and creates the requirement entry."}

    conn = get_db() if db is None else __import__("sqlite3").connect(db)
    if db is not None:
        conn.row_factory = __import__("sqlite3").Row
    try:
        cursor = conn.cursor()
        # Look up by item_id or file_path — no status filter so deferred/killed/etc. items are found
        if item_id is not None:
            cursor.execute("SELECT * FROM backlog WHERE id = ?", (item_id,))
        else:
            cursor.execute("SELECT * FROM backlog WHERE file_path = ?", (file_path,))
        row = cursor.fetchone()
        if not row:
            lookup_key = f"id={item_id}" if item_id is not None else f"'{file_path}'"
            return {"error": f"Backlog item {lookup_key} not found."}

        # Use the actual file_path from the DB row for the UPDATE WHERE clause
        actual_file_path = row["file_path"]

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

        params.append(actual_file_path)
        cursor.execute(
            f"UPDATE backlog SET {', '.join(set_clauses)} WHERE file_path = ?",
            params,
        )
        conn.commit()

        cursor.execute("SELECT * FROM backlog WHERE file_path = ?", (actual_file_path,))
        updated = cursor.fetchone()
        return dict(updated)
    finally:
        conn.close()
