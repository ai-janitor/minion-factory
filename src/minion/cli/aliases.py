"""Backwards-compat aliases — old flat command names registered on the root CLI.

All aliases are hidden from --help to encourage the new grouped syntax,
but remain functional so existing scripts and agents don't break.
"""

from __future__ import annotations

import click


def register_aliases(cli: click.Group) -> None:
    """Register hidden flat-name aliases for all grouped commands on the root CLI.

    The commands are already registered under their groups. This function
    finds them and adds top-level aliases that are hidden from --help.
    """
    # Collect the group commands we need to alias
    agent_group = cli.commands["agent"]
    comms_group = cli.commands["comms"]
    task_group = cli.commands["task"]
    flow_group = cli.commands["flow"]
    war_group = cli.commands["war"]
    file_group = cli.commands["file"]
    crew_group = cli.commands["crew"]
    trigger_group = cli.commands["trigger"]
    daemon_group = cli.commands["daemon"]

    # Build alias map: {top-level-name: (group, subcommand-name)}
    # For nested groups like comms > send > local, we dig deeper.
    _alias_map: dict[str, click.BaseCommand] = {}

    # Agent group aliases
    for sub_name in ["register", "set-status", "set-context", "who", "update-hp",
                     "cold-start", "fenix-down", "check-activity", "check-freshness"]:
        cmd = agent_group.commands.get(sub_name)  # type: ignore[union-attr]
        if cmd:
            _alias_map[sub_name] = cmd
    retire_cmd = agent_group.commands.get("retire")  # type: ignore[union-attr]
    if retire_cmd:
        _alias_map["retire-agent"] = retire_cmd

    # Comms group aliases
    send_group = comms_group.commands.get("send")  # type: ignore[union-attr]
    if send_group:
        local_cmd = send_group.commands.get("local")  # type: ignore[union-attr]
        if local_cmd:
            _alias_map["send-local"] = local_cmd
        global_cmd = send_group.commands.get("global")  # type: ignore[union-attr]
        if global_cmd:
            _alias_map["send-global"] = global_cmd
    for sub_name in ["check-inbox", "purge-inbox", "list-history"]:
        cmd = comms_group.commands.get(sub_name)  # type: ignore[union-attr]
        if cmd:
            _alias_map[sub_name] = cmd

    # Task group aliases
    for orig, alias in [("create", "create-task"), ("assign", "assign-task"),
                        ("update", "update-task"), ("list", "list-tasks"),
                        ("get", "get-task"), ("lineage", "task-lineage"),
                        ("submit-result", "submit-result"), ("close", "close-task"),
                        ("reopen", "reopen-task"), ("pull", "pull-task"),
                        ("complete-phase", "complete-phase"), ("check-work", "check-work")]:
        cmd = task_group.commands.get(orig)  # type: ignore[union-attr]
        if cmd:
            _alias_map[alias] = cmd

    # Flow group aliases
    for orig, alias in [("list", "list-flows"), ("show", "show-flow"),
                        ("next-status", "next-status"), ("transition", "transition")]:
        cmd = flow_group.commands.get(orig)  # type: ignore[union-attr]
        if cmd:
            _alias_map[alias] = cmd

    # War group aliases
    for orig, alias in [("set-plan", "set-battle-plan"), ("get-plan", "get-battle-plan"),
                        ("update-status", "update-battle-plan-status"),
                        ("log", "log-raid"), ("list-log", "list-raid-log")]:
        cmd = war_group.commands.get(orig)  # type: ignore[union-attr]
        if cmd:
            _alias_map[alias] = cmd

    # File group aliases
    for orig, alias in [("claim", "claim-file"), ("release", "release-file"),
                        ("list", "list-claims")]:
        cmd = file_group.commands.get(orig)  # type: ignore[union-attr]
        if cmd:
            _alias_map[alias] = cmd

    # Crew group aliases
    for orig, alias in [("list", "list-crews"), ("spawn", "spawn-party"),
                        ("stand-down", "stand-down"), ("halt", "halt"),
                        ("recruit", "recruit"), ("hand-off-zone", "hand-off-zone"),
                        ("status", "party-status")]:
        cmd = crew_group.commands.get(orig)  # type: ignore[union-attr]
        if cmd:
            _alias_map[alias] = cmd

    # Trigger group aliases
    for orig, alias in [("list", "list-triggers"), ("clear-moon-crash", "clear-moon-crash")]:
        cmd = trigger_group.commands.get(orig)  # type: ignore[union-attr]
        if cmd:
            _alias_map[alias] = cmd

    # Daemon group aliases
    for orig, alias in [("run", "daemon-run"), ("start", "start"),
                        ("stop", "stop"), ("logs", "logs")]:
        cmd = daemon_group.commands.get(orig)  # type: ignore[union-attr]
        if cmd:
            _alias_map[alias] = cmd

    # Legacy get-* collection name aliases
    list_tasks_cmd = task_group.commands.get("list")  # type: ignore[union-attr]
    if list_tasks_cmd:
        _alias_map["get-tasks"] = list_tasks_cmd
    list_history_cmd = comms_group.commands.get("list-history")  # type: ignore[union-attr]
    if list_history_cmd:
        _alias_map["get-history"] = list_history_cmd
    list_raid_cmd = war_group.commands.get("list-log")  # type: ignore[union-attr]
    if list_raid_cmd:
        _alias_map["get-raid-log"] = list_raid_cmd
    list_claims_cmd = file_group.commands.get("list")  # type: ignore[union-attr]
    if list_claims_cmd:
        _alias_map["get-claims"] = list_claims_cmd
    list_triggers_cmd = trigger_group.commands.get("list")  # type: ignore[union-attr]
    if list_triggers_cmd:
        _alias_map["get-triggers"] = list_triggers_cmd

    # Register all aliases as hidden commands
    for alias_name, orig_cmd in _alias_map.items():
        wrapper = click.Command(
            name=alias_name,
            callback=orig_cmd.callback,
            params=orig_cmd.params,
            help=orig_cmd.help,
            hidden=True,
        )
        cli.add_command(wrapper, alias_name)
