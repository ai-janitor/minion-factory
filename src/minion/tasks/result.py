"""Create a result file for a task and submit it in one step."""

from __future__ import annotations

import os

from minion.db import get_runtime_dir
from minion.tasks.submit_result import submit_result
from minion.tasks.update_task import complete_phase


def create_result(
    agent_name: str,
    task_id: int,
    summary: str,
    files_changed: str = "",
    notes: str = "",
) -> dict[str, object]:
    """Write a result markdown file and submit it via submit_result().

    Resolves .work/ from the DB path, creates .work/results/ if needed,
    writes TASK-{task_id}-result.md, then delegates to submit_result().
    """
    work_dir = get_runtime_dir()
    results_dir = os.path.join(work_dir, "results")
    os.makedirs(results_dir, exist_ok=True)

    result_file = os.path.join(results_dir, f"TASK-{task_id}-result.md")

    lines = [f"# Result — Task #{task_id}\n"]

    lines.append("## Summary\n")
    lines.append(f"{summary}\n")

    lines.append("## Files Changed\n")
    if files_changed.strip():
        for f in files_changed.split(","):
            f = f.strip()
            if f:
                lines.append(f"- `{f}`")
        lines.append("")
    else:
        lines.append("_None specified._\n")

    lines.append("## Notes\n")
    if notes.strip():
        lines.append(f"{notes}\n")
    else:
        lines.append("_No additional notes._\n")

    with open(result_file, "w") as fh:
        fh.write("\n".join(lines))

    result = submit_result(agent_name, task_id, result_file)

    # Advance task through the DAG after submitting the result
    if "error" not in result:
        try:
            phase_result = complete_phase(agent_name, task_id, passed=True)
            if "error" in phase_result:
                result["phase_warning"] = phase_result["error"]
            else:
                result["phase_advanced"] = phase_result.get("new_status", True)
        except Exception as exc:
            result["phase_warning"] = str(exc)

    return result
