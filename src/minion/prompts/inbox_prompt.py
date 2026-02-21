"""Compose the full inbox prompt from protocol + rules + inbox sections."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from ._history import build_history_block
from ._inbox import format_inbox
from ._protocol import load_protocol
from ._rules import load_rules


def build_inbox_prompt(
    docs_dir: Path,
    agent: str,
    role: str,
    poll_data: Dict[str, Any],
    guardrails: str = "",
    history_snapshot: Optional[str] = None,
    capabilities: tuple[str, ...] = (),
) -> str:
    """Assemble the inbox prompt with inline messages/tasks.

    Args:
        docs_dir: Path to docs directory.
        agent: Agent name.
        role: Agent role.
        poll_data: Dict with 'messages' and 'tasks' lists.
        guardrails: Provider-specific prompt guardrails (may be empty).
        history_snapshot: Rolling buffer snapshot for post-compaction recovery.
        capabilities: Agent's capabilities from crew YAML or class defaults.
    """
    protocol_section = load_protocol(docs_dir, role, agent)
    rules_section = load_rules(docs_dir, agent, role, capabilities)
    inbox_section = format_inbox(docs_dir, poll_data, agent)

    sections = []
    if guardrails:
        sections.append(guardrails)
    sections.append(protocol_section)

    if history_snapshot is not None:
        sections.append(build_history_block(docs_dir, history_snapshot))

    sections.extend([rules_section, inbox_section])
    return "\n\n".join(s for s in sections if s.strip())
