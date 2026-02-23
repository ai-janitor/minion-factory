"""Write test reports and advance task phase."""

from __future__ import annotations

import os

from minion.db import _get_db_path


def create_test_report(
    agent_name: str,
    task_id: int,
    passed: bool,
    output: str = "",
    notes: str = "",
) -> dict[str, object]:
    """Write a test report to .work/test-reports/ and advance the task phase."""
    from minion.tasks.update_task import complete_phase

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
