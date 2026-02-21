"""Build prompt for terminal-transport agents."""

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
