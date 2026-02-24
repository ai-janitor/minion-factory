"""Get all intel docs linked to a specific task."""

from __future__ import annotations

import json

from minion.db import get_db


def intel_for_task(task_id: int) -> dict[str, object]:
    """Return all intel docs linked to the given task_id."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """SELECT d.slug, d.doc_path, d.tags, d.description
               FROM intel_links l
               JOIN intel_docs d ON l.intel_slug = d.slug
               WHERE l.entity_type = 'task' AND l.entity_id = ?
               ORDER BY d.slug""",
            (task_id,),
        )
        docs = []
        for row in cursor.fetchall():
            d = dict(row)
            d["tags"] = json.loads(d.get("tags") or "[]")
            docs.append(d)
        return {"task_id": task_id, "docs": docs}
    finally:
        conn.close()
