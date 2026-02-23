"""Read-only task queries — no writes, no side effects."""

from __future__ import annotations

from minion.db import get_db
from ._helpers import _get_flow


def get_tasks(
    status: str = "",
    project: str = "",
    zone: str = "",
    assigned_to: str = "",
    class_required: str = "",
    count: int = 50,
) -> dict[str, object]:
    conn = get_db()
    cursor = conn.cursor()
    try:
        query = "SELECT * FROM tasks WHERE 1=1"
        params: list[str | int] = []

        if status:
            query += " AND status = ?"
            params.append(status)
        else:
            query += " AND status NOT IN ('closed')"

        if project:
            query += " AND project = ?"
            params.append(project)
        if zone:
            query += " AND zone = ?"
            params.append(zone)
        if assigned_to:
            query += " AND assigned_to = ?"
            params.append(assigned_to)
        if class_required:
            query += " AND class_required = ?"
            params.append(class_required)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(count)

        cursor.execute(query, params)
        tasks_list = [dict(row) for row in cursor.fetchall()]
        return {"tasks": tasks_list}
    finally:
        conn.close()


def get_task(task_id: int) -> dict[str, object]:
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        if not row:
            return {"error": f"Task #{task_id} not found."}
        result = {"task": dict(row)}
        try:
            comment_rows = cursor.execute(
                """SELECT agent_name, phase, comment, files_read, created_at
                   FROM task_comments WHERE task_id = ? ORDER BY created_at ASC""",
                (task_id,),
            ).fetchall()
            import json as _json_mod
            comments = []
            for cr in comment_rows:
                c = dict(cr)
                if c.get("files_read"):
                    try:
                        c["files_read"] = _json_mod.loads(c["files_read"])
                    except Exception:
                        pass
                comments.append(c)
            result["comments"] = comments
        except Exception:
            result["comments"] = []
        return result
    finally:
        conn.close()


def get_task_lineage(task_id: int) -> dict[str, object]:
    """Return task detail + transition history + flow stages for lineage visualization."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        if not row:
            return {"error": f"Task #{task_id} not found."}

        task = dict(row)
        task_type = task.get("task_type") or "bugfix"

        # History
        cursor.execute(
            "SELECT from_status, to_status, triggered_by AS agent, created_at AS timestamp FROM transition_log WHERE entity_id = ? AND entity_type = 'task' ORDER BY created_at ASC",
            (task_id,),
        )
        history = [dict(r) for r in cursor.fetchall()]

        # Flow stages for this task type
        flow = _get_flow(task_type)
        stages = sorted(flow.stages.keys())

        return {
            "task": task,
            "history": history,
            "flow_type": task_type,
            "flow_stages": stages,
        }
    finally:
        conn.close()
