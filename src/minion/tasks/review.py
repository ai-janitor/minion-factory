"""Write a review verdict for a task and advance its phase."""

from __future__ import annotations

import os
from pathlib import Path

from minion.db import _get_db_path

from .update_task import complete_phase


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
