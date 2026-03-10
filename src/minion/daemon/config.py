"""Daemon config loader — shares dataclasses with crew/config.py (DRY).
AgentConfig and SwarmConfig are defined once in crew/config.py. Daemon
reuses them — the extra fields (skills, scope) have defaults and are
simply unused by daemon code.

Purpose: Daemon config loader — shares dataclasses with crew/config.py (DRY).
Rationale: Extracted into own module for single-responsibility daemon transport.
Responsibility: Daemon config loader — shares dataclasses with crew/config.py (DRY). NOT responsible for unrelated concerns.
Organization: Standalone functions and/or a single class. See source."""
from __future__ import annotations

import os
from pathlib import Path

import yaml
from minion.defaults import (
    DEFAULT_DOCS_DIR,
    ENV_DB_PATH,
    ENV_DOCS_DIR,
    resolve_db_path,
    resolve_path as _resolve_path,
)

# DRY: import shared dataclasses from crew — single source of truth
from minion.crew.config import AgentConfig, SwarmConfig  # noqa: F401


def load_config(config_path: str | Path) -> SwarmConfig:
    cfg_path = Path(config_path).expanduser().resolve()
    if not cfg_path.exists():
        raise FileNotFoundError(f"Config not found: {cfg_path}")

    raw = yaml.safe_load(cfg_path.read_text()) or {}
    if not isinstance(raw, dict):
        raise ValueError("Top-level config must be a YAML mapping")

    project_dir = _resolve_path(str(raw.get("project_dir", cfg_path.parent)), cfg_path.parent)
    comms_dir = _resolve_path(
        str(raw.get("comms_dir", ".work")),
        project_dir,
    )

    # comms_db comes from MINION_DB_PATH env (set by spawn), not from YAML.
    # Ignore stale comms_db in crew YAMLs — env is the source of truth.
    comms_db = _resolve_path(
        str(os.environ.get(ENV_DB_PATH) or resolve_db_path()),
        cfg_path.parent,
    )

    docs_dir = _resolve_path(
        str(raw.get("docs_dir", os.environ.get(ENV_DOCS_DIR, DEFAULT_DOCS_DIR))),
        cfg_path.parent,
    )

    agents_raw = raw.get("agents")
    if not isinstance(agents_raw, dict) or not agents_raw:
        raise ValueError("Config must define a non-empty 'agents' mapping")

    # Delegate agent parsing to crew/config._parse_agents — single source of truth.
    # skills and scope fields have AgentConfig dataclass defaults; daemon doesn't set them.
    from minion.crew.config import _parse_agents
    agents = _parse_agents(agents_raw, str(raw.get("system_prefix", "")))

    return SwarmConfig(
        config_path=cfg_path,
        project_dir=project_dir,
        comms_dir=comms_dir,
        comms_db=comms_db,
        docs_dir=docs_dir,
        agents=agents,
    )
