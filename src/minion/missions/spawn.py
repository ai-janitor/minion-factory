"""Mission spawn — resolve party slots and spawn a dynamic crew."""
from __future__ import annotations

import os
from typing import Any

import yaml

from minion.crew.spawn import _find_crew_file, spawn_party
from minion.missions.loader import load_mission
from minion.missions.resolver import resolve_slots
from minion.missions.party import suggest_party


def resolve_and_spawn(
    mission_type: str,
    party_str: str,
    crew: str,
    project_dir: str,
    runtime: str = "python",
) -> dict[str, Any]:
    """Resolve mission slots, validate party, build dynamic crew YAML, and spawn."""
    mission = load_mission(mission_type)
    slots = resolve_slots(set(mission.requires))
    crews_filter = [c.strip() for c in crew.split(",") if c.strip()] or None
    party = suggest_party(slots, crews=crews_filter, project_dir=project_dir)

    if not party_str:
        return {
            "status": "suggest",
            "mission": mission.name,
            "slots": slots,
            "eligible": party,
            "hint": "Re-run with --party <names> to spawn",
        }

    # Validate party members exist in eligible characters
    requested = [p.strip() for p in party_str.split(",")]
    all_eligible = {c["name"]: c for slot_chars in party.values() for c in slot_chars}
    unknown = [p for p in requested if p not in all_eligible]
    if unknown:
        return {"error": f"Unknown characters: {', '.join(unknown)}. Eligible: {', '.join(sorted(all_eligible))}"}

    # Build a dynamic crew config from selected characters
    agents_cfg: dict = {}
    for name in requested:
        char = all_eligible[name]
        crew_name = char["crew"]
        crew_file = _find_crew_file(crew_name, project_dir)
        if not crew_file:
            return {"error": f"Crew file for '{crew_name}' not found"}
        with open(crew_file) as f:
            crew_cfg = yaml.safe_load(f)
        agent_raw = crew_cfg.get("agents", {}).get(name, {})
        agents_cfg[name] = agent_raw

    # Write temporary crew YAML
    dynamic_crew = {
        "project_dir": os.path.abspath(project_dir),
        "agents": agents_cfg,
    }
    tmpdir = os.path.expanduser("~/.minion-swarm")
    os.makedirs(tmpdir, exist_ok=True)
    tmp_crew_name = f"mission-{mission.name}"
    tmp_path = os.path.join(tmpdir, f"{tmp_crew_name}.yaml")
    with open(tmp_path, "w") as f:
        yaml.dump(dynamic_crew, f, default_flow_style=False)

    result = spawn_party(tmp_crew_name, project_dir, runtime=runtime)
    result["mission"] = mission.name
    result["slots"] = slots
    return result
