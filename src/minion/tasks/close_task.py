"""Close and reopen tasks — lifecycle boundary operations."""

from __future__ import annotations

from minion.db import get_db, now_iso
from minion.crew._tmux import update_pane_task
from ._helpers import _get_flow, _log_transition


def close_task(agent_name: str, task_id: int) -> dict[str, object]:
    conn = get_db()
    cursor = conn.cursor()
    now = now_iso()
    try:
        cursor.execute("SELECT agent_class FROM agents WHERE name = ?", (agent_name,))
        row = cursor.fetchone()
        if not row:
            return {"error": f"BLOCKED: Agent '{agent_name}' not registered."}
        cursor.execute("SELECT id, status, result_file, title, flow_type, assigned_to FROM tasks WHERE id = ?", (task_id,))
        task_row = cursor.fetchone()
        if not task_row:
            return {"error": f"Task #{task_id} not found."}

        task_type = task_row["flow_type"] or "bugfix"
        # Non-leads can close tasks assigned to them (their own phase)
        is_own_task = task_row["assigned_to"] == agent_name
        if row["agent_class"] != "lead" and not is_own_task:
            return {"error": f"BLOCKED: Only lead-class agents can close other agents' tasks. '{agent_name}' can only close tasks assigned to them."}
        flow = _get_flow(task_type)
        if flow and flow.is_terminal(task_row["status"]):
            return {"error": f"Task #{task_id} is already in terminal status '{task_row['status']}'."}

        if not task_row["result_file"]:
            return {"error": f"BLOCKED: Task #{task_id} has no result file. Agent must call submit-result first."}

        cursor.execute(
            "UPDATE tasks SET status = 'closed', updated_at = ? WHERE id = ?",
            (now, task_id),
        )
        _log_transition(cursor, task_id, task_row["status"], "closed", agent_name, now)
        conn.commit()
        # Clear pane task label for the agent who had this task
        if task_row["assigned_to"]:
            update_pane_task(task_row["assigned_to"])
        return {"status": "closed", "task_id": task_id, "title": task_row["title"]}
    finally:
        conn.close()


def reopen_task(agent_name: str, task_id: int, to_status: str = "assigned") -> dict[str, object]:
    """Lead-only: reopen a terminal task back to an earlier phase."""
    conn = get_db()
    cursor = conn.cursor()
    now = now_iso()
    try:
        cursor.execute("SELECT agent_class FROM agents WHERE name = ?", (agent_name,))
        row = cursor.fetchone()
        if not row:
            return {"error": f"BLOCKED: Agent '{agent_name}' not registered."}
        if row["agent_class"] != "lead":
            return {"error": f"BLOCKED: Only lead can reopen tasks. '{agent_name}' is '{row['agent_class']}'."}

        cursor.execute(
            "SELECT id, status, flow_type, title, assigned_to FROM tasks WHERE id = ?",
            (task_id,),
        )
        task_row = cursor.fetchone()
        if not task_row:
            return {"error": f"Task #{task_id} not found."}

        task_type = task_row["flow_type"] or "bugfix"
        flow = _get_flow(task_type)

        if flow and to_status not in flow.stages:
            return {"error": f"Invalid status '{to_status}'. Valid: {', '.join(sorted(flow.stages.keys()))}"}
        if flow and flow.is_terminal(to_status):
            return {"error": f"Cannot reopen to terminal status '{to_status}'."}

        old_status = task_row["status"]
        cursor.execute(
            "UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?",
            (to_status, now, task_id),
        )
        _log_transition(cursor, task_id, old_status, to_status, agent_name, now)
        conn.commit()

        result: dict[str, object] = {
            "status": "reopened", "task_id": task_id,
            "title": task_row["title"],
            "from_status": old_status, "to_status": to_status,
        }
        if flow:
            result["dag"] = flow.render_dag(to_status)
        return result
    finally:
        conn.close()
