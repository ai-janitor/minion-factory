"""Write test reports and advance task phase.

Purpose: Write test reports and advance task phase.
Rationale: Extracted into own module for single-responsibility task management.
Responsibility: Write test reports and advance task phase. NOT responsible for unrelated concerns.
Organization: Standalone functions and/or a single class. See source."""

from __future__ import annotations

import os

from minion.db import _get_db_path, get_db


def create_test_report(
    agent_name: str,
    task_id: int,
    passed: bool,
    output: str = "",
    notes: str = "",
) -> dict[str, object]:
    """Write a test report to .work/test-reports/ and advance the task phase."""
    from minion.tasks.update_task import complete_phase
    from minion.tasks.flow_gates_and_validation import _get_flow

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
                    f"cannot submit test report for task #{task_id} in stage '{task_row['status']}'. "
                    f"Eligible classes: {eligible}."
                }
    finally:
        conn.close()

    # Resolve .work/ dir from DB path
    work_dir = os.path.dirname(_get_db_path())
    reports_dir = os.path.join(work_dir, "test-reports")
    os.makedirs(reports_dir, exist_ok=True)

    result_str = "PASSED" if passed else "FAILED"
    report_path = os.path.join(reports_dir, f"TASK-{task_id}-test.md")

    lines = [
        f"## Test Report for Task #{task_id}",
        "",
        f"**Result:** {result_str}",
        f"**Agent:** {agent_name}",
        "",
    ]

    if output:
        lines += ["## Output", "", "```", output, "```", ""]

    if notes:
        lines += ["## Notes", "", notes, ""]

    with open(report_path, "w") as f:
        f.write("\n".join(lines))

    # Advance phase using the same logic as complete-phase CLI
    phase_result = complete_phase(agent_name, task_id, passed=passed)

    phase_result["test_report"] = report_path
    return phase_result
