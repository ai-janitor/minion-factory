"""Missions — capability-driven team composition.

Purpose: Missions — capability-driven team composition.
Rationale: Extracted into own module for single-responsibility mission orchestration.
Responsibility: Missions — capability-driven team composition. NOT responsible for unrelated concerns.
Organization: Re-exports public API symbols. Imports only, no logic."""

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
