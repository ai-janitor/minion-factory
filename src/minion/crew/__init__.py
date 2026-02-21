"""Crew — spawn, stand down, retire, stop, hand off, logs."""

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
    "recruit_agent",
    "retire_agent",
    "spawn_party",
    "stand_down",
    "stop_agent_process",
    "tail_agent_log",
]
