"""Missions — capability-driven team composition."""

from minion.missions.loader import load_mission, list_missions, Mission
from minion.missions.resolver import resolve_slots
from minion.missions.party import suggest_party
from minion.missions.spawn import resolve_and_spawn

__all__ = [
    "Mission",
    "load_mission",
    "list_missions",
    "resolve_and_spawn",
    "resolve_slots",
    "suggest_party",
]
