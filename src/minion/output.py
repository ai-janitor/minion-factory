"""CLI output formatting — JSON, human-readable, and compact modes."""
from __future__ import annotations

import json
import sys

import click


def output(data: dict[str, object], human: bool = False, compact: bool = False) -> None:
    """Print result as JSON (default), human-readable, or compact text."""
    if "error" in data:
        click.echo(json.dumps(data, indent=2, default=str), err=True)
        sys.exit(1)
    if compact:
        click.echo(_format_compact(data))
    elif human:
        for k, v in data.items():
            if isinstance(v, (list, dict)):
                click.echo(f"{k}: {json.dumps(v, indent=2, default=str)}")
            else:
                click.echo(f"{k}: {v}")
    else:
        click.echo(json.dumps(data, indent=2, default=str))


def _format_compact(data: dict[str, object]) -> str:
    """Format CLI output as concise text for agent context injection."""
    lines: list[str] = []

    # Status line
    status = data.get("status", "")
    agent = data.get("agent", data.get("agent_name", ""))
    cls = data.get("class", data.get("agent_class", ""))
    if status and agent:
        transport = ""
        playbook = data.get("playbook")
        if isinstance(playbook, dict):
            transport = f", {playbook.get('type', '')}"
        lines.append(f"{status}: {agent} ({cls}{transport})")

    # Tools as compact table
    tools = data.get("tools")
    if isinstance(tools, list) and tools:
        lines.append("")
        lines.append("Commands:")
        for t in tools:
            if isinstance(t, dict):
                cmd = t.get("command", "")
                desc = t.get("description", "")
                lines.append(f"  {cmd:30s} {desc}")

    # Triggers as one-liner
    triggers = data.get("triggers")
    if isinstance(triggers, str) and triggers:
        codes = []
        for line in triggers.splitlines():
            if line.startswith("| `"):
                code = line.split("`")[1]
                codes.append(code)
        if codes:
            lines.append("")
            lines.append(f"Triggers: {', '.join(codes)}")

    # Playbook as bullets
    playbook = data.get("playbook")
    if isinstance(playbook, dict):
        steps = playbook.get("steps", [])
        if steps:
            lines.append("")
            lines.append("Playbook:")
            for step in steps:
                lines.append(f"  - {step}")

    if not lines:
        return json.dumps(data, indent=2, default=str)

    return "\n".join(lines)
