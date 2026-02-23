"""Add a new item to the backlog."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from minion.db import get_db, now_iso, _get_db_path
from minion.backlog._helpers import (
    VALID_TYPES,
    VALID_PRIORITIES,
    TYPE_TO_FOLDER,
    _get_backlog_path,
    _slugify,
)


def _resolve_template_path() -> Path:
    """Find backlog.md template relative to the project root.

    Project root is two levels above the DB file:
      .work/minion.db  → .work/ → project-root/
    Falls back to searching upward from this source file.
    """
    # Primary: derive from DB location (respects -C / MINION_DB_PATH overrides)
    db_path = Path(_get_db_path())
    project_root = db_path.parent.parent  # .work/ -> project root
    candidate = project_root / "task-flows" / "templates" / "backlog.md"
    if candidate.exists():
        return candidate

    # Fallback: walk up from this file's location until we find the template
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "task-flows" / "templates" / "backlog.md"
        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        "backlog.md template not found. Expected at task-flows/templates/backlog.md "
        f"relative to project root ({project_root})."
    )


def add(
    type: str,
    title: str,
    source: str = "human",
    description: str = "",
    priority: str = "unset",
    db: str | None = None,
) -> dict[str, Any]:
    """Capture a new backlog item as a README.md folder and index it in the DB.

    Validates type/priority, stamps the template, writes the folder, then
    inserts a row into the backlog table. file_path stored in DB is relative
    to .work/backlog/ so it survives directory moves.
    """
    if type not in VALID_TYPES:
        return {"error": f"Invalid type '{type}'. Valid: {', '.join(sorted(VALID_TYPES))}"}
    if priority not in VALID_PRIORITIES:
        return {"error": f"Invalid priority '{priority}'. Valid: {', '.join(sorted(VALID_PRIORITIES))}"}

    slug = _slugify(title)
    if not slug:
        return {"error": "Title produces an empty slug — use alphanumeric characters."}

    backlog_root = _get_backlog_path(db)
    folder = os.path.join(backlog_root, TYPE_TO_FOLDER[type], slug)

    if os.path.exists(folder):
        return {"error": f"Backlog item folder already exists: {folder}"}

    os.makedirs(folder, exist_ok=True)

    template_path = _resolve_template_path()
    template = template_path.read_text()
    import datetime
    today = datetime.date.today().isoformat()
    content = template.format(
        title=title,
        type=type,
        source=source,
        date=today,
        description=description or "_No description provided._",
    )

    readme_path = os.path.join(folder, "README.md")
    with open(readme_path, "w") as f:
        f.write(content)

    # file_path stored relative to backlog root for portability
    rel_path = os.path.join(TYPE_TO_FOLDER[type], slug)

    now = now_iso()
    conn = get_db() if db is None else __import__("sqlite3").connect(db)
    if db is not None:
        conn.row_factory = __import__("sqlite3").Row
    try:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO backlog
                   (file_path, type, title, priority, status, source, created_at, updated_at)
               VALUES (?, ?, ?, ?, 'open', ?, ?, ?)""",
            (rel_path, type, title, priority, source, now, now),
        )
        item_id = cursor.lastrowid
        conn.commit()
        return {
            "id": item_id,
            "file_path": rel_path,
            "title": title,
            "type": type,
            "status": "open",
        }
    finally:
        conn.close()
