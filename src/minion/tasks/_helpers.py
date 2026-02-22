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


def _log_transition(cursor: sqlite3.Cursor, task_id: int, from_status: str | None, to_status: str, agent: str, timestamp: str) -> None:
    """Record a status transition in transition_log."""
    cursor.execute(
        "INSERT INTO transition_log (entity_id, entity_type, from_status, to_status, triggered_by, created_at) VALUES (?, 'task', ?, ?, ?, ?)",
        (task_id, from_status, to_status, agent, timestamp),
    )
