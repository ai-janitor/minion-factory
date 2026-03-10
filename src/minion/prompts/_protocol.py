"""Load protocol docs (protocol-common.md + protocol-{role}.md).

Purpose: Load protocol docs (protocol-common.md + protocol-{role}.md).
Rationale: Extracted into own module following single-responsibility principle.
Responsibility: Load protocol docs (protocol-common.md + protocol-{role}.md). NOT responsible for unrelated concerns.
Organization: Standalone functions and/or a single class. See source."""

from __future__ import annotations

from pathlib import Path
from typing import List


def load_protocol(docs_dir: Path, role: str, agent: str) -> str:
    """Read protocol-common.md + protocol-{role}.md, fallback to hardcoded."""
    sections: List[str] = []
    for fname in ["protocol-common.md", f"protocol-{role}.md"]:
        doc = docs_dir / fname
        if doc.exists():
            sections.append(doc.read_text().strip())
    if sections:
        return "\n\n".join(sections)
    # Fallback if protocol docs not installed
    return "\n".join(
        [
            "Communication protocol — use the `minion` CLI via Bash tool:",
            f"- Check inbox: minion check-inbox --agent {agent}",
            f"- Send message: minion send-local --from {agent} --to <recipient> --message '...'",
            f"- Set status: minion set-status --agent {agent} --status '...'",
            f"- Set context: minion set-context --agent {agent} --context '...'",
            f"- View agents: minion who",
            "- All minion commands output JSON. Use Bash tool to run them.",
        ]
    )
