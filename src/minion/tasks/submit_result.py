"""Submit a result file for a task."""

from __future__ import annotations

import os

from minion.db import get_db, now_iso


def submit_result(agent_name: str, task_id: int, result_file: str) -> dict[str, object]:
    conn = get_db()
    cursor = conn.cursor()
    now = now_iso()
    try:
        cursor.execute("SELECT name FROM agents WHERE name = ?", (agent_name,))
        if not cursor.fetchone():
            return {"error": f"BLOCKED: Agent '{agent_name}' not registered."}

        cursor.execute("SELECT id, status, title FROM tasks WHERE id = ?", (task_id,))
        task_row = cursor.fetchone()
        if not task_row:
            return {"error": f"Task #{task_id} not found."}

        if not os.path.exists(result_file):
            return {"error": f"BLOCKED: Result file does not exist: {result_file}"}

        cursor.execute(
            "UPDATE tasks SET result_file = ?, updated_at = ? WHERE id = ?",
            (result_file, now, task_id),
        )
        cursor.execute("UPDATE agents SET last_seen = ? WHERE name = ?", (now, agent_name))
        conn.commit()

        return {"status": "submitted", "task_id": task_id, "result_file": result_file}
    finally:
        conn.close()
