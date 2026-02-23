"""Fetch a single backlog item by file_path or DB id."""

from __future__ import annotations

from typing import Any

from minion.db import get_db


def get_item(
    file_path: str | None = None,
    item_id: int | None = None,
    db: str | None = None,
) -> dict[str, Any] | None:
    """Look up a backlog item by file_path or id.

    Exactly one of file_path or item_id must be provided.
    Returns a dict on success, None if not found, or a dict with 'error'
    key if neither lookup key is provided.
    """
    if file_path is None and item_id is None:
        return {"error": "Provide file_path or item_id."}

    conn = get_db() if db is None else __import__("sqlite3").connect(db)
    if db is not None:
        conn.row_factory = __import__("sqlite3").Row
    try:
        cursor = conn.cursor()
        if item_id is not None:
            cursor.execute("SELECT * FROM backlog WHERE id = ?", (item_id,))
        else:
            cursor.execute("SELECT * FROM backlog WHERE file_path = ?", (file_path,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()
