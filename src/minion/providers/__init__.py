"""Provider registry — maps provider name to concrete BaseProvider subclass.

Purpose: Provider registry — maps provider name to concrete BaseProvider subclass.
Rationale: Extracted into own module for single-responsibility provider configuration.
Responsibility: Provider registry — maps provider name to concrete BaseProvider subclass. NOT responsible for unrelated concerns.
Organization: Re-exports public API symbols. Imports only, no logic.

ASSUMPTIONS:
- Provider names in _REGISTRY must match the "provider" field in crew YAML configs
  exactly (lowercase). If a crew YAML specifies provider: "Claude" (capitalized),
  get_provider() will raise ValueError — no case normalization is done.
- All provider CLIs (claude, codex, gemini, opencode) must be installed and on PATH
  for their respective providers to work. The registry eagerly imports all provider
  classes at module load time — if any provider module has an import error, the entire
  registry fails to load even if that provider isn't being used.
- agent_cfg is expected to be an AgentConfig namedtuple/dataclass from crew/config.py.
  The type annotation says 'agent_cfg' (untyped) because of circular import avoidance.
  Passing a plain dict or None will cause AttributeError in provider constructors that
  access agent_cfg.model, agent_cfg.system_prompt, etc.
- use_poll=True tells the provider to inject polling instructions into the agent's
  system prompt. Providers that don't support polling (codex) ignore this flag silently.
"""
from __future__ import annotations

from .cli_provider_protocol import BaseProvider
from .claude import ClaudeProvider
from .codex import CodexProvider
from .gemini import GeminiProvider
from .opencode import OpencodeProvider

__all__ = [
    "BaseProvider",
    "ClaudeProvider",
    "CodexProvider",
    "GeminiProvider",
    "OpencodeProvider",
    "get_provider",
]

_REGISTRY: dict[str, type[BaseProvider]] = {
    "claude": ClaudeProvider,
    "codex": CodexProvider,
    "gemini": GeminiProvider,
    "opencode": OpencodeProvider,
}


def get_provider(name: str, agent_name: str, agent_cfg, use_poll: bool, project_dir: str = "") -> BaseProvider:
    cls = _REGISTRY.get(name)
    if cls is None:
        raise ValueError(f"Unknown provider '{name}'. Available: {sorted(_REGISTRY)}")
    return cls(agent_name=agent_name, agent_cfg=agent_cfg, use_poll=use_poll, project_dir=project_dir)
