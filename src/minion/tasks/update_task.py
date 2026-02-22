"""Update task state and complete DAG phases."""

from __future__ import annotations

from minion.db import get_db, now_iso, staleness_check
from minion.crew._tmux import update_pane_task
from ._helpers import _get_flow, _log_transition


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
        if flow.is_terminal(current):
            return {"error": f"Task #{task_id} is already in terminal status '{current}'."}

        # DAG decides next status — no fallback
        new_status = flow.next_status(current, passed)

        if new_status is None:
            return {"error": f"No transition from '{current}' (passed={passed}) in flow '{task_type}'."}

        # Blocked requires a reason so lead can act on it
        if new_status == "blocked" and not reason:
            return {"error": "BLOCKED transition requires --reason explaining why you're stuck."}

        # Who works on the next stage?
        eligible = flow.workers_for(new_status, class_required)

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

        # Clear pane task label when agent is done with this phase
        if eligible is not None or (flow and flow.is_terminal(new_status)):
            update_pane_task(agent_name)

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
