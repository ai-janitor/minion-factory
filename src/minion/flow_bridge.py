"""Bridge to task DAG engine — all queries route through YAML-defined flows.

No fallbacks. Missing YAML = hard failure.
"""

from __future__ import annotations

from typing import Any

from minion.tasks import TaskFlow, list_flows as _mt_list_flows, load_flow as _mt_load_flow

# Cache loaded flows so we don't re-parse YAML every call
_flow_cache: dict[str, Any] = {}


def _get_flow(task_type: str = "bugfix") -> TaskFlow:
    """Load and cache a TaskFlow. Hard fail if unavailable."""
    if task_type in _flow_cache:
        return _flow_cache[task_type]
    flow = _mt_load_flow(task_type)
    _flow_cache[task_type] = flow
    return flow


# -- Terminal statuses (closed, abandoned, etc.) --

def is_terminal(status: str, task_type: str = "bugfix") -> bool:
    """Is this status terminal (no further transitions)?"""
    return _get_flow(task_type).is_terminal(status)


def is_dead_end(status: str, task_type: str = "bugfix") -> bool:
    """Is this a dead-end status (abandoned/stale/obsolete)?"""
    return status in _get_flow(task_type).dead_ends


# -- Status sets --

def all_statuses(task_type: str = "bugfix") -> set[str]:
    """All known statuses for this flow type."""
    return set(_get_flow(task_type).stages.keys())


def active_statuses(task_type: str = "bugfix") -> tuple[str, ...]:
    """Non-terminal, non-dead-end statuses (what agents actively work on)."""
    flow = _get_flow(task_type)
    return tuple(
        name for name, stage in flow.stages.items()
        if not stage.terminal and not stage.parked and name not in flow.dead_ends
    )


# -- Transitions --

def valid_transitions(current: str, task_type: str = "bugfix") -> set[str] | None:
    """Valid next statuses from current. None if current is unknown/terminal."""
    result = _get_flow(task_type).valid_transitions(current)
    return result if result else None


def next_status(current: str, task_type: str = "bugfix", passed: bool = True) -> str | None:
    """DAG-driven next status. Returns None if terminal/unknown."""
    return _get_flow(task_type).next_status(current, passed)


# -- Worker routing --

def workers_for(status: str, class_required: str, task_type: str = "bugfix") -> list[str] | None:
    """Which agent classes can work on this stage? None = current assignee continues."""
    return _get_flow(task_type).workers_for(status, class_required)


# -- Flow discovery --

def available_flows() -> list[str]:
    """List available flow type names."""
    return _mt_list_flows()
