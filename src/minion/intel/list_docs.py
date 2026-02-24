"""List all registered intel docs, with optional tag filter."""

from __future__ import annotations

import json

from minion.db import get_db


def list_docs(tag: str = "", limit: int = 50) -> dict[str, object]:
    """Return all intel_docs rows, optionally filtered by tag."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        if tag:
            # JSON array contains check — LIKE fallback is portable across SQLite versions
            cursor.execute(
                """SELECT slug, doc_path, tags, description, created_by, created_at
                   FROM intel_docs WHERE tags LIKE ? ORDER BY slug LIMIT ?""",
                (f'%"{tag}"%', limit),
            )
        else:
            cursor.execute(
                """SELECT slug, doc_path, tags, description, created_by, created_at
                   FROM intel_docs ORDER BY slug LIMIT ?""",
                (limit,),
            )
        docs = []
        for row in cursor.fetchall():
            d = dict(row)
            d["tags"] = json.loads(d.get("tags") or "[]")
            docs.append(d)
        return {"docs": docs}
    finally:
        conn.close()
