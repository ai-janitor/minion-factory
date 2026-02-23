"""Read-only task queries — no writes, no side effects."""

from __future__ import annotations

import os

from minion.db import get_db
from ._helpers import _get_flow


def _resolve_path(path: str) -> str:
    """Resolve a DB-stored path against the project root (DB parent's parent)."""
    if os.path.isabs(path):
        return path
    from minion.db import _get_db_path
    db_path = _get_db_path()
    # DB lives at .work/minion.db — project root is two levels up
    project_root = os.path.dirname(os.path.dirname(db_path))
    return os.path.join(project_root, path)


def _inline_file(path: str | None) -> str | None:
    """Read file contents if path exists, else None."""
    if not path:
        return None
    resolved = _resolve_path(path)
    if not os.path.exists(resolved):
        return None
    try:
        with open(resolved) as f:
            return f.read()
    except Exception:
        return None


def _inline_requirement(req_path: str | None) -> str | None:
    """Read README.md from a requirement directory path (relative to .work/requirements/)."""
    if not req_path:
        return None
    from minion.db import _get_db_path
    db_path = _get_db_path()
    project_root = os.path.dirname(os.path.dirname(db_path))
    readme = os.path.join(project_root, ".work", "requirements", req_path, "README.md")
    if not os.path.exists(readme):
        return None
    try:
        with open(readme) as f:
            return f.read()
    except Exception:
        return None


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
        task = dict(row)
        result: dict[str, object] = {"task": task}

        # Inline file contents
        task_content = _inline_file(task.get("task_file"))
        if task_content is not None:
            result["task_content"] = task_content

        result_content = _inline_file(task.get("result_file"))
        if result_content is not None:
            result["result_content"] = result_content

        req_content = _inline_requirement(task.get("requirement_path"))
        if req_content is not None:
            result["requirement_content"] = req_content

        # Transition history
        cursor.execute(
            "SELECT from_status, to_status, triggered_by AS agent, created_at AS timestamp "
            "FROM transition_log WHERE entity_id = ? AND entity_type = 'task' ORDER BY created_at ASC",
            (task_id,),
        )
        result["history"] = [dict(r) for r in cursor.fetchall()]

        # Flow position — DAG render with current stage marked
        task_type = task.get("task_type") or "bugfix"
        flow = _get_flow(task_type)
        if flow:
            result["flow_position"] = flow.render_dag(task.get("status"))

        # Comments
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
