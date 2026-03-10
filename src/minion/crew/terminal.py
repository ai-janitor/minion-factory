"""Terminal transport — interactive claude session in its own Terminal.app window.

Purpose: Terminal transport — interactive claude session in its own Terminal.app window.
Rationale: Extracted into own module for single-responsibility crew lifecycle management.
Responsibility: Terminal transport — interactive claude session in its own Terminal.app window. NOT responsible for unrelated concerns.
Organization: Standalone functions and/or a single class. See source."""

from __future__ import annotations

import os

from minion.crew._tmux import open_terminal_with_command


def spawn_terminal(
    agent: str,
    project_dir: str,
    cfg: dict,
) -> None:
    """Launch an interactive claude session in a new Terminal.app window."""
    from minion.prompts import build_terminal_prompt

    system_prompt = cfg.get("system", "").strip()
    full_prompt = build_terminal_prompt(system_prompt, agent)

    # Inject env vars so Stop hook knows which agent/project to check
    cmd_parts = [
        f"cd {project_dir}",
        f"export MINION_AGENT_NAME={agent}",
        f"export MINION_PROJECT_DIR={project_dir}",
        "claude --dangerously-skip-permissions",
    ]
    if full_prompt:
        prompt_file = os.path.join(
            project_dir, ".minion-swarm", "prompts", f"{agent}.md"
        )
        os.makedirs(os.path.dirname(prompt_file), exist_ok=True)
        with open(prompt_file, "w") as pf:
            pf.write(full_prompt)
        cmd_parts[-1] += f" --append-system-prompt \"$(cat {prompt_file})\""
    cmd_parts[-1] += " \"Execute your ON STARTUP instructions now.\""

    open_terminal_with_command(" && ".join(cmd_parts), title=f"lead:{agent}")
