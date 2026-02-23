"""Rebuild the backlog DB index by scanning the filesystem."""

from __future__ import annotations

import os
from typing import Any

from minion.db import get_db, now_iso
from minion.backlog._helpers import _get_backlog_path, _parse_readme, TYPE_TO_FOLDER


# Reverse mapping — folder name → type string for metadata inference
_FOLDER_TO_TYPE: dict[str, str] = {v: k for k, v in TYPE_TO_FOLDER.items()}


def reindex(db: str | None = None) -> dict[str, Any]:
    """Scan .work/backlog/ and insert any README.md items missing from the DB.

    Existing rows are preserved (INSERT OR IGNORE). Metadata is parsed from
    each README.md using _parse_readme; unknown or unreadable fields default
    gracefully. Returns counts so callers can log progress.
    """
    backlog_root = _get_backlog_path(db)

    if not os.path.isdir(backlog_root):
        return {"registered": 0, "skipped": 0, "error": f"Backlog directory not found: {backlog_root}"}

    conn = get_db() if db is None else __import__("sqlite3").connect(db)
    if db is not None:
        conn.row_factory = __import__("sqlite3").Row
    try:
        cursor = conn.cursor()
        now = now_iso()
        registered = 0
        skipped = 0

        for dirpath, _dirnames, filenames in os.walk(backlog_root):
            if "README.md" not in filenames:
                continue

            # Derive file_path relative to backlog_root (e.g. "ideas/my-idea")
            rel = os.path.relpath(dirpath, backlog_root).replace("\\", "/")
            if rel == ".":
                # Skip the backlog root itself
                continue

            # Infer item type from the top-level folder segment
            parts = rel.split("/")
            folder_name = parts[0]
            item_type = _FOLDER_TO_TYPE.get(folder_name)
            if item_type is None:
                # Unknown folder structure — skip to avoid polluting the index
                continue

            readme_path = os.path.join(dirpath, "README.md")
            meta = _parse_readme(readme_path)
            title = meta.get("title") or parts[-1]  # fall back to slug as title
            source = meta.get("source") or "unknown"

            result = cursor.execute(
                """INSERT OR IGNORE INTO backlog
                       (file_path, type, title, priority, status, source, created_at, updated_at)
                   VALUES (?, ?, ?, 'unset', 'open', ?, ?, ?)""",
                (rel, item_type, title, source, now, now),
            )
            if result.rowcount > 0:
                registered += 1
            else:
                skipped += 1

        conn.commit()
        return {"registered": registered, "skipped": skipped}
    finally:
        conn.close()
