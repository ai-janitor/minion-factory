"""Read the content of a registered intel doc.

Purpose: Read the content of a registered intel doc.
Rationale: Extracted into own module for single-responsibility intel management.
Responsibility: Read the content of a registered intel doc. NOT responsible for unrelated concerns.
Organization: Standalone functions and/or a single class. See source."""

from __future__ import annotations

import os

from minion.db import get_db
from minion.fs import MAX_DOC_SIZE


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
        size = os.path.getsize(path)
        if size > MAX_DOC_SIZE:
            return {"error": f"File too large: {path} ({size} bytes > {MAX_DOC_SIZE})", "slug": slug}
        with open(path, encoding="utf-8") as fh:
            content = fh.read()
    except OSError:
        return {"error": f"File not found: {path}", "slug": slug}

    if summary:
        content = "\n".join(content.splitlines()[:10])

    return {"slug": slug, "path": path, "content": content}
