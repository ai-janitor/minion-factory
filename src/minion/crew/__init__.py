"""Crew — spawn, stand down, retire, stop, hand off, logs, tmux pane management."""

from minion.crew._tmux import update_pane_task
from minion.crew.config import AgentConfig, SwarmConfig, load_config
from minion.crew.lifecycle import hand_off_zone, interrupt_agent, retire_agent, stand_down, stop_agent_process
from minion.crew.logs import tail_agent_log
from minion.crew.recruit import recruit_agent
from minion.crew.spawn import list_crews, spawn_party

__all__ = [
    "AgentConfig",
    "SwarmConfig",
    "hand_off_zone",
    "interrupt_agent",
    "list_crews",
    "load_config",
    "merge_crew_context",
    "recruit_agent",
    "retire_agent",
    "spawn_party",
    "stand_down",
    "stop_agent_process",
    "tail_agent_log",
    "update_pane_task",
]


def merge_crew_context(crew: str, agent_name: str) -> dict[str, object]:
    """Extract agent context (zone, capabilities, system prompt) from a crew YAML.

    Returns a dict with keys: crew, zone, capabilities, system_prompt_excerpt,
    crew_warning, crew_error — depending on what was found.
    This function is called by comms/register.py to avoid crew logic in comms.
    """
    result: dict[str, object] = {}
    from minion.crew.spawn import _find_crew_file

    crew_file = _find_crew_file(crew)
    if not crew_file:
        result["crew_warning"] = f"Crew '{crew}' not found — skipping crew context"
        return result

    try:
        crew_cfg = load_config(crew_file)
        agent_cfg = crew_cfg.agents.get(agent_name)
        if not agent_cfg:
            result["crew_error"] = (
                f"Agent '{agent_name}' not found in crew '{crew}'. "
                f"Available: {', '.join(sorted(crew_cfg.agents.keys()))}"
            )
        else:
            result["crew"] = crew
            if agent_cfg.zone:
                result["zone"] = agent_cfg.zone
            if agent_cfg.capabilities:
                result["capabilities"] = list(agent_cfg.capabilities)
            if agent_cfg.system:
                result["system_prompt_excerpt"] = agent_cfg.system[:200]
    except Exception as exc:
        result["crew_error"] = f"Failed to load crew '{crew}': {exc}"

    return result
