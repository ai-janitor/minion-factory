"""Read the content of a registered intel doc."""

from __future__ import annotations

from minion.db import get_db


def read_doc(slug: str, summary: bool = False) -> dict[str, object]:
    """Return file content for a registered intel doc.

    summary=True returns only the first 10 lines — useful for quick context injection.
    """
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT doc_path FROM intel_docs WHERE slug = ?", (slug,))
        row = cursor.fetchone()
        if not row:
            return {"error": f"Intel doc '{slug}' not registered."}
        path = row["doc_path"]
    finally:
        conn.close()

    try:
        with open(path, encoding="utf-8") as fh:
            content = fh.read()
    except OSError:
        return {"error": f"File not found: {path}", "slug": slug}

    if summary:
        content = "\n".join(content.splitlines()[:10])

    return {"slug": slug, "path": path, "content": content}
