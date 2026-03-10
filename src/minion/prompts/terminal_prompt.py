"""Build prompt for terminal-transport agents.

Purpose: Build prompt for terminal-transport agents.
Rationale: Extracted into own module following single-responsibility principle.
Responsibility: Build prompt for terminal-transport agents. NOT responsible for unrelated concerns.
Organization: Standalone functions and/or a single class. See source."""

from __future__ import annotations


def build_terminal_prompt(system_prompt: str, agent: str) -> str:
    """Append poll instruction to terminal agent's system prompt."""
    poll_instruction = (
        f"\n\nIMPORTANT: On startup, run `minion poll --agent {agent} &` "
        f"in the background to receive messages from other agents."
    )
    if system_prompt:
        return system_prompt + poll_instruction
    return ""
