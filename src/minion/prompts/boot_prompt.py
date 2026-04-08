"""Compose the full boot prompt from protocol + rules + boot sections.

Purpose: Compose the full boot prompt from protocol + rules + boot sections.
Rationale: Extracted into own module following single-responsibility principle.
Responsibility: Compose the full boot prompt from protocol + rules + boot sections. NOT responsible for unrelated concerns.
Organization: Standalone functions and/or a single class. See source."""

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
    model: str = "",
) -> str:
    """Assemble the first-invocation boot prompt.

    Args:
        docs_dir: Path to docs directory (contracts, protocol files).
        agent: Agent name.
        role: Agent role (lead, coder, scout, etc.).
        guardrails: Provider-specific prompt guardrails (may be empty).
        capabilities: Agent's capabilities from crew YAML or class defaults.
        model: Model ID for the boot register command (required by --model
            on `minion register`). Empty string falls back to a default in
            load_boot_section.
    """
    protocol_section = load_protocol(docs_dir, role, agent)
    rules_section = load_rules(docs_dir, agent, role, capabilities)
    boot_section = load_boot_section(docs_dir, agent, role, model=model)

    sections = [protocol_section, rules_section, boot_section]
    if guardrails:
        sections.insert(0, guardrails)
    return "\n\n".join(sections)
