"""Write a review verdict for a task and advance its phase.

Purpose: Write a review verdict for a task and advance its phase.
Rationale: Extracted into own module for single-responsibility task management.
Responsibility: Write a review verdict for a task and advance its phase. NOT responsible for unrelated concerns.
Organization: Standalone functions and/or a single class. See source."""

from __future__ import annotations

import os
from pathlib import Path

from minion.db import _get_db_path, get_db

from .update_task import complete_phase
from .flow_gates_and_validation import _get_flow


def create_review(
    agent_name: str,
    task_id: int,
    verdict: str,
    notes: str = "",
) -> dict[str, object]:
    """Write a review file and advance the task phase.

    Verdict "pass" → complete_phase(passed=True),
    verdict "fail" → complete_phase(passed=False).
    """
    if verdict not in ("pass", "fail"):
        return {"error": f"Invalid verdict '{verdict}'. Must be 'pass' or 'fail'."}

    # Pre-check: verify agent's class is eligible for the current stage
    conn = get_db()
    try:
        agent_row = conn.execute("SELECT agent_class FROM agents WHERE name = ?", (agent_name,)).fetchone()
        task_row = conn.execute("SELECT status, flow_type, class_required FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if agent_row and task_row:
            flow = _get_flow(task_row["flow_type"] or "bugfix")
            eligible = flow.workers_for(task_row["status"], task_row["class_required"] or "")
            if eligible is not None and agent_row["agent_class"] not in eligible:
                return {
                    "error": f"BLOCKED: Agent '{agent_name}' (class '{agent_row['agent_class']}') "
                    f"cannot review task #{task_id} in stage '{task_row['status']}'. "
                    f"Eligible classes: {eligible}."
                }
    finally:
        conn.close()

    # Resolve .work/ dir from DB path
    db_path = _get_db_path()
    work_dir = os.path.dirname(db_path)
    reviews_dir = os.path.join(work_dir, "reviews")
    os.makedirs(reviews_dir, exist_ok=True)

    # Write review markdown
    review_path = os.path.join(reviews_dir, f"TASK-{task_id}-review.md")
    lines = [
        f"## Review for Task #{task_id}",
        "",
        f"**Verdict:** {verdict}",
        f"**Reviewer:** {agent_name}",
        "",
    ]
    if notes:
        lines.extend(["## Notes", "", notes, ""])

    Path(review_path).write_text("\n".join(lines))

    # Advance phase via the same backend as complete-phase CLI
    result = complete_phase(agent_name, task_id, passed=(verdict == "pass"))
    result["review_file"] = review_path
    return result
