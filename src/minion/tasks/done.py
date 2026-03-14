"""Fast-close for externally completed tasks.
Bypasses the normal assign/pull/submit-result/close ceremony for work
done outside the minion DAG (worktrees, Claude Code agents, etc.).

Purpose: Fast-close for externally completed tasks.
Rationale: Extracted into own module for single-responsibility task management.
Responsibility: Fast-close for externally completed tasks. NOT responsible for unrelated concerns.
Organization: Standalone functions and/or a single class. See source."""

from __future__ import annotations

import os

from minion.db import get_db, now_iso
from minion.defaults import resolve_work_dir
from ._helpers import _get_flow, _log_transition
from .dag import TERMINAL_STATUSES


def _find_final_advancing_stage(flow) -> str | None:
    """Find the last non-terminal, non-skip, non-parked stage that leads directly to a terminal.

    Walks each stage in the flow. Returns the name of the stage whose resolved
    next_status() is a terminal. This is the "done-ready" stage — the stage a
    task must reach before a lead can fast-close it via task done.

    Returns None if the flow has no such stage (degenerate / all-terminal flow).

    Time complexity: O(S) where S = number of stages.
    """
    for name, stage in flow.stages.items():
        # Skip meta-stages that are not active working stages
        if stage.skip or stage.terminal or stage.parked:
            continue
        # Check if the happy-path next resolves to a terminal
        resolved_next = flow.next_status(name, passed=True)
        if resolved_next is not None and resolved_next in TERMINAL_STATUSES:
            return name
    return None


def done_task(agent_name: str, task_id: int, summary: str = "") -> dict[str, object]:
    conn = get_db()
    cursor = conn.cursor()
    now = now_iso()
    try:
        cursor.execute("SELECT agent_class FROM agents WHERE name = ?", (agent_name,))
        row = cursor.fetchone()
        if not row:
            return {"error": f"BLOCKED: Agent '{agent_name}' not registered."}
        if row["agent_class"] != "lead":
            return {"error": f"BLOCKED: Only lead-class agents can force-close tasks. '{agent_name}' is '{row['agent_class']}'."}

        cursor.execute(
            "SELECT id, status, title, assigned_to, flow_type FROM tasks WHERE id = ?",
            (task_id,),
        )
        task_row = cursor.fetchone()
        if not task_row:
            return {"error": f"Task #{task_id} not found."}

        old_status = task_row["status"]
        if old_status == "closed":
            return {"error": f"Task #{task_id} is already closed."}

        # --- DAG gate: fast-close only allowed from the final pre-terminal stage ---
        # task done is not a shortcut past review/QE/testing. A lead can only invoke
        # it when the task has legitimately reached the last stage before close.
        # Exception: 'open' tasks may be cancelled (no work was started).
        # Exception: terminal statuses are caught above.
        # Exception: dead_end statuses (abandoned, stale, obsolete) are terminal.
        task_type = task_row["flow_type"] or "bugfix"
        flow = _get_flow(task_type)
        if flow and old_status not in TERMINAL_STATUSES and old_status != "open":
            final_stage = _find_final_advancing_stage(flow)
            if final_stage is not None and old_status != final_stage:
                # Build the happy path to show what stages remain
                stages_remaining: list[str] = []
                cursor_stage: str | None = old_status
                visited: set[str] = set()
                while cursor_stage and cursor_stage not in visited and cursor_stage not in TERMINAL_STATUSES:
                    visited.add(cursor_stage)
                    nxt = flow.next_status(cursor_stage, passed=True)
                    if nxt and nxt not in TERMINAL_STATUSES:
                        stages_remaining.append(nxt)
                    cursor_stage = nxt
                hint = f" Remaining stages: {stages_remaining}." if stages_remaining else ""
                return {
                    "error": (
                        f"BLOCKED: Task #{task_id} is at '{old_status}' but must reach "
                        f"'{final_stage}' before fast-close. "
                        f"Use 'minion task complete-phase' to advance through each stage.{hint}"
                    )
                }

        result_file = None
        if summary:
            work_dir = resolve_work_dir()
            results_dir = work_dir / "results"
            results_dir.mkdir(parents=True, exist_ok=True)
            result_file = str(results_dir / f"TASK-{task_id}-result.md")
            with open(result_file, "w") as f:
                f.write(f"# Task #{task_id} Result\n\n{summary}\n")

        updates = "status = 'closed', updated_at = ?"
        params: list[object] = [now]
        if result_file:
            updates += ", result_file = ?"
            params.append(result_file)
        params.append(task_id)

        with conn:
            cursor.execute(f"UPDATE tasks SET {updates} WHERE id = ?", params)
            _log_transition(cursor, task_id, old_status, "closed", agent_name, now)

        result: dict[str, object] = {
            "status": "closed",
            "task_id": task_id,
            "title": task_row["title"],
            "from_status": old_status,
        }
        if result_file:
            result["result_file"] = result_file
        return result
    finally:
        conn.close()
