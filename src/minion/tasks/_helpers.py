"""Shared helpers for task CRUD operations."""

from __future__ import annotations

import sqlite3
from typing import Any

from .loader import load_flow

# Cache loaded flows
_flow_cache: dict[str, Any] = {}


def _get_flow(task_type: str = "bugfix") -> Any:
    """Load and cache a TaskFlow. Hard fail if unavailable."""
    if task_type in _flow_cache:
        return _flow_cache[task_type]
    flow = load_flow(task_type)
    _flow_cache[task_type] = flow
    return flow


def task_past_gate(task_id: int, gate_name: str = "scaffolding", conn: sqlite3.Connection | None = None) -> bool:
    """Check if a task has reached or passed the stage with the given gate.

    Returns True if:
    - The task's flow has no such gate (no enforcement needed)
    - The task's current status is at or past the gated stage
    """
    close_conn = False
    if conn is None:
        from minion.db import get_db
        conn = get_db()
        close_conn = True
    try:
        row = conn.execute(
            "SELECT status, flow_type FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if row is None:
            return True  # task not found = no enforcement
        flow_type = row["flow_type"] if "flow_type" in row.keys() else row.get("task_type", "bugfix")
        flow = _get_flow(flow_type)
        return flow.past_gate(row["status"], gate_name)
    finally:
        if close_conn:
            conn.close()


def agent_past_scaffolding(agent_name: str, conn: sqlite3.Connection | None = None) -> tuple[bool, list[int]]:
    """Check if ALL of an agent's in-progress tasks have passed scaffolding.

    Returns (all_past, blocking_task_ids) where blocking_task_ids are tasks
    that have NOT passed the scaffolding gate.
    """
    close_conn = False
    if conn is None:
        from minion.db import get_db
        conn = get_db()
        close_conn = True
    try:
        rows = conn.execute(
            "SELECT id, status, flow_type FROM tasks WHERE assigned_to = ? AND status NOT IN ('closed', 'abandoned', 'stale', 'obsolete')",
            (agent_name,),
        ).fetchall()
        blocking: list[int] = []
        for row in rows:
            flow_type = row["flow_type"] if "flow_type" in row.keys() else row.get("task_type", "bugfix")
            flow = _get_flow(flow_type)
            if flow.has_gate("scaffolding") and not flow.past_gate(row["status"], "scaffolding"):
                blocking.append(row["id"])
        return (len(blocking) == 0, blocking)
    finally:
        if close_conn:
            conn.close()


def _log_transition(cursor: sqlite3.Cursor, task_id: int, from_status: str | None, to_status: str, agent: str, timestamp: str) -> None:
    """Record a status transition in transition_log."""
    # Precondition assertions — backlog #63
    assert cursor is not None, "cursor must not be None"
    assert isinstance(task_id, int) and task_id > 0, f"task_id must be a positive int, got {task_id}"
    assert to_status, "to_status must not be empty"
    assert agent, "agent must not be empty"
    assert timestamp, "timestamp must not be empty"

    cursor.execute(
        "INSERT INTO transition_log (entity_id, entity_type, from_status, to_status, triggered_by, created_at) VALUES (?, 'task', ?, ?, ?, ?)",
        (task_id, from_status, to_status, agent, timestamp),
    )
