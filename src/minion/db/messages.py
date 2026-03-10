"""Message-related DB helpers — triggers, onboarding, trigger codebook.

Functions that scan messages for trigger words, load onboarding docs,
and format the trigger codebook display.
"""

from __future__ import annotations

import os

from minion.defaults import resolve_docs_dir

DOCS_DIR = resolve_docs_dir()


def scan_triggers(message: str) -> list[str]:
    """Return trigger words found in message text.

    Only matches deliberate !!trigger!! pattern — not casual mentions.
    """
    from minion.defaults import TRIGGER_WORDS
    lower = message.lower()
    return [word for word in TRIGGER_WORDS if f"!!{word}!!" in lower]


def format_trigger_codebook() -> str:
    """Format the trigger word codebook for display."""
    from minion.defaults import TRIGGER_WORDS
    lines = ["## Trigger Words (Brevity Codes)", ""]
    lines.append("Wrap in `!!` to activate: `!!stand_down!!`. Bare mentions are ignored.")
    lines.append("")
    lines.append("| Code | Meaning |")
    lines.append("|---|---|")
    for word, meaning in TRIGGER_WORDS.items():
        lines.append(f"| `{word}` | {meaning} |")
    return "\n".join(lines)


def load_onboarding(agent_class: str) -> str:
    """Load protocol + class profile docs from runtime directory."""
    parts: list[str] = []

    protocol_path = os.path.join(DOCS_DIR, "protocol-common.md")
    if os.path.exists(protocol_path):
        with open(protocol_path) as f:
            parts.append(f.read())

    if agent_class:
        class_path = os.path.join(DOCS_DIR, f"protocol-{agent_class}.md")
        if os.path.exists(class_path):
            with open(class_path) as f:
                parts.append(f.read())

    return "\n\n---\n\n".join(parts) if parts else ""
