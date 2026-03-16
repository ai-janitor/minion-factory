"""Recruit — add an ad-hoc agent into a running crew's tmux session.

Purpose: Recruit — add an ad-hoc agent into a running crew's tmux session.
Rationale: Extracted into own module for single-responsibility crew lifecycle management.
Responsibility: Recruit — add an ad-hoc agent into a running crew's tmux session. NOT responsible for unrelated concerns.
Organization: Standalone functions and/or a single class. See source."""

from __future__ import annotations

import os
import subprocess
from typing import Any

import yaml

from minion.auth import VALID_CAPABILITIES, VALID_CLASSES
from minion.comms import register as _register
from ._tmux import finalize_layout, style_pane
from minion.crew.daemon import init_swarm, spawn_pane, start_swarm
from minion.crew.spawn import _find_crew_file


def recruit_agent(
    name: str,
    agent_class: str | None,
    crew: str,
    *,
    from_crew: str = "",
    capabilities: str = "",
    system: str = "",
    provider: str | None = None,
    model: str = "",
    transport: str | None = None,
    permission_mode: str = "",
    zone: str = "",
    runtime: str = "python",
    project_dir: str = ".",
) -> dict[str, Any]:
    """Add a single ad-hoc agent into an already-running crew tmux session.

    Config cascade (highest to lowest precedence):
      1. CLI args (explicit, non-None values passed from crew_cmds.py)
      2. Config file (--from-crew YAML character values)
      3. Hardcoded defaults
    """

    project_dir = os.path.abspath(project_dir)

    # --- Pull character config from source crew YAML ---
    char_cfg: dict[str, Any] | None = None
    if from_crew:
        source_file = _find_crew_file(from_crew, project_dir)
        if not source_file:
            return {"error": f"BLOCKED: Source crew '{from_crew}' not found."}
        with open(source_file) as f:
            source_cfg = yaml.safe_load(f)
        char_cfg = source_cfg.get("agents", {}).get(name)
        if not char_cfg:
            # Name not in source crew — try matching by class for cloning
            by_class = {
                n: c for n, c in source_cfg.get("agents", {}).items()
                if c.get("role") == agent_class
            }
            if by_class:
                char_cfg = next(iter(by_class.values()))
            # If still nothing, fall through — use CLI flags/defaults

    # Config cascade: CLI explicit (non-None) > config file > defaults.
    # For each field: if CLI provided a value (non-None/non-empty), use it.
    # Otherwise check config file. Otherwise apply hardcoded default.
    if char_cfg:
        agent_class = agent_class or char_cfg.get("role") or "coder"
        provider = provider or char_cfg.get("provider") or "claude"
        model = model or char_cfg.get("model", "")
        transport = transport or char_cfg.get("transport") or "daemon"
        permission_mode = permission_mode or char_cfg.get("permission_mode", "")
        zone = zone or char_cfg.get("zone", "")
        system = system or char_cfg.get("system", "")
        if not capabilities:
            source_caps = char_cfg.get("capabilities")
            if isinstance(source_caps, list):
                capabilities = ",".join(str(c) for c in source_caps)

    # Apply defaults for anything still unset (no CLI arg, no config file value)
    agent_class = agent_class or "coder"
    provider = provider or "claude"
    transport = transport or "daemon"

    # --- Validate inputs ---
    if agent_class not in VALID_CLASSES:
        return {"error": f"BLOCKED: Invalid class '{agent_class}'. Valid: {sorted(VALID_CLASSES)}"}

    if provider not in {"claude", "codex", "opencode", "gemini"}:
        return {"error": f"BLOCKED: Invalid provider '{provider}'. Valid: claude, codex, opencode, gemini"}

    if capabilities:
        caps = [c.strip() for c in capabilities.split(",") if c.strip()]
        bad = [c for c in caps if c not in VALID_CAPABILITIES]
        if bad:
            return {"error": f"BLOCKED: Invalid capabilities: {bad}. Valid: {sorted(VALID_CAPABILITIES)}"}
    else:
        caps = []

    # --- Verify tmux session exists ---
    tmux_session = f"crew-{crew}"
    rc = subprocess.run(
        ["tmux", "has-session", "-t", tmux_session],
        capture_output=True,
    ).returncode
    if rc != 0:
        return {"error": f"BLOCKED: tmux session '{tmux_session}' not found. Spawn the crew first."}

    # --- Register agent in DB ---
    _register(
        agent_name=name,
        agent_class=agent_class,
        model=model,
        transport=transport,
    )

    # Write crew column
    from minion.db import get_db
    conn = get_db()
    try:
        conn.execute("UPDATE agents SET crew = ? WHERE name = ?", (crew, name))
        conn.commit()
    finally:
        conn.close()

    # --- Build single-agent YAML with full config ---
    agent_cfg: dict[str, Any] = {
        "role": agent_class,
        "provider": provider,
        "transport": transport,
    }
    if system:
        agent_cfg["system"] = system
    if model:
        agent_cfg["model"] = model
    if permission_mode:
        agent_cfg["permission_mode"] = permission_mode
    if zone:
        agent_cfg["zone"] = zone
    if caps:
        agent_cfg["capabilities"] = caps

    crew_yaml = {
        "project_dir": project_dir,
        "agents": {name: agent_cfg},
    }

    config_dir = os.path.expanduser("~/.minion-swarm")
    os.makedirs(config_dir, exist_ok=True)
    crew_config = os.path.join(config_dir, f"recruit-{crew}-{name}.yaml")
    with open(crew_config, "w") as f:
        yaml.dump(crew_yaml, f, default_flow_style=False)

    # --- Init runtime dirs ---
    init_swarm(crew_config, project_dir)

    # --- Count existing panes for style index ---
    result = subprocess.run(
        ["tmux", "list-panes", "-t", tmux_session],
        capture_output=True, text=True,
    )
    pane_idx = 0
    if result.returncode == 0:
        pane_idx = len(result.stdout.strip().splitlines())

    # --- Multi-instance: detect if this agent already has an alive process ---
    from minion.instance import is_instance_alive, next_instance_id
    instance_id: str | None = None
    effective_name = name
    if is_instance_alive(name, None, project_dir):
        instance_id = next_instance_id(name, project_dir)
        effective_name = f"{name}-{instance_id}"
        # Re-register with instance-qualified name so comms routing works
        _register(
            agent_name=effective_name,
            agent_class=agent_class,
            model=model,
            transport=transport,
        )
        # Update crew column for instance-qualified agent
        conn2 = get_db()
        try:
            conn2.execute("UPDATE agents SET crew = ? WHERE name = ?", (crew, effective_name))
            conn2.commit()
        finally:
            conn2.close()

    # --- Spawn tmux pane ---
    pane_result = spawn_pane(tmux_session, name, project_dir, crew_config, session_exists=True, instance_id=instance_id)
    if pane_result is not True:
        return {"error": f"Failed to spawn pane: {pane_result}"}

    style_pane(tmux_session, pane_idx, effective_name, agent_class, model=model, provider=provider)
    finalize_layout(tmux_session, is_new=False, pane_count=pane_idx + 1)

    # --- Start daemon ---
    db_path = os.path.join(project_dir, ".work", "minion.db")
    start_swarm(name, crew_config, project_dir, runtime=runtime, db_path=db_path, instance_id=instance_id)

    result_dict: dict[str, Any] = {
        "status": "recruited",
        "agent": effective_name,
        "class": agent_class,
        "crew": crew,
        "tmux_session": tmux_session,
    }
    if instance_id:
        result_dict["instance_id"] = instance_id
        result_dict["base_agent"] = name
    return result_dict
