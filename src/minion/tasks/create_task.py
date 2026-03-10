"""Create and assign tasks."""

from __future__ import annotations

import os

from minion.db import get_db, now_iso
from minion.crew import update_pane_task
from ._helpers import _get_flow, _log_transition


def create_task(
    agent_name: str,
    title: str,
    task_file: str,
    project: str = "",
    zone: str = "",
    blocked_by: str = "",
    class_required: str = "",
    task_type: str = "bugfix",
    requirement_id: int | None = None,
) -> dict[str, object]:
    # SU-09: Precondition assertions
    assert agent_name, "agent_name must not be empty"
    assert title, "title must not be empty"
    conn = get_db()
    cursor = conn.cursor()
    now = now_iso()
    try:
        cursor.execute("SELECT agent_class FROM agents WHERE name = ?", (agent_name,))
        row = cursor.fetchone()
        if not row:
            return {"error": f"BLOCKED: Agent '{agent_name}' not registered."}
        if row["agent_class"] != "lead" and task_type != "chore":
            return {"error": f"BLOCKED: Only lead-class agents can create tasks (use --type chore for self-service). '{agent_name}' is '{row['agent_class']}'."}

        cursor.execute("SELECT COUNT(*) FROM battle_plan WHERE status = 'active'")
        has_session_plan = cursor.fetchone()[0] > 0
        if not has_session_plan and task_type != "chore":
            # Also accept persistent war plan (.work/intel/WAR_PLAN.md) as context
            from minion.intel.war_plan import _war_plan_path
            if not os.path.exists(_war_plan_path()):
                return {"error": "BLOCKED: No active battle plan or war plan. Set with: minion war set-plan --agent <name> --plan 'objective'"}

        if not os.path.exists(task_file):
            return {"error": f"BLOCKED: Task file does not exist: {task_file}"}

        blocker_ids: list[int] = []
        if blocked_by:
            for raw_id in blocked_by.split(","):
                raw_id = raw_id.strip()
                if not raw_id:
                    continue
                try:
                    tid = int(raw_id)
                except ValueError:
                    return {"error": f"BLOCKED: Invalid task ID in blocked_by: '{raw_id}'."}
                cursor.execute("SELECT id FROM tasks WHERE id = ?", (tid,))
                if not cursor.fetchone():
                    return {"error": f"BLOCKED: blocked_by task #{tid} does not exist."}
                blocker_ids.append(tid)

        blocked_by_str = ",".join(str(i) for i in blocker_ids) if blocker_ids else None

        # Resolve requirement_path from requirement_id for lineage tracing
        req_path = None
        if requirement_id is not None:
            req_row = cursor.execute(
                "SELECT file_path FROM requirements WHERE id = ?", (requirement_id,)
            ).fetchone()
            if req_row:
                req_path = req_row["file_path"]

        cursor.execute(
            """INSERT INTO tasks
               (title, task_file, project, zone, status, blocked_by,
                class_required, flow_type, created_by, activity_count,
                requirement_id, requirement_path, created_at, updated_at)
               VALUES (?, ?, ?, ?, 'open', ?, ?, ?, ?, 0, ?, ?, ?, ?)""",
            (title, task_file, project or None, zone or None, blocked_by_str,
             class_required or None, task_type, agent_name,
             requirement_id, req_path, now, now),
        )
        task_id = cursor.lastrowid
        _log_transition(cursor, task_id, None, "open", agent_name, now)
        conn.commit()

        result: dict[str, object] = {"status": "created", "task_id": task_id, "title": title, "task_type": task_type}
        if blocked_by_str:
            result["blocked_by"] = blocker_ids
        if class_required:
            result["class_required"] = class_required
        # Echo the enrolled flow and first stages
        try:
            from minion.tasks.loader import load_flow
            flow = load_flow(task_type)
            stages = [s.name for s in flow.stages]
            result["flow"] = task_type
            result["dag"] = " → ".join(stages[:4]) + (" → ..." if len(stages) > 4 else "")
        except (ImportError, KeyError, ValueError):
            pass  # SU-17: narrowed — flow loader may not find the flow type
        return result
    finally:
        conn.close()


def assign_task(agent_name: str, task_id: int, assigned_to: str) -> dict[str, object]:
    conn = get_db()
    cursor = conn.cursor()
    now = now_iso()
    try:
        # moon_crash blocks assignments
        cursor.execute("SELECT value, set_by, set_at FROM flags WHERE key = 'moon_crash'")
        mc_row = cursor.fetchone()
        if mc_row and mc_row["value"] == "1":
            return {"error": f"BLOCKED: moon_crash active — no new assignments. (set by {mc_row['set_by']} at {mc_row['set_at']})"}

        cursor.execute("SELECT agent_class FROM agents WHERE name = ?", (agent_name,))
        row = cursor.fetchone()
        if not row:
            return {"error": f"BLOCKED: Agent '{agent_name}' not registered."}
        if row["agent_class"] != "lead":
            return {"error": f"BLOCKED: Only lead-class agents can assign tasks. '{agent_name}' is '{row['agent_class']}'."}

        cursor.execute("SELECT name FROM agents WHERE name = ?", (assigned_to,))
        if not cursor.fetchone():
            return {"error": f"BLOCKED: Agent '{assigned_to}' not registered."}

        cursor.execute("SELECT id, status, flow_type FROM tasks WHERE id = ?", (task_id,))
        task_row = cursor.fetchone()
        if not task_row:
            return {"error": f"Task #{task_id} not found."}

        task_type = task_row["flow_type"] or "bugfix"
        flow = _get_flow(task_type)
        if flow and flow.is_terminal(task_row["status"]):
            return {"error": f"BLOCKED: Task #{task_id} is in terminal status '{task_row['status']}'."}

        cursor.execute("SELECT title FROM tasks WHERE id = ?", (task_id,))
        title_row = cursor.fetchone()
        task_title = title_row["title"] if title_row else f"T{task_id}"

        current_status = task_row["status"]
        # At review stages (workers defined = handoff point), only reassign — don't reset status
        review_stage = False
        if flow:
            workers = flow.workers_for(current_status, "")
            if workers is not None:
                review_stage = True

        if review_stage:
            cursor.execute(
                "UPDATE tasks SET assigned_to = ?, updated_at = ? WHERE id = ?",
                (assigned_to, now, task_id),
            )
        else:
            cursor.execute(
                "UPDATE tasks SET assigned_to = ?, status = 'assigned', updated_at = ? WHERE id = ?",
                (assigned_to, now, task_id),
            )
            _log_transition(cursor, task_id, current_status, "assigned", assigned_to, now)
        # Update agent status to busy so dashboard reflects the assignment
        cursor.execute(
            "UPDATE agents SET status = 'busy', last_seen = ? WHERE name = ?",
            (now, assigned_to),
        )
        conn.commit()
        update_pane_task(assigned_to, f"T{task_id}: {task_title}")
        return {"status": "assigned", "task_id": task_id, "assigned_to": assigned_to}
    finally:
        conn.close()
