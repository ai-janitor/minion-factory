"""YAML loading, search paths, and validation for mission templates."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from minion.auth import VALID_CAPABILITIES


@dataclass(frozen=True)
class Mission:
    name: str
    description: str
    requires: list[str] = field(default_factory=list)


def _find_missions_dir() -> Path:
    """Search order: env var → ~/.minion/missions/ → bundled missions/."""
    env = os.getenv("MINION_MISSIONS_DIR")
    if env:
        return Path(env)
    user_dir = Path.home() / ".minion" / "missions"
    if user_dir.exists():
        return user_dir
    # Bundled: 4 levels up from src/minion/missions/loader.py
    return Path(__file__).resolve().parent.parent.parent.parent / "missions"


_DEFAULT_MISSIONS_DIR = _find_missions_dir()


def _validate(raw: dict, name: str) -> None:
    """Validate mission YAML structure."""
    if "name" not in raw:
        raise ValueError(f"Mission '{name}' missing required key: name")
    requires = raw.get("requires")
    if not requires or not isinstance(requires, list):
        raise ValueError(f"Mission '{name}' must have a non-empty 'requires' list")
    for cap in requires:
        if cap not in VALID_CAPABILITIES:
            raise ValueError(
                f"Mission '{name}': unknown capability '{cap}'. "
                f"Valid: {sorted(VALID_CAPABILITIES)}"
            )


def load_mission(name: str, missions_dir: str | Path | None = None) -> Mission:
    """Load a mission template by name."""
    mdir = Path(missions_dir) if missions_dir else _DEFAULT_MISSIONS_DIR
    path = mdir / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Mission '{name}' not found at {path}")
    with open(path) as f:
        raw = yaml.safe_load(f)
    _validate(raw, name)
    return Mission(
        name=raw["name"],
        description=raw.get("description", ""),
        requires=raw["requires"],
    )


def list_missions(missions_dir: str | Path | None = None) -> list[str]:
    """List available mission template names."""
    mdir = Path(missions_dir) if missions_dir else _DEFAULT_MISSIONS_DIR
    if not mdir.exists():
        return []
    return sorted(p.stem for p in mdir.glob("*.yaml"))
