"""Task System — create, assign, update, list, get, submit_result, close."""

from __future__ import annotations

import os
from typing import Any

import sqlite3

from minion.db import get_db, now_iso, staleness_check
from .loader import load_flow, list_flows as _list_flows

# Cache loaded flows
_flow_cache: dict[str, Any] = {}

def _get_flow(task_type: str = "bugfix") -> Any | None:
    """Load and cache a TaskFlow, or return None if unavailable."""
    if task_type in _flow_cache:
        return _flow_cache[task_type]
    try:
        flow = load_flow(task_type)
        _flow_cache[task_type] = flow
        return flow
    except (FileNotFoundError, ValueError) as exc:
        import sys
        print(f"WARNING: task flow '{task_type}' failed to load: {exc}", file=sys.stderr)
        _flow_cache[task_type] = None
        return None

def _log_transition(cursor: sqlite3.Cursor, task_id: int, from_status: str | None, to_status: str, agent: str, timestamp: str) -> None:
    """Record a status transition in task_history."""
    cursor.execute(
        "INSERT INTO task_history (task_id, from_status, to_status, agent, timestamp) VALUES (?, ?, ?, ?, ?)",
        (task_id, from_status, to_status, agent, timestamp),
    )

def create_task(
    agent_name: str,
    title: str,
    task_file: str,
    project: str = "",
    zone: str = "",
    blocked_by: str = "",
    class_required: str = "",
    task_type: str = "bugfix",
) -> dict[str, object]:
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
        if cursor.fetchone()[0] == 0 and task_type != "chore":
            return {"error": "BLOCKED: No active battle plan. Lead must call set-battle-plan first."}

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

        cursor.execute(
            """INSERT INTO tasks
               (title, task_file, project, zone, status, blocked_by,
                class_required, task_type, created_by, activity_count, created_at, updated_at)
               VALUES (?, ?, ?, ?, 'open', ?, ?, ?, ?, 0, ?, ?)""",
            (title, task_file, project or None, zone or None, blocked_by_str,
             class_required or None, task_type, agent_name, now, now),
        )
        task_id = cursor.lastrowid
        _log_transition(cursor, task_id, None, "open", agent_name, now)
        conn.commit()

        result: dict[str, object] = {"status": "created", "task_id": task_id, "title": title, "task_type": task_type}
        if blocked_by_str:
            result["blocked_by"] = blocker_ids
        if class_required:
            result["class_required"] = class_required
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

        cursor.execute("SELECT id, status, task_type FROM tasks WHERE id = ?", (task_id,))
        task_row = cursor.fetchone()
        if not task_row:
            return {"error": f"Task #{task_id} not found."}
        
        task_type = task_row["task_type"] or "bugfix"
        flow = _get_flow(task_type)
        if flow and flow.is_terminal(task_row["status"]):
            return {"error": f"BLOCKED: Task #{task_id} is in terminal status '{task_row['status']}'."}

        cursor.execute(
            "UPDATE tasks SET assigned_to = ?, status = 'assigned', updated_at = ? WHERE id = ?",
            (assigned_to, now, task_id),
        )
        _log_transition(cursor, task_id, task_row["status"], "assigned", assigned_to, now)
        conn.commit()
        return {"status": "assigned", "task_id": task_id, "assigned_to": assigned_to}
    finally:
        conn.close()


def update_task(
    agent_name: str,
    task_id: int,
    status: str = "",
    progress: str = "",
    files: str = "",
) -> dict[str, object]:
    conn = get_db()
    cursor = conn.cursor()
    now = now_iso()
    try:
        cursor.execute("SELECT name FROM agents WHERE name = ?", (agent_name,))
        if not cursor.fetchone():
            return {"error": f"BLOCKED: Agent '{agent_name}' not registered."}

        cursor.execute(
            "SELECT id, status, activity_count, title, assigned_to, result_file, task_type, files FROM tasks WHERE id = ?",
            (task_id,),
        )
        task_row = cursor.fetchone()
        if not task_row:
            return {"error": f"Task #{task_id} not found."}

        task_type = task_row["task_type"] or "bugfix"
        flow = _get_flow(task_type)

        if flow and flow.is_terminal(task_row["status"]):
            return {"error": f"BLOCKED: Task #{task_id} is in terminal status '{task_row['status']}'."}

        if status:
            if flow:
                if status not in flow.stages:
                    return {"error": f"Invalid status '{status}'. Valid: {', '.join(sorted(flow.stages.keys()))}"}
                if flow.is_terminal(status):
                    return {"error": f"BLOCKED: Cannot set status to '{status}' via update-task. Use close-task."}
            elif status not in {"open", "assigned", "in_progress", "fixed", "verified", "closed"}:
                return {"error": f"Invalid status '{status}'."}

        current_status = task_row["status"]
        warnings: list[str] = []

        if status:
            # Transition validation — warn but allow
            if flow:
                valid_next = flow.valid_transitions(current_status)
                if status not in valid_next:
                    warnings.append(f"Skipped steps — went from {current_status} to {status}")

            # Ownership warning — agent updating a task assigned to someone else
            assigned = task_row["assigned_to"]
            if assigned and assigned != agent_name:
                warnings.append(f"Ownership: task assigned to {assigned}, updated by {agent_name}")

            # Result file warning — setting fixed without submit_result
            if status == "fixed" and not task_row["result_file"]:
                warnings.append("Setting fixed without submit_result — result file required before close")

        fields = ["activity_count = activity_count + 1", "updated_at = ?"]
        params: list[str | int] = [now]

        if status:
            fields.append("status = ?")
            params.append(status)
        if progress:
            fields.append("progress = ?")
            params.append(progress)
        if files:
            fields.append("files = ?")
            params.append(files)

        params.append(task_id)
        cursor.execute(f"UPDATE tasks SET {', '.join(fields)} WHERE id = ?", params)

        if status:
            _log_transition(cursor, task_id, current_status, status, agent_name, now)

        cursor.execute("SELECT activity_count FROM tasks WHERE id = ?", (task_id,))
        new_count = cursor.fetchone()["activity_count"]

        cursor.execute("UPDATE agents SET last_seen = ? WHERE name = ?", (now, agent_name))
        conn.commit()

        result: dict[str, object] = {
            "status": "updated",
            "task_id": task_id,
            "activity_count": new_count,
        }
        if status:
            result["new_status"] = status
        if warnings:
            result["transition_warning"] = "; ".join(warnings)
        if new_count >= 4:
            result["warning"] = f"Activity count at {new_count} — this fight is dragging. Consider reassessing."

        # Nudge: when transitioning to in_progress, remind agent to claim files
        if status == "in_progress":
            task_files = task_row["files"]
            if task_files:
                result["claim_reminder"] = (
                    f"Claim files before editing: "
                    + " ".join(f"minion claim-file --agent {agent_name} --file {f.strip()}" for f in task_files.split(",") if f.strip())
                )
            else:
                result["claim_reminder"] = f"Claim files before editing: minion claim-file --agent {agent_name} --file <path>"

        _, stale_msg = staleness_check(cursor, agent_name)
        if stale_msg:
            result["staleness_warning"] = stale_msg.replace("BLOCKED: ", "")

        return result
    finally:
        conn.close()


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
        return {"task": dict(row)}
    finally:
        conn.close()


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


def close_task(agent_name: str, task_id: int) -> dict[str, object]:
    conn = get_db()
    cursor = conn.cursor()
    now = now_iso()
    try:
        cursor.execute("SELECT agent_class FROM agents WHERE name = ?", (agent_name,))
        row = cursor.fetchone()
        if not row:
            return {"error": f"BLOCKED: Agent '{agent_name}' not registered."}
        cursor.execute("SELECT id, status, result_file, title, task_type, assigned_to FROM tasks WHERE id = ?", (task_id,))
        task_row = cursor.fetchone()
        if not task_row:
            return {"error": f"Task #{task_id} not found."}

        task_type = task_row["task_type"] or "bugfix"
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
            "SELECT id, status, task_type, title, assigned_to FROM tasks WHERE id = ?",
            (task_id,),
        )
        task_row = cursor.fetchone()
        if not task_row:
            return {"error": f"Task #{task_id} not found."}

        task_type = task_row["task_type"] or "bugfix"
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


def complete_phase(agent_name: str, task_id: int, passed: bool = True, reason: str | None = None) -> dict[str, object]:
    """Complete your phase — DAG decides next status and routing."""
    conn = get_db()
    cursor = conn.cursor()
    now = now_iso()
    try:
        cursor.execute("SELECT name FROM agents WHERE name = ?", (agent_name,))
        if not cursor.fetchone():
            return {"error": f"BLOCKED: Agent '{agent_name}' not registered."}

        cursor.execute(
            "SELECT id, status, task_type, class_required, assigned_to, title FROM tasks WHERE id = ?",
            (task_id,),
        )
        task_row = cursor.fetchone()
        if not task_row:
            return {"error": f"Task #{task_id} not found."}

        task_type = task_row["task_type"] or "bugfix"
        current = task_row["status"]
        class_required = task_row["class_required"] or ""

        flow = _get_flow(task_type)
        if flow and flow.is_terminal(current):
            return {"error": f"Task #{task_id} is already in terminal status '{current}'."}

        # DAG decides next status
        if flow:
            new_status = flow.next_status(current, passed)
        else:
            # Fallback linear pipeline
            _linear = {
                "open": "assigned",
                "assigned": "in_progress",
                "in_progress": "fixed",
                "fixed": "verified",
                "verified": "closed",
            }
            if not passed:
                new_status = "assigned" if current in ("fixed", "verified") else None
            else:
                new_status = _linear.get(current)

        if new_status is None:
            return {"error": f"No transition from '{current}' (passed={passed}) in flow '{task_type}'."}

        # Blocked requires a reason so lead can act on it
        if new_status == "blocked" and not reason:
            return {"error": "BLOCKED transition requires --reason explaining why you're stuck."}

        # Who works on the next stage?
        eligible = flow.workers_for(new_status, class_required) if flow else None

        # Update task
        fields = ["status = ?", "updated_at = ?", "activity_count = activity_count + 1"]
        params: list[object] = [new_status, now]

        # Write block reason to progress field
        if new_status == "blocked" and reason:
            fields.append("progress = ?")
            params.append(f"BLOCKED: {reason}")

        # If next stage needs a different worker class, clear assignment for re-pull
        if eligible is not None:
            fields.append("assigned_to = NULL")

        params.append(task_id)
        cursor.execute(f"UPDATE tasks SET {', '.join(fields)} WHERE id = ?", params)

        _log_transition(cursor, task_id, current, new_status, agent_name, now)

        cursor.execute("UPDATE agents SET last_seen = ? WHERE name = ?", (now, agent_name))
        conn.commit()

        result: dict[str, object] = {
            "status": "completed",
            "task_id": task_id,
            "title": task_row["title"],
            "from_status": current,
            "to_status": new_status,
        }
        if eligible is not None:
            result["eligible_classes"] = eligible
        if flow and flow.is_terminal(new_status):
            result["terminal"] = True
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
            "SELECT from_status, to_status, agent, timestamp FROM task_history WHERE task_id = ? ORDER BY timestamp ASC",
            (task_id,),
        )
        history = [dict(r) for r in cursor.fetchall()]

        # Flow stages for this task type
        flow = _get_flow(task_type)
        stages = sorted(flow.stages.keys()) if flow else ["open", "assigned", "in_progress", "fixed", "verified", "closed"]

        return {
            "task": task,
            "history": history,
            "flow_type": task_type,
            "flow_stages": stages,
        }
    finally:
        conn.close()

def list_flows() -> list[str]:
    """List available task flow names."""
    try:
        return _list_flows()
    except Exception as exc:
        import sys
        print(f"WARNING: list_flows failed: {exc}", file=sys.stderr)
        return ["bugfix"]
