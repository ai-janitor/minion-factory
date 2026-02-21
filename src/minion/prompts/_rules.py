"""Load daemon rules from contract or fallback, plus capability prompts."""

from __future__ import annotations

from pathlib import Path
from typing import List

from minion.daemon.contracts import load_contract

from .capabilities import load_capability_prompts
from .roles import load_role_prompt


def load_rules(docs_dir: Path, agent: str, role: str, capabilities: tuple[str, ...] = ()) -> str:
    """Build the daemon rules + role prompts + capability prompts for an agent."""
    contract = load_contract(docs_dir, "daemon-rules")
    if contract:
        def _sub(s: str) -> str:
            return s.replace("{agent}", agent)
        lines: List[str] = ["Autonomous daemon rules:"]
        lines.extend(f"- {_sub(r)}" for r in contract["common"])
        role_rules = contract.get("lead" if role == "lead" else "non_lead", [])
        lines.extend(f"- {_sub(r)}" for r in role_rules)
        rules_text = "\n".join(lines)
    else:
        lines = [
            "Autonomous daemon rules:",
            "- Do not use AskUserQuestion — it blocks in headless mode.",
            f"- Route questions to lead via Bash: minion send --from {agent} --to lead --message '...'",
            "- Execute exactly the incoming task.",
            "- Send one summary message when done.",
            "- Task governance: lead manages task queue and assignment ownership.",
        ]
        rules_text = "\n".join(lines)

    # Role-level prompts from roles/{role}/prompt.md
    role_text = load_role_prompt(role)

    # Capability-level prompts from capabilities/{cap}/prompt.md
    cap_text = load_capability_prompts(set(capabilities))

    sections = [rules_text]
    if role_text:
        sections.append(role_text)
    if cap_text:
        sections.append(cap_text)
    return "\n\n".join(sections)
