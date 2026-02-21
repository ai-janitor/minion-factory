"""Compose the watcher-mode prompt from protocol + rules + message."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ._history import build_history_block
from ._protocol import load_protocol
from ._rules import load_rules


def build_watcher_prompt(
    docs_dir: Path,
    agent: str,
    role: str,
    message_section: str,
    guardrails: str = "",
    history_snapshot: Optional[str] = None,
    capabilities: tuple[str, ...] = (),
) -> str:
    """Assemble the watcher-mode prompt with a single incoming message.

    Args:
        docs_dir: Path to docs directory.
        agent: Agent name.
        role: Agent role.
        message_section: Pre-formatted incoming message block.
        guardrails: Provider-specific prompt guardrails (may be empty).
        history_snapshot: Rolling buffer snapshot for post-compaction recovery.
        capabilities: Agent's capabilities from crew YAML or class defaults.
    """
    protocol_section = load_protocol(docs_dir, role, agent)
    rules_section = load_rules(docs_dir, agent, role, capabilities)

    sections = [protocol_section]

    if history_snapshot is not None:
        sections.append(build_history_block(docs_dir, history_snapshot))

    sections.extend([rules_section, message_section])
    return "\n\n".join(s for s in sections if s.strip())
