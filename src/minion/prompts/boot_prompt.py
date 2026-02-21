"""Compose the full boot prompt from protocol + rules + boot sections."""

from __future__ import annotations

from pathlib import Path

from ._boot import load_boot_section
from ._protocol import load_protocol
from ._rules import load_rules


def build_boot_prompt(
    docs_dir: Path,
    agent: str,
    role: str,
    guardrails: str = "",
    capabilities: tuple[str, ...] = (),
) -> str:
    """Assemble the first-invocation boot prompt.

    Args:
        docs_dir: Path to docs directory (contracts, protocol files).
        agent: Agent name.
        role: Agent role (lead, coder, scout, etc.).
        guardrails: Provider-specific prompt guardrails (may be empty).
        capabilities: Agent's capabilities from crew YAML or class defaults.
    """
    protocol_section = load_protocol(docs_dir, role, agent)
    rules_section = load_rules(docs_dir, agent, role, capabilities)
    boot_section = load_boot_section(docs_dir, agent, role)

    sections = [protocol_section, rules_section, boot_section]
    if guardrails:
        sections.insert(0, guardrails)
    return "\n\n".join(sections)
