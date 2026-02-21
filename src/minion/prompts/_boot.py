"""Load boot-sequence contract or fallback."""

from __future__ import annotations

from pathlib import Path
from typing import Dict

from minion.daemon.contracts import load_contract


def load_boot_section(docs_dir: Path, agent: str, role: str) -> str:
    """Build the ON STARTUP boot section."""
    contract = load_contract(docs_dir, "boot-sequence")
    if contract:
        subs: Dict[str, str] = {"{agent}": agent, "{role}": role}

        def _sub(s: str) -> str:
            for k, v in subs.items():
                s = s.replace(k, v)
            return s

        cmds = [f"  {_sub(c)}" for c in contract["commands"]]
        return "\n".join(
            [_sub(contract["preamble"])] + cmds + ["", _sub(contract["postamble"])]
        )

    return "\n".join([
        "BOOT: You just started. Run these commands via the Bash tool:",
        f"  minion --compact register --name {agent} --class {role} --transport daemon",
        f"  minion set-context --agent {agent} --context 'just started'",
        f"  minion set-status --agent {agent} --status 'ready for orders'",
        "",
        "IMPORTANT: You are a daemon agent managed by minion-swarm.",
        "Do NOT run poll.sh — minion-swarm handles polling for you.",
        "Do NOT use AskUserQuestion — it blocks in headless mode.",
        "After running these 3 commands, STOP. Do not do anything else.",
    ])
