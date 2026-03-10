"""Read the spec file (task_file) for a task by ID.

Purpose: Read the spec file (task_file) for a task by ID.
Rationale: Extracted into own module for single-responsibility task management.
Responsibility: Read the spec file (task_file) for a task by ID. NOT responsible for unrelated concerns.
Organization: Standalone functions and/or a single class. See source."""

from __future__ import annotations

import os

from minion.db import get_db
from minion.fs import MAX_DOC_SIZE


def get_spec(task_id: int) -> dict[str, object]:
    """Return the raw contents of a task's spec file (task_file column).

    Agents use this to read their assignment without knowing filesystem paths.
    Returns error dict if task not found, task_file not set, or file missing.
    """
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, title, task_file FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        if not row:
            return {"error": f"Task #{task_id} not found."}

        task = dict(row)
        task_file = task.get("task_file")
        if not task_file:
            return {"error": f"Task #{task_id} has no task_file set."}

        # Resolve relative paths against project root (.work/ parent)
        if not os.path.isabs(task_file):
            from minion.db import _get_db_path
            db_path = _get_db_path()
            project_root = os.path.dirname(os.path.dirname(db_path))
            task_file = os.path.join(project_root, task_file)

        if not os.path.exists(task_file):
            return {"error": f"Task #{task_id} spec file not found: {task_file}"}

        size = os.path.getsize(task_file)
        if size > MAX_DOC_SIZE:
            return {"error": f"Task #{task_id} spec file too large ({size} bytes > {MAX_DOC_SIZE})", "task_file": task_file}

        with open(task_file) as fh:
            contents = fh.read()

        return {
            "task_id": task_id,
            "title": task["title"],
            "task_file": task_file,
            "spec": contents,
        }
    finally:
        conn.close()
