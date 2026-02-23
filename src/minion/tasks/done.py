"""Fast-close for externally completed tasks.

Bypasses the normal assign/pull/submit-result/close ceremony for work
done outside the minion DAG (worktrees, Claude Code agents, etc.).
"""

from __future__ import annotations

import os

from minion.db import get_db, now_iso
from minion.defaults import resolve_work_dir
from ._helpers import _log_transition


def done_task(agent_name: str, task_id: int, summary: str = "") -> dict[str, object]:
    conn = get_db()
    cursor = conn.cursor()
    now = now_iso()
    try:
        cursor.execute("SELECT agent_class FROM agents WHERE name = ?", (agent_name,))
        row = cursor.fetchone()
        if not row:
            return {"error": f"BLOCKED: Agent '{agent_name}' not registered."}
        if row["agent_class"] != "lead":
            return {"error": f"BLOCKED: Only lead-class agents can force-close tasks. '{agent_name}' is '{row['agent_class']}'."}

        cursor.execute(
            "SELECT id, status, title, assigned_to FROM tasks WHERE id = ?",
            (task_id,),
        )
        task_row = cursor.fetchone()
        if not task_row:
            return {"error": f"Task #{task_id} not found."}

        old_status = task_row["status"]
        if old_status == "closed":
            return {"error": f"Task #{task_id} is already closed."}

        result_file = None
        if summary:
            work_dir = resolve_work_dir()
            results_dir = work_dir / "results"
            results_dir.mkdir(parents=True, exist_ok=True)
            result_file = str(results_dir / f"TASK-{task_id}-result.md")
            with open(result_file, "w") as f:
                f.write(f"# Task #{task_id} Result\n\n{summary}\n")

        updates = "status = 'closed', updated_at = ?"
        params: list[object] = [now]
        if result_file:
            updates += ", result_file = ?"
            params.append(result_file)
        params.append(task_id)

        cursor.execute(f"UPDATE tasks SET {updates} WHERE id = ?", params)
        _log_transition(cursor, task_id, old_status, "closed", agent_name, now)
        conn.commit()

        result: dict[str, object] = {
            "status": "closed",
            "task_id": task_id,
            "title": task_row["title"],
            "from_status": old_status,
        }
        if result_file:
            result["result_file"] = result_file
        return result
    finally:
        conn.close()
