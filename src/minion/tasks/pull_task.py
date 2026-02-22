"""Claim a specific task — DAG-aware task puller."""

from __future__ import annotations

import os

from minion.db import get_db, now_iso
from minion.crew._tmux import update_pane_task
from ._helpers import _get_flow, _log_transition


def pull_task(agent_name: str, task_id: int) -> dict[str, object]:
    """Claim a specific task. Agent calls this after poll shows available tasks."""
    conn = get_db()
    cursor = conn.cursor()
    now = now_iso()
    try:
        # moon_crash blocks
        cursor.execute("SELECT value FROM flags WHERE key = 'moon_crash'")
        mc = cursor.fetchone()
        if mc and mc["value"] == "1":
            return {"error": "BLOCKED: moon_crash active — no task claims."}

        cursor.execute("SELECT agent_class FROM agents WHERE name = ?", (agent_name,))
        agent_row = cursor.fetchone()
        if not agent_row:
            return {"error": f"BLOCKED: Agent '{agent_name}' not registered."}

        cursor.execute(
            "SELECT id, title, task_file, status, assigned_to, blocked_by, task_type FROM tasks WHERE id = ?",
            (task_id,),
        )
        task_row = cursor.fetchone()
        if not task_row:
            return {"error": f"Task #{task_id} not found."}

        task_status = task_row["status"]
        task_type = task_row["task_type"] or "bugfix"
        flow = _get_flow(task_type)

        if flow and flow.is_terminal(task_status):
            return {"error": f"BLOCKED: Task #{task_id} is in terminal status '{task_status}'."}

        # Check blockers
        blocked_by_str = task_row["blocked_by"]
        if blocked_by_str:
            blocker_ids = [int(x.strip()) for x in blocked_by_str.split(",") if x.strip()]
            placeholders = ",".join("?" for _ in blocker_ids)
            cursor.execute(
                f"SELECT COUNT(*) FROM tasks WHERE id IN ({placeholders}) AND status != 'closed'",
                blocker_ids,
            )
            if cursor.fetchone()[0] > 0:
                return {"error": f"BLOCKED: Task #{task_id} has unresolved blockers."}

        # Atomic claim
        if task_status in ("fixed", "verified"):
            cursor.execute(
                """UPDATE tasks SET assigned_to = ?, updated_at = ?
                   WHERE id = ? AND status = ? AND (assigned_to IS NULL OR assigned_to = ?)""",
                (agent_name, now, task_id, task_status, agent_name),
            )
        else:
            cursor.execute(
                """UPDATE tasks SET assigned_to = ?, status = 'assigned', updated_at = ?
                   WHERE id = ? AND (
                       (status = 'assigned' AND assigned_to = ?) OR
                       (status = 'open' AND assigned_to IS NULL)
                   )""",
                (agent_name, now, task_id, agent_name),
            )

        if cursor.rowcount == 0:
            return {"error": f"Race lost — task #{task_id} was claimed by another agent."}

        new_status = "assigned" if task_status not in ("fixed", "verified") else task_status
        _log_transition(cursor, task_id, task_status, new_status, agent_name, now)

        # Read task file content
        task_content = ""
        task_file = task_row["task_file"]
        if task_file and os.path.exists(task_file):
            with open(task_file) as f:
                task_content = f.read()

        cursor.execute(
            "UPDATE agents SET context_updated_at = ?, last_seen = ? WHERE name = ?",
            (now, now, agent_name),
        )
        conn.commit()

        update_pane_task(agent_name, f"T{task_id}: {task_row['title']}")

        result: dict[str, object] = {
            "status": "claimed",
            "task_id": task_id,
            "title": task_row["title"],
            "task_file": task_file,
            "task_status": task_status,
        }
        if task_content:
            result["task_content"] = task_content
        return result
    finally:
        conn.close()
