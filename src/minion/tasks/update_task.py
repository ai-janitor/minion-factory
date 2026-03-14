"""Update task state and complete DAG phases."""

from __future__ import annotations

from minion.db import get_db, now_iso, staleness_check
from minion.crew import update_pane_task
from ._helpers import _get_flow, _log_transition


def update_task(
    agent_name: str,
    task_id: int,
    status: str = "",
    progress: str = "",
    files: str = "",
    checklist: str = "",
) -> dict[str, object]:
    # Precondition assertions — backlog #63
    assert agent_name, "agent_name must not be empty"
    assert isinstance(task_id, int) and task_id > 0, f"task_id must be a positive int, got {task_id}"

    conn = get_db()
    cursor = conn.cursor()
    now = now_iso()
    try:
        cursor.execute("SELECT name FROM agents WHERE name = ?", (agent_name,))
        if not cursor.fetchone():
            return {"error": f"BLOCKED: Agent '{agent_name}' not registered."}

        cursor.execute(
            "SELECT id, status, activity_count, title, assigned_to, result_file, flow_type, files FROM tasks WHERE id = ?",
            (task_id,),
        )
        task_row = cursor.fetchone()
        if not task_row:
            return {"error": f"Task #{task_id} not found."}

        task_type = task_row["flow_type"] or "bugfix"
        flow = _get_flow(task_type)

        if flow and flow.is_terminal(task_row["status"]):
            return {"error": f"BLOCKED: Task #{task_id} is in terminal status '{task_row['status']}'."}

        if status:
            if flow:
                if status not in flow.stages:
                    return {"error": f"Invalid status '{status}'. Valid: {', '.join(sorted(flow.stages.keys()))}"}
                if flow.is_terminal(status):
                    return {"error": f"BLOCKED: Cannot set status to '{status}' via update-task. Use close-task."}
            elif status not in {"open", "assigned", "in_progress", "fixed", "verified", "findings_ready", "assessed", "closed"}:
                return {"error": f"Invalid status '{status}'."}

        current_status = task_row["status"]

        # --- DAG transition enforcement — block stage skipping (checked first) ---
        # Agents MUST advance through declared next: stages in order.
        # valid_transitions() returns the set of allowed next statuses for the
        # current stage (including dead_ends and alt_next). Any jump outside
        # this set is a skip and must be rejected hard — not warned.
        # This check runs BEFORE the checklist gate: a transition that's invalid
        # for the DAG should be rejected immediately, not with a misleading
        # "write a checklist first" message.
        if status and flow:
            valid_next = flow.valid_transitions(current_status)
            if status not in valid_next:
                return {
                    "error": (
                        f"BLOCKED: Cannot transition from '{current_status}' to '{status}'. "
                        f"Valid next stages: {sorted(valid_next)}. "
                        "Advance through each stage in order — use complete-phase to route automatically."
                    )
                }

        # --- Checklist gate: transitioning to in_progress requires --checklist ---
        # Mechanical enforcement: agents MUST register a checklist file before
        # the system lets them claim they're working. Without this, agents skip
        # writing CHECKLIST.md and go straight to coding.
        if status == "in_progress":
            if not checklist:
                return {
                    "error": "BLOCKED: Transition to in_progress requires --checklist <path>. "
                    "Write your checklist first, then register it."
                }
            import os as _os
            checklist_path = checklist
            if not _os.path.isabs(checklist_path):
                project_root = _os.environ.get("MINION_PROJECT_DIR", _os.getcwd())
                checklist_path = _os.path.join(project_root, checklist_path)
            if not _os.path.isfile(checklist_path):
                return {
                    "error": f"BLOCKED: Checklist file not found: {checklist}. "
                    "Create the file first, then register it."
                }

        warnings: list[str] = []

        if status:

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
        if checklist:
            fields.append("checklist_path = ?")
            params.append(checklist)

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
    # Precondition assertions — backlog #63
    assert agent_name, "agent_name must not be empty"
    assert isinstance(task_id, int) and task_id > 0, f"task_id must be a positive int, got {task_id}"

    conn = get_db()
    cursor = conn.cursor()
    now = now_iso()
    try:
        cursor.execute("SELECT name, agent_class FROM agents WHERE name = ?", (agent_name,))
        agent_row = cursor.fetchone()
        if not agent_row:
            return {"error": f"BLOCKED: Agent '{agent_name}' not registered."}
        agent_class = agent_row["agent_class"]

        cursor.execute(
            "SELECT id, status, flow_type, class_required, assigned_to, title FROM tasks WHERE id = ?",
            (task_id,),
        )
        task_row = cursor.fetchone()
        if not task_row:
            return {"error": f"Task #{task_id} not found."}

        task_type = task_row["flow_type"] or "bugfix"
        current = task_row["status"]
        class_required = task_row["class_required"] or ""

        flow = _get_flow(task_type)
        if flow.is_terminal(current):
            return {"error": f"Task #{task_id} is already in terminal status '{current}'."}

        # DAG enforcement: verify agent's class is eligible to work the CURRENT stage
        eligible_current = flow.workers_for(current, class_required)
        if eligible_current is not None and agent_class not in eligible_current:
            return {
                "error": f"BLOCKED: Agent '{agent_name}' (class '{agent_class}') cannot complete "
                f"stage '{current}'. Eligible classes: {eligible_current}. "
                f"This stage requires a different agent."
            }

        # --- SU-03: Self-review bypass prevention ---
        # If current stage requires reviewer classes, block the implementer from self-reviewing.
        # Lead class bypasses this check (trusted to self-review when necessary).
        if agent_class != "lead":
            current_stage_obj = flow.stages.get(current)
            if current_stage_obj and current_stage_obj.workers is not None:
                # Check if this is a review-type stage (workers are reviewer classes)
                eligible_workers = flow.workers_for(current, class_required)
                # Look for who last advanced this task — query transition_log
                implementer_row = cursor.execute(
                    "SELECT triggered_by FROM transition_log "
                    "WHERE entity_id = ? AND entity_type = 'task' AND triggered_by IS NOT NULL AND triggered_by != '' "
                    "ORDER BY created_at DESC LIMIT 1",
                    (task_id,),
                ).fetchone()
                if implementer_row and implementer_row["triggered_by"] == agent_name:
                    # Agent was the last to work on it — block self-review if eligible
                    if eligible_workers is not None and agent_class in (eligible_workers or []):
                        return {
                            "error": f"BLOCKED: Agent '{agent_name}' was the last to advance this task "
                            f"and cannot self-review stage '{current}'. Assign a different reviewer."
                        }

        # --- SU-21: Scaffolding gate enforcement ---
        # If current stage has gate: "scaffolding", verify listed files exist on disk.
        # Lead class bypasses this check. Empty files field = skip with warning.
        current_stage_obj_for_gate = flow.stages.get(current)
        if current_stage_obj_for_gate and current_stage_obj_for_gate.gate == "scaffolding":
            # Read task's files field
            cursor.execute("SELECT files FROM tasks WHERE id = ?", (task_id,))
            files_row = cursor.fetchone()
            files_field = (files_row["files"] or "") if files_row else ""
            if files_field.strip():
                import os as _os
                file_paths = [f.strip() for f in files_field.split(",") if f.strip()]
                project_root = _os.environ.get("MINION_PROJECT_DIR", _os.getcwd())
                missing = []
                for fp in file_paths:
                    abs_path = _os.path.join(project_root, fp) if not _os.path.isabs(fp) else fp
                    if not _os.path.exists(abs_path):
                        missing.append(fp)
                if missing and agent_class != "lead":
                    return {
                        "error": f"BLOCKED: Scaffolding incomplete. Missing files: {missing}. "
                        f"Create stubs before advancing."
                    }
                # Lead bypass or all files present — proceed

        # DAG decides next status — no fallback
        new_status = flow.next_status(current, passed)

        if new_status is None:
            # Show valid transitions so the agent knows what's possible
            valid = []
            for p in (True, False):
                ns = flow.next_status(current, p)
                if ns:
                    valid.append(f"passed={p} → {ns}")
            hint = f" Valid transitions from '{current}': {', '.join(valid)}" if valid else ""
            return {"error": f"No transition from '{current}' (passed={passed}) in flow '{task_type}'.{hint}"}

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
        # --- SU-06: Poll reminder after phase completion ---
        result["poll_reminder"] = f"Run: minion poll --agent {agent_name}"
        return result
    finally:
        conn.close()
