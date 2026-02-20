"""Character matching: resolved slots + crew rosters → party suggestions."""

from __future__ import annotations

import os
from typing import Any

import yaml

from minion.crew.spawn import _all_search_paths, _find_crew_file


def _scan_all_characters(project_dir: str = ".") -> list[dict[str, Any]]:
    """Scan all crew YAMLs and return flat list of characters with metadata."""
    characters: list[dict[str, Any]] = []
    seen_crews: set[str] = set()

    for search_dir in _all_search_paths(project_dir):
        if not os.path.isdir(search_dir):
            continue
        for fname in sorted(os.listdir(search_dir)):
            if not fname.endswith(".yaml"):
                continue
            crew_name = fname.replace(".yaml", "")
            if crew_name in seen_crews:
                continue
            seen_crews.add(crew_name)
            fpath = os.path.join(search_dir, fname)
            try:
                with open(fpath) as f:
                    cfg = yaml.safe_load(f)
                agents = cfg.get("agents", {})
                for name, agent_cfg in agents.items():
                    if not isinstance(agent_cfg, dict):
                        continue
                    characters.append({
                        "name": name,
                        "crew": crew_name,
                        "role": agent_cfg.get("role", "coder"),
                        "skills": agent_cfg.get("skills", []),
                    })
            except Exception as exc:
                import sys
                print(f"WARNING: failed to parse crew {crew_name}: {exc}", file=sys.stderr)
                continue

    return characters


def suggest_party(
    slots: list[str],
    crews: list[str] | None = None,
    project_dir: str = ".",
) -> dict[str, list[dict[str, Any]]]:
    """For each slot, find all eligible characters by class.

    Returns {slot_class: [character_info, ...]}.
    If crews is provided, only include characters from those crews.
    """
    all_chars = _scan_all_characters(project_dir)

    if crews:
        all_chars = [c for c in all_chars if c["crew"] in crews]

    result: dict[str, list[dict[str, Any]]] = {}
    for slot in slots:
        eligible = [c for c in all_chars if c["role"] == slot]
        result[slot] = eligible

    return result
