"""Merge crew-level system_prefix with agent system prompt."""

from __future__ import annotations


def build_system_prompt(prefix: str, agent_system: str) -> str:
    """Merge system_prefix + agent system prompt. Handles empty/whitespace inputs."""
    prefix = prefix.strip()
    if prefix:
        return prefix + "\n\n" + agent_system
    return agent_system
