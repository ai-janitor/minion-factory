"""Fetch intel doc metadata and its linked entities."""

from __future__ import annotations

import json

from minion.db import get_db


def get_doc(slug: str) -> dict[str, object]:
    """Return full metadata + links for a registered intel doc."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT slug, doc_path, tags, description, created_by, created_at FROM intel_docs WHERE slug = ?",
            (slug,),
        )
        row = cursor.fetchone()
        if not row:
            return {"error": f"Intel doc '{slug}' not registered."}

        doc = dict(row)
        doc["tags"] = json.loads(doc.get("tags") or "[]")

        cursor.execute(
            "SELECT entity_type, entity_id FROM intel_links WHERE intel_slug = ? ORDER BY entity_type, entity_id",
            (slug,),
        )
        links = [{"entity_type": r["entity_type"], "entity_id": r["entity_id"]} for r in cursor.fetchall()]

        return {"doc": doc, "links": links}
    finally:
        conn.close()
