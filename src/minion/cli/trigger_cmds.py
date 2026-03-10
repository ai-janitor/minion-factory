"""Trigger group — list, clear-moon-crash.
Manage trigger words that flag messages for special handling.

Purpose: Trigger group — list, clear-moon-crash.
Rationale: Extracted into own module for single-responsibility CLI command grouping.
Responsibility: Trigger group — list, clear-moon-crash. NOT responsible for unrelated concerns.
Organization: Click command group with subcommands."""

from __future__ import annotations

import click

from minion.cli.main import _agent_option, _output


def register_commands(cli: click.Group) -> None:
    """Attach the trigger group and its subcommands to the root CLI."""

    @cli.group("trigger")
    @click.pass_context
    def trigger_group(ctx: click.Context) -> None:
        """Manage trigger words that flag messages for special handling."""
        pass

    @trigger_group.command("list")
    @click.pass_context
    def list_triggers(ctx: click.Context) -> None:
        """Return the trigger word codebook."""
        from minion.triggers import get_triggers as _get_triggers
        _output(_get_triggers(), ctx.obj["human"])

    @trigger_group.command("clear-moon-crash")
    @_agent_option(required=True)
    @click.pass_context
    def clear_moon_crash(ctx: click.Context, agent: str) -> None:
        """Clear the emergency stop flag. Lead only."""
        from minion.auth import require_class
        require_class("lead")(lambda: None)()
        from minion.triggers import clear_moon_crash as _clear
        _output(_clear(agent), ctx.obj["human"])
