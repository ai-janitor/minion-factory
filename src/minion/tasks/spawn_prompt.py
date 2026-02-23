"""Assemble a complete spawn-ready prompt for an agent + task."""

from __future__ import annotations

from typing import Any

from minion.auth import get_tools_for_class
from minion.crew.config import get_agent_prompt
from minion.tasks.query_task import get_task


def get_spawn_prompt(task_id: int, agent_name: str, crew_name: str) -> dict[str, Any]:
    """Combine crew YAML agent config, task content, and onboarding tools.

    Returns a dict with all fields needed to spawn an agent session,
    or an error dict if the task or agent cannot be resolved.
    """
    # Resolve agent config from crew YAML
    agent_cfg = get_agent_prompt(agent_name, crew_name)
    if "error" in agent_cfg:
        return agent_cfg

    # Resolve task content from DB
    task_data = get_task(task_id)
    if "error" in task_data:
        return task_data

    task = task_data["task"]
    title = task.get("title", "")

    # Build task briefing from available content
    sections = [f"# Task #{task_id}: {title}"]

    task_content = task_data.get("task_content")
    if task_content:
        sections.append(task_content)

    req_content = task_data.get("requirement_content")
    if req_content:
        sections.append(f"## Requirement\n{req_content}")

    flow_position = task_data.get("flow_position")
    if flow_position:
        sections.append(f"## Flow Position\n{flow_position}")

    task_briefing = "\n\n".join(sections)

    # Resolve tools for this agent's role
    tools = get_tools_for_class(agent_cfg["role"])

    return {
        "system_prompt": agent_cfg["system"],
        "task_briefing": task_briefing,
        "tools": tools,
        "model": agent_cfg.get("model"),
        "allowed_tools": agent_cfg.get("allowed_tools"),
        "permission_mode": agent_cfg.get("permission_mode"),
        "task_id": task_id,
        "agent_name": agent_name,
        "crew_name": crew_name,
    }
