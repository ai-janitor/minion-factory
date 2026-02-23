"""Task comments — mid-flight context injection and phase input tracking."""

from __future__ import annotations

import json
from typing import Any

from minion.db import get_db, now_iso


def add_comment(
    agent_name: str,
    task_id: int,
    comment: str,
    files_read: list[str] | None = None,
) -> dict[str, Any]:
    """Add a comment to a task. Phase auto-detected from current task status."""
    conn = get_db()
    cursor = conn.cursor()
    now = now_iso()
    try:
        cursor.execute("SELECT id, status FROM tasks WHERE id = ?", (task_id,))
        task_row = cursor.fetchone()
        if not task_row:
            return {"error": f"Task #{task_id} not found."}

        phase = task_row["status"]
        files_json = json.dumps(files_read) if files_read else None

        cursor.execute(
            """INSERT INTO task_comments (task_id, agent_name, phase, comment, files_read, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (task_id, agent_name, phase, comment, files_json, now),
        )
        comment_id = cursor.lastrowid
        conn.commit()
        return {
            "status": "added",
            "comment_id": comment_id,
            "task_id": task_id,
            "phase": phase,
            "agent": agent_name,
        }
    finally:
        conn.close()


def list_comments(task_id: int) -> dict[str, Any]:
    """List all comments for a task, ordered by time."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM tasks WHERE id = ?", (task_id,))
        if not cursor.fetchone():
            return {"error": f"Task #{task_id} not found."}

        cursor.execute(
            """SELECT id, agent_name, phase, comment, files_read, created_at
               FROM task_comments WHERE task_id = ? ORDER BY created_at ASC""",
            (task_id,),
        )
        comments = []
        for row in cursor.fetchall():
            c = dict(row)
            if c.get("files_read"):
                try:
                    c["files_read"] = json.loads(c["files_read"])
                except (json.JSONDecodeError, TypeError):
                    pass
            comments.append(c)
        return {"task_id": task_id, "comments": comments, "count": len(comments)}
    finally:
        conn.close()
