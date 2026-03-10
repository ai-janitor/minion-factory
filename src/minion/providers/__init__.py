"""Provider registry — maps provider name to concrete BaseProvider subclass.

Purpose: Provider registry — maps provider name to concrete BaseProvider subclass.
Rationale: Extracted into own module for single-responsibility provider configuration.
Responsibility: Provider registry — maps provider name to concrete BaseProvider subclass. NOT responsible for unrelated concerns.
Organization: Re-exports public API symbols. Imports only, no logic."""
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


def get_provider(name: str, agent_name: str, agent_cfg, use_poll: bool) -> BaseProvider:
    cls = _REGISTRY.get(name)
    if cls is None:
        raise ValueError(f"Unknown provider '{name}'. Available: {sorted(_REGISTRY)}")
    return cls(agent_name=agent_name, agent_cfg=agent_cfg, use_poll=use_poll)
