"""Walk the Click command tree and emit a structured CLI schema.

Used by `minion docs` to auto-generate cli-reference.md from the source of truth.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from importlib.metadata import version as pkg_version
from io import StringIO
from typing import Any

import click


# Flat aliases live below the "Hidden aliases" comment in cli.py.
# We skip them by collecting only commands that belong to groups.
_SKIP_PARAMS = {"help"}  # every command has --help, no need to document


def generate_cli_schema(cli: click.Group) -> dict[str, Any]:
    """Return structured dict of the entire CLI tree."""
    groups: list[dict] = []
    top_level_commands: list[dict] = []

    # Collect all commands that live inside a group so we can skip aliases
    grouped_cmds: set[int] = set()
    for name, cmd in sorted(cli.commands.items()):
        if isinstance(cmd, click.Group):
            for sub in cmd.commands.values():
                grouped_cmds.add(id(sub))

    for name, cmd in sorted(cli.commands.items()):
        if isinstance(cmd, click.Group):
            groups.append(_extract_group(name, cmd))
        elif id(cmd) not in grouped_cmds:
            # Top-level command that isn't an alias of a grouped command
            top_level_commands.append(_extract_command(name, cmd))

    return {
        "version": pkg_version("minion-factory"),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "groups": groups,
        "top_level_commands": top_level_commands,
    }


def _extract_group(name: str, group: click.Group) -> dict[str, Any]:
    commands = []
    for cmd_name, cmd in sorted(group.commands.items()):
        if not cmd.hidden:
            commands.append(_extract_command(cmd_name, cmd))
    return {
        "name": name,
        "help": group.help or "",
        "commands": commands,
    }


def _extract_command(name: str, cmd: click.Command) -> dict[str, Any]:
    params = []
    for p in cmd.params:
        if p.name in _SKIP_PARAMS or getattr(p, "hidden", False):
            continue
        param_info: dict[str, Any] = {
            "name": p.name,
            "type": p.type.name,
            "required": p.required,
        }
        default = p.default
        # Filter out Click's internal sentinel for required params
        if default is not None and not repr(default).startswith("Sentinel"):
            param_info["default"] = default
        if isinstance(p, click.Option):
            param_info["opts"] = p.opts
            param_info["is_flag"] = p.is_flag
            if p.help:
                param_info["help"] = p.help
        elif isinstance(p, click.Argument):
            param_info["opts"] = [p.name]
        params.append(param_info)
    return {
        "name": name,
        "help": cmd.help or "",
        "params": params,
    }


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------


def schema_to_markdown(schema: dict[str, Any]) -> str:
    """Render the schema dict as a markdown CLI reference."""
    out = StringIO()
    w = out.write

    w("# Minion CLI Reference\n\n")
    w(f"> Auto-generated from Click introspection — v{schema['version']}\n")
    w(f"> Generated: {schema['generated_at']}\n")
    w(">\n")
    w("> Regenerate: `minion docs --output docs/`\n\n")

    w("## Global Options\n\n")
    w("| Option | Description |\n")
    w("|--------|-------------|\n")
    w("| `--human` | Human-readable output instead of JSON |\n")
    w("| `--compact` | Concise text output for agent context injection |\n")
    w("| `--project-dir`, `-C` | Project directory (default: cwd) |\n")
    w("| `--version` | Show version and exit |\n\n")

    # Groups
    for i, group in enumerate(schema["groups"], 1):
        w(f"## {i}. {group['name']}\n\n")
        if group["help"]:
            w(f"{group['help']}\n\n")
        for cmd in group["commands"]:
            _write_command(w, f"minion {group['name']} {cmd['name']}", cmd)

    # Top-level commands
    if schema["top_level_commands"]:
        w(f"## {len(schema['groups']) + 1}. Top-Level Commands\n\n")
        for cmd in schema["top_level_commands"]:
            _write_command(w, f"minion {cmd['name']}", cmd)

    return out.getvalue()


def _write_command(w, usage_prefix: str, cmd: dict[str, Any]) -> None:
    w(f"### `{usage_prefix}`\n\n")
    if cmd["help"]:
        w(f"{cmd['help']}\n\n")
    if cmd["params"]:
        w("| Option | Type | Required | Default | Description |\n")
        w("|--------|------|----------|---------|-------------|\n")
        for p in cmd["params"]:
            opts = ", ".join(f"`{o}`" for o in p.get("opts", []))
            ptype = p["type"]
            req = "Yes" if p["required"] else ""
            default = f"`{p['default']}`" if "default" in p and p["default"] not in (None, "", False, 0) else ""
            desc = p.get("help", "")
            w(f"| {opts} | {ptype} | {req} | {default} | {desc} |\n")
        w("\n")
    else:
        w("*No options.*\n\n")


def schema_to_json(schema: dict[str, Any]) -> str:
    return json.dumps(schema, indent=2)
