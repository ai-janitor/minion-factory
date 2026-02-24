"""Find intel docs by tag or path fragment."""

from __future__ import annotations

import json

from minion.db import get_db


def find_docs(tag: str = "", path_fragment: str = "") -> dict[str, object]:
    """Search intel_docs by tag and/or path fragment (AND when both provided).

    At least one of tag or path_fragment should be non-empty for useful results.
    """
    conn = get_db()
    cursor = conn.cursor()
    try:
        wheres = []
        params: list[object] = []

        if tag:
            wheres.append('tags LIKE ?')
            params.append(f'%"{tag}"%')
        if path_fragment:
            wheres.append('doc_path LIKE ?')
            params.append(f'%{path_fragment}%')

        where_clause = ("WHERE " + " AND ".join(wheres)) if wheres else ""
        cursor.execute(
            f"""SELECT slug, doc_path, tags, description, created_by, created_at
                FROM intel_docs {where_clause} ORDER BY slug""",
            params,
        )
        docs = []
        for row in cursor.fetchall():
            d = dict(row)
            d["tags"] = json.loads(d.get("tags") or "[]")
            docs.append(d)
        return {"docs": docs}
    finally:
        conn.close()
