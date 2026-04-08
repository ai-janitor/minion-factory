"""Load boot-sequence contract or fallback.

Purpose: Load boot-sequence contract or fallback.
Rationale: Extracted into own module following single-responsibility principle.
Responsibility: Load boot-sequence contract or fallback. NOT responsible for unrelated concerns.
Organization: Standalone functions and/or a single class. See source."""

from __future__ import annotations

from pathlib import Path
from typing import Dict

from minion.daemon.contracts import load_contract


def load_boot_section(docs_dir: Path, agent: str, role: str, model: str = "") -> str:
    """Build the ON STARTUP boot section.

    Backlog #310-followup: `model` was added because `minion register` now
    requires `--model`. Without it the boot register call exits 2 and the
    daemon spins forever in a register loop. Defaults to a sensible model
    when caller doesn't pass one (older callers).
    """
    effective_model = model or "claude-sonnet-4-6"
    contract = load_contract(docs_dir, "boot-sequence")
    if contract:
        subs: Dict[str, str] = {
            "{agent}": agent,
            "{role}": role,
            "{model}": effective_model,
        }

        def _sub(s: str) -> str:
            for k, v in subs.items():
                s = s.replace(k, v)
            return s

        # Backlog: legacy contract templates may not include {model}. If the
        # register command in the contract doesn't already mention --model,
        # inject it inline so old contracts on disk keep working.
        rendered_cmds = []
        for c in contract["commands"]:
            rendered = _sub(c)
            if (
                "register" in rendered
                and "--model" not in rendered
                and "set-context" not in rendered
                and "set-status" not in rendered
            ):
                rendered = f"{rendered} --model {effective_model}"
            rendered_cmds.append(f"  {rendered}")
        return "\n".join(
            [_sub(contract["preamble"])] + rendered_cmds + ["", _sub(contract["postamble"])]
        )

    return "\n".join([
        "BOOT: You just started. Run these commands via the Bash tool:",
        f"  minion --compact register --name {agent} --class {role} --model {effective_model} --transport daemon",
        f"  minion set-context --agent {agent} --context 'just started'",
        f"  minion set-status --agent {agent} --status 'ready for orders'",
        "",
        "IMPORTANT: You are a daemon agent managed by minion-swarm.",
        "Do NOT run poll.sh — minion-swarm handles polling for you.",
        "Do NOT use AskUserQuestion — it blocks in headless mode.",
        "After running these 3 commands, STOP. Do not do anything else.",
    ])
