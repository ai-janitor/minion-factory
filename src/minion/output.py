"""CLI output formatting — human-readable (default), JSON (opt-in), and compact modes.

Exit code convention:
  0 = success
  1 = runtime error (command understood but failed)
  2 = usage error (bad args, missing required input)

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
    (re.compile(r"blocked_by|blocked by task|unresolved blockers"),
     "This task has unresolved blockers. Check dependencies with `minion task show --id <id>`."),

    # Unread messages blocking send
    (re.compile(r"unread message\(s\).*check-inbox"),
     "You must read your inbox before sending. Run: `minion comms check-inbox --agent <your-name>`."),

    # Context staleness blocking send
    (re.compile(r"context.*stale|stale.*context|staleness"),
     "Your context is stale. Update it: `minion set-context --agent <your-name> --context '<what you are doing>'`."),

    # Agent not registered in project (send errors)
    (re.compile(r"not registered in this project"),
     "Register in the current project first: `minion agent register --name <name> --class <role>`. "
     "Verify your cwd is the correct project root."),

    # Agent belongs to different project
    (re.compile(r"belongs to .*, not this repo"),
     "The target agent is in a different project. Use cross-repo messaging: "
     "`minion comms send global --from <you> --to <target> --message '<msg>'`."),

    # NETWORK_URL not set
    (re.compile(r"MINION_NETWORK_URL not set"),
     "Set the network URL: `export MINION_NETWORK_URL=http://<host>:<port>`. "
     "Or start the network server: `minion api serve`."),

    # Invalid class on registration
    (re.compile(r"Unknown class '([^']+)'"),
     "Valid agent classes: coder, lead, recon, auditor, builder. "
     "Example: `minion agent register --name <name> --class coder`."),

    # Model not allowed for class
    (re.compile(r"Model '([^']+)' not allowed for class"),
     "Check allowed models for your class. Re-register with a permitted model: "
     "`minion agent register --name <name> --class <role> --model <allowed-model>`."),

    # Race condition on task claim
    (re.compile(r"Race lost.*claimed by another"),
     "Another agent grabbed this task first. Run `minion task list --status open` to find available tasks."),

    # Only lead can do X
    (re.compile(r"Only lead-class agents can|Only lead can"),
     "This operation requires lead privileges. Ask your lead to perform it, "
     "or re-register as lead if you have authority: `minion agent register --name <name> --class lead`."),

    # Checklist required for in_progress transition
    (re.compile(r"requires --checklist"),
     "Generate a checklist first: `minion checklist generate --agent <name> --task-id <id> --type <role>`, "
     "then pass it: `minion task update --agent <name> --id <id> --status in_progress --checklist <path>`."),

    # Scaffolding incomplete
    (re.compile(r"Scaffolding incomplete.*Missing files"),
     "Create the missing scaffold files before advancing. The DAG requires all planned files to exist "
     "before implementation begins. Stub them with comment headers first."),

    # Invalid status transition
    (re.compile(r"Invalid status '([^']+)'.*Valid:"),
     "The status you specified is not valid for this flow. Check valid statuses with `minion task show --id <id>`."),

    # No transition from current status
    (re.compile(r"No transition from '([^']+)'"),
     "The task cannot advance from its current stage. Check the DAG flow with `minion task lineage --id <id>` "
     "or `minion flow list` to see stage transitions."),

    # Battle plan not found
    (re.compile(r"Battle plan #?\d+ not found"),
     "Run `minion show-battle-plan` to see existing battle plans."),

    # Invalid priority (raid log / backlog)
    (re.compile(r"Invalid priority '([^']+)'.*Valid:"),
     "Use one of the valid priority levels listed in the error message."),

    # Backlog item not found
    (re.compile(r"Backlog item .* not found"),
     "Run `minion backlog list` to see available backlog items."),

    # Requirement not found / not registered
    (re.compile(r"Requirement '([^']+)' not (found|registered)"),
     "Run `minion req list` to see registered requirements. "
     "Create one with: `minion req create --path <path> --title '<title>'`."),

    # Crew not found
    (re.compile(r"Crew '([^']+)' not found"),
     "Run `minion list-crews` to see available crew YAML files."),

    # tmux required
    (re.compile(r"tmux required"),
     "Install tmux to spawn daemon workers. On macOS: `brew install tmux`. On Linux: `apt install tmux`."),

    # PyYAML required
    (re.compile(r"PyYAML required"),
     "Install PyYAML: `pip install pyyaml` or `uv pip install pyyaml`."),

    # Spec file not found / no task_file
    (re.compile(r"has no task_file set|spec file not found"),
     "Create a task spec: `minion task define --title '<title>' --flow <type>` or attach one with "
     "`minion task update --id <id> --task-file <path>`."),

    # No result file for close
    (re.compile(r"has no result file.*submit-result"),
     "Submit a result before closing: `minion task result --agent <name> --id <id> --file <path>`."),

    # Coordinator DB errors
    (re.compile(r"Coordinator DB"),
     "The coordinator database may be unavailable. Ensure the minion daemon is running, or check "
     "file permissions on ~/.minion_work/coordinator.db."),

    # Remote not configured
    (re.compile(r"Remote '([^']+)' not (found|configured)|No remote configured"),
     "Configure a remote: `minion api set-remote --name <name> --url <url>`."),

    # Intel doc not registered
    (re.compile(r"Intel doc '([^']+)' not registered"),
     "Register the intel doc first: `minion intel add --slug <slug> --path <file>`. "
     "List registered docs: `minion intel list`."),

    # File not found (generic)
    (re.compile(r"File not found:|not found:.*\."),
     "Verify the file path exists. Use absolute paths or paths relative to the project root."),
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


def output(data: dict[str, object], human: bool = True, compact: bool = False) -> None:
    """Print result as human-readable text (default), JSON, or compact text.

    The `human` parameter controls the output mode:
      - True (default): human-readable key: value pairs
      - False: JSON output for scripts and programmatic consumption

    The CLI layer resolves the default based on flags and environment:
      - Default: human=True (interactive CLI)
      - --json flag: human=False
      - MINION_CLASS env var set: human=False (daemon agents)
      - --human flag (legacy, hidden): human=True (overrides daemon auto-JSON)

    Backlog #306: when stdout is being piped (not a tty), automatically emit
    valid JSON regardless of `human`. The yaml-ish "key: json" form is
    convenient for terminals but breaks `| jq` and `| python -m json.tool`.

    Exit codes: 0=success, 1=error. Usage errors (exit 2) are handled by Click.
    """
    # Backlog #306: piped stdout => emit clean JSON so consumers can parse it.
    if human and not compact:
        try:
            if not sys.stdout.isatty():
                human = False
        except (AttributeError, ValueError):
            pass
    if "error" in data:
        data = _add_remediation_hint(data)
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
