"""CLI output formatting — JSON, human-readable, and compact modes.

Includes remediation hints — when an error matches a known pattern, a
'hint' field is appended to the output with a suggested fix command.
"""
from __future__ import annotations

import json
import re
import sys

import click


# ---------------------------------------------------------------------------
# Remediation hints — map error patterns to actionable fix suggestions.
# Each entry: (compiled regex matching error message, hint string).
# Checked in order; first match wins.
# ---------------------------------------------------------------------------

_REMEDIATION_HINTS: list[tuple[re.Pattern[str], str]] = [
    # Agent not found / not registered
    (re.compile(r"Agent '([^']+)' not (found|registered)"),
     "Run `minion who` to see registered agents, or `minion agent register --name <name> --class <role>` to register."),

    # Task not found
    (re.compile(r"Task #?(\d+) not found"),
     "Run `minion task list` to see available tasks."),

    # Task in terminal status
    (re.compile(r"terminal status '([^']+)'"),
     "Terminal tasks cannot be advanced. Create a new task or use `minion task reopen` if available."),

    # Wrong class / auth failure
    (re.compile(r"Class '([^']+)' cannot run '([^']+)'"),
     "Check your class with `echo $MINION_CLASS`. Required classes are listed in the error. "
     "Re-register with the correct class: `minion agent register --name <name> --class <role>`."),

    # Scope restriction
    (re.compile(r"Scope '([^']+)' cannot run '([^']+)'"),
     "This command is restricted for your scope level. Ask your lead to perform this operation."),

    # Flow not found
    (re.compile(r"Task flow '([^']+)' not found"),
     "Run `minion flow list` to see available flow types."),

    # File claimed by another agent
    (re.compile(r"File '([^']+)' claimed by '([^']+)'"),
     "Wait for the holder to release, or ask a lead to force-release: `minion file release --path <path> --agent <lead> --force`."),

    # DB / .work not initialized
    (re.compile(r"no such table|unable to open database|minion\.db"),
     "Run `minion` once in the project root to initialize the .work/ directory, or use `-C <project-dir>` to target the right project."),

    # moon_crash active
    (re.compile(r"moon_crash active"),
     "A moon_crash halt is in effect. Wait for the lead to lift it: `minion trigger clear --trigger moon_crash`."),

    # Blocked by other tasks
    (re.compile(r"blocked_by|blocked by task"),
     "This task has unresolved blockers. Check dependencies with `minion task show --id <id>`."),
]


def _add_remediation_hint(data: dict[str, object]) -> dict[str, object]:
    """If data has an 'error' key, check against known patterns and add a 'hint' field."""
    error_msg = data.get("error")
    if not isinstance(error_msg, str):
        return data
    for pattern, hint in _REMEDIATION_HINTS:
        if pattern.search(error_msg):
            data = dict(data)  # shallow copy to avoid mutating caller's dict
            data["hint"] = hint
            return data
    return data


def output(data: dict[str, object], human: bool = False, compact: bool = False) -> None:
    """Print result as JSON (default), human-readable, or compact text."""
    if "error" in data:
        data = _add_remediation_hint(data)
        click.echo(json.dumps(data, indent=2, default=str))
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
