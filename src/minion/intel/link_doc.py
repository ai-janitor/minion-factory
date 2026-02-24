"""Link an intel doc to a task or requirement."""

from __future__ import annotations

import sqlite3

from minion.db import get_db


def link_doc(
    slug: str,
    task_id: int | None = None,
    req_id: int | None = None,
) -> dict[str, object]:
    """Insert an intel_links row connecting a doc to a task or requirement.

    Exactly one of task_id or req_id must be provided.
    Duplicate links (UNIQUE constraint) return already_linked, not an error.
    """
    if task_id is None and req_id is None:
        return {"error": "Provide --task or --req (exactly one required)."}
    if task_id is not None and req_id is not None:
        return {"error": "Provide only one of --task or --req, not both."}

    entity_type = "task" if task_id is not None else "requirement"
    entity_id = task_id if task_id is not None else req_id

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT slug FROM intel_docs WHERE slug = ?", (slug,))
        if not cursor.fetchone():
            return {"error": f"Intel doc '{slug}' not registered."}

        try:
            cursor.execute(
                "INSERT INTO intel_links (intel_slug, entity_type, entity_id) VALUES (?, ?, ?)",
                (slug, entity_type, entity_id),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            return {"status": "already_linked", "slug": slug, "entity_type": entity_type, "entity_id": entity_id}

        return {"status": "linked", "slug": slug, "entity_type": entity_type, "entity_id": entity_id}
    finally:
        conn.close()
