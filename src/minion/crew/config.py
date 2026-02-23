from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Literal, Optional

import yaml
from minion.defaults import ENV_DB_PATH, resolve_db_path, resolve_docs_dir, resolve_path

ProviderName = Literal["claude", "codex", "opencode", "gemini"]


@dataclass(frozen=True)
class AgentConfig:
    name: str
    role: str
    zone: str
    provider: ProviderName
    system: str
    allowed_tools: Optional[str]
    permission_mode: Optional[str]
    model: Optional[str]
    max_history_tokens: int
    max_prompt_chars: int
    no_output_timeout_sec: int
    retry_backoff_sec: int
    retry_backoff_max_sec: int
    skills: tuple[str, ...] = ()
    self_dismiss: bool = False
    capabilities: tuple[str, ...] = ()


@dataclass(frozen=True)
class SwarmConfig:
    config_path: Path
    project_dir: Path
    comms_dir: Path
    comms_db: Path
    docs_dir: Path
    agents: Dict[str, AgentConfig]

    @property
    def runtime_dir(self) -> Path:
        return self.project_dir / ".minion-swarm"

    @property
    def logs_dir(self) -> Path:
        return self.runtime_dir / "logs"

    @property
    def pids_dir(self) -> Path:
        return self.runtime_dir / "pids"

    @property
    def state_dir(self) -> Path:
        return self.runtime_dir / "state"

    def ensure_runtime_dirs(self) -> None:
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.pids_dir.mkdir(parents=True, exist_ok=True)
        self.state_dir.mkdir(parents=True, exist_ok=True)



def load_config(config_path: str | Path) -> SwarmConfig:
    cfg_path = Path(config_path).expanduser().resolve()
    if not cfg_path.exists():
        raise FileNotFoundError(f"Config not found: {cfg_path}")

    raw = yaml.safe_load(cfg_path.read_text()) or {}
    if not isinstance(raw, dict):
        raise ValueError("Top-level config must be a YAML mapping")

    project_dir = resolve_path(str(raw.get("project_dir", cfg_path.parent)), cfg_path.parent)
    comms_dir = resolve_path(
        str(raw.get("comms_dir", ".work")),
        project_dir,
    )

    # comms_db comes from MINION_DB_PATH env (set by spawn), not from YAML.
    # Ignore stale comms_db in crew YAMLs — env is the source of truth.
    comms_db = resolve_path(
        str(os.environ.get(ENV_DB_PATH) or resolve_db_path()),
        cfg_path.parent,
    )

    docs_dir = resolve_path(
        str(raw.get("docs_dir", resolve_docs_dir())),
        cfg_path.parent,
    )

    agents_raw = raw.get("agents")
    if not isinstance(agents_raw, dict) or not agents_raw:
        raise ValueError("Config must define a non-empty 'agents' mapping")

    agents: Dict[str, AgentConfig] = {}
    for name, item in agents_raw.items():
        if not isinstance(item, dict):
            raise ValueError(f"Agent '{name}' config must be a mapping")

        provider = str(item.get("provider", "claude")).strip().lower()
        if provider not in {"claude", "codex", "opencode", "gemini"}:
            raise ValueError(
                f"Agent '{name}' has invalid provider '{provider}'. "
                "Expected one of: claude, codex, opencode, gemini."
            )

        role = str(item.get("role", "coder"))
        zone = str(item.get("zone", ""))
        system = str(item.get("system", "")).strip()
        if not system:
            system = (
                f"You are {name} ({role}) running under minion-swarm. "
                "Check inbox, execute tasks, and report when done."
            )

        # Inject crew-level system_prefix into every agent's prompt
        from minion.prompts import build_system_prompt
        system = build_system_prompt(str(raw.get("system_prefix", "")), system)

        allowed_tools = item.get("allowed_tools")
        if allowed_tools is not None:
            allowed_tools = str(allowed_tools)

        permission_mode = item.get("permission_mode")
        if permission_mode is not None:
            permission_mode = str(permission_mode).strip()
            if not permission_mode:
                permission_mode = None

        model = item.get("model")
        if model is not None:
            model = str(model)

        max_history_tokens = int(item.get("max_history_tokens", 100_000))
        max_prompt_chars = int(item.get("max_prompt_chars", 120_000))
        no_output_timeout_sec = int(item.get("no_output_timeout_sec", 600))
        retry_backoff_sec = int(item.get("retry_backoff_sec", 30))
        retry_backoff_max_sec = int(item.get("retry_backoff_max_sec", 300))

        skills_raw = item.get("skills", [])
        skills = tuple(str(s) for s in skills_raw) if isinstance(skills_raw, list) else ()

        from minion.auth import CLASS_CAPABILITIES, VALID_CAPABILITIES
        caps_raw = item.get("capabilities")
        if isinstance(caps_raw, list):
            caps = tuple(str(c) for c in caps_raw if str(c) in VALID_CAPABILITIES)
        else:
            caps = tuple(sorted(CLASS_CAPABILITIES.get(role, set())))

        agents[str(name)] = AgentConfig(
            name=str(name),
            role=role,
            zone=zone,
            provider=provider,  # type: ignore[arg-type]
            system=system,
            allowed_tools=allowed_tools,
            permission_mode=permission_mode,
            model=model,
            max_history_tokens=max_history_tokens,
            max_prompt_chars=max_prompt_chars,
            no_output_timeout_sec=no_output_timeout_sec,
            retry_backoff_sec=retry_backoff_sec,
            retry_backoff_max_sec=retry_backoff_max_sec,
            skills=skills,
            self_dismiss=bool(item.get("self_dismiss", False)),
            capabilities=caps,
        )

    return SwarmConfig(
        config_path=cfg_path,
        project_dir=project_dir,
        comms_dir=comms_dir,
        comms_db=comms_db,
        docs_dir=docs_dir,
        agents=agents,
    )


def get_agent_prompt(profile_name: str, crew_name: str) -> dict[str, Any]:
    """Load a crew YAML and return the named agent's full prompt config.

    profile_name: key in the crew YAML agents mapping (character/role profile)
    Reuses _find_crew_file() for crew discovery and load_config() for parsing,
    so all prompt construction (system_prefix injection, defaults) stays consistent.
    """
    from minion.crew.spawn import _find_crew_file

    crew_file = _find_crew_file(crew_name)
    if crew_file is None:
        return {"error": f"Crew '{crew_name}' not found"}

    try:
        cfg = load_config(crew_file)
    except (FileNotFoundError, ValueError) as exc:
        return {"error": f"Failed to load crew '{crew_name}': {exc}"}

    agent = cfg.agents.get(profile_name)
    if agent is None:
        return {
            "error": f"Agent '{profile_name}' not found in crew '{crew_name}'",
            "available_agents": sorted(cfg.agents.keys()),
        }

    return {
        "name": agent.name,
        "role": agent.role,
        "zone": agent.zone,
        "model": agent.model,
        "system": agent.system,
        "allowed_tools": agent.allowed_tools,
        "permission_mode": agent.permission_mode,
        "capabilities": list(agent.capabilities),
    }
