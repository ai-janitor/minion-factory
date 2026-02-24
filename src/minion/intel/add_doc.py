"""Register an intel doc in the index."""

from __future__ import annotations

import json
import os

from minion.db import get_db, now_iso
from ._frontmatter import _parse_frontmatter


_FRONTMATTER_STUB = """\
---
tags: []
linked_tasks: []
linked_reqs: []
author:
date:
---

"""


def add_doc(
    slug: str,
    doc_path: str,
    tags: list[str] | None = None,
    description: str = "",
    created_by: str = "",
    scaffold: bool = False,
) -> dict[str, object]:
    """Insert or update an intel_docs row for the given slug.

    If scaffold=True and the file doesn't exist, create it with a frontmatter stub.
    After inserting, auto-populate intel_links from frontmatter linked_tasks/linked_reqs.
    """
    tags = tags or []

    if scaffold and not os.path.exists(doc_path):
        os.makedirs(os.path.dirname(doc_path), exist_ok=True)
        with open(doc_path, "w", encoding="utf-8") as fh:
            fh.write(_FRONTMATTER_STUB)
    elif not os.path.exists(doc_path):
        return {"error": f"File not found: {doc_path}. Use --scaffold to create it."}

    conn = get_db()
    cursor = conn.cursor()
    now = now_iso()
    try:
        cursor.execute("SELECT slug FROM intel_docs WHERE slug = ?", (slug,))
        exists = cursor.fetchone() is not None

        tags_json = json.dumps(tags)
        if exists:
            cursor.execute(
                """UPDATE intel_docs SET doc_path=?, tags=?, description=?, created_by=?, updated_at=?
                   WHERE slug=?""",
                (doc_path, tags_json, description, created_by, now, slug),
            )
            status = "updated"
        else:
            cursor.execute(
                """INSERT INTO intel_docs (slug, doc_path, tags, description, created_by, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (slug, doc_path, tags_json, description, created_by, now, now),
            )
            status = "added"

        # Auto-link from frontmatter
        fm = _parse_frontmatter(doc_path)
        for task_id in fm.get("linked_tasks", []):
            try:
                cursor.execute(
                    "INSERT OR IGNORE INTO intel_links (intel_slug, entity_type, entity_id) VALUES (?, 'task', ?)",
                    (slug, task_id),
                )
            except Exception:
                pass
        for req_id in fm.get("linked_reqs", []):
            try:
                cursor.execute(
                    "INSERT OR IGNORE INTO intel_links (intel_slug, entity_type, entity_id) VALUES (?, 'requirement', ?)",
                    (slug, req_id),
                )
            except Exception:
                pass

        conn.commit()
        return {"status": status, "slug": slug}
    finally:
        conn.close()
