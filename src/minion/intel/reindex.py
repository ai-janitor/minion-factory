"""Rebuild intel_docs and intel_links from filesystem frontmatter."""

from __future__ import annotations

import json
import os
import sqlite3

from minion.db import get_db, now_iso
from ._frontmatter import _parse_frontmatter


def reindex_intel() -> dict[str, object]:
    """Walk .work/intel/, parse frontmatter, and upsert into intel_docs/intel_links.

    Slug is derived from the relative path stem, e.g. 'design/cpu-ops' for
    .work/intel/design/cpu-ops.md. WAR_PLAN.md is skipped — it's not queryable.

    Does NOT delete existing DB rows for docs missing from disk (avoids data loss).
    """
    from minion.db import RUNTIME_DIR
    intel_dir = os.path.join(RUNTIME_DIR, "intel")

    if not os.path.isdir(intel_dir):
        return {"status": "ok", "indexed": 0, "links_created": 0}

    conn = get_db()
    cursor = conn.cursor()
    now = now_iso()
    indexed = 0
    links_created = 0

    try:
        for dirpath, _dirs, files in os.walk(intel_dir):
            for fname in files:
                if not fname.endswith(".md"):
                    continue
                if fname == "WAR_PLAN.md":
                    continue

                abs_path = os.path.join(dirpath, fname)
                rel = os.path.relpath(abs_path, intel_dir)
                # slug: relative path without .md extension, forward slashes
                slug = os.path.splitext(rel)[0].replace(os.sep, "/")

                fm = _parse_frontmatter(abs_path)
                tags_json = json.dumps(fm.get("tags", []))

                cursor.execute(
                    """INSERT OR REPLACE INTO intel_docs (slug, doc_path, tags, description, created_by, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, COALESCE((SELECT created_at FROM intel_docs WHERE slug=?), ?), ?)""",
                    (slug, abs_path, tags_json, "", fm.get("author", ""), slug, now, now),
                )
                indexed += 1

                for task_id in fm.get("linked_tasks", []):
                    try:
                        cursor.execute(
                            "INSERT OR IGNORE INTO intel_links (intel_slug, entity_type, entity_id) VALUES (?, 'task', ?)",
                            (slug, task_id),
                        )
                        if cursor.rowcount:
                            links_created += 1
                    except sqlite3.IntegrityError:
                        pass

                for req_id in fm.get("linked_reqs", []):
                    try:
                        cursor.execute(
                            "INSERT OR IGNORE INTO intel_links (intel_slug, entity_type, entity_id) VALUES (?, 'requirement', ?)",
                            (slug, req_id),
                        )
                        if cursor.rowcount:
                            links_created += 1
                    except sqlite3.IntegrityError:
                        pass

        conn.commit()
        return {"status": "ok", "indexed": indexed, "links_created": links_created}
    finally:
        conn.close()
