"""Block a task — write block report and transition to blocked status."""

from __future__ import annotations

import os

from minion.db import get_runtime_dir, now_iso
from minion.tasks.update_task import update_task


def block_task(
    agent_name: str,
    task_id: int,
    reason: str,
) -> dict[str, object]:
    """Write a block report to .work/blocks/ and transition task to blocked."""
    work_dir = get_runtime_dir()
    blocks_dir = os.path.join(work_dir, "blocks")
    os.makedirs(blocks_dir, exist_ok=True)

    timestamp = now_iso()
    report_path = os.path.join(blocks_dir, f"TASK-{task_id}-block.md")

    report = (
        f"## Block Report for Task #{task_id}\n"
        f"\n"
        f"**Reason:** {reason}\n"
        f"\n"
        f"**Blocked by:** {agent_name}\n"
        f"\n"
        f"**Date:** {timestamp}\n"
    )

    with open(report_path, "w") as f:
        f.write(report)

    # Transition task to blocked status
    update_result = update_task(agent_name, task_id, status="blocked")

    return {
        "status": "blocked",
        "task_id": task_id,
        "block_report": report_path,
        "reason": reason,
        "agent": agent_name,
        "timestamp": timestamp,
        "update_result": update_result,
    }
