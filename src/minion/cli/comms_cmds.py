"""Comms group — send (local/global), check-inbox, purge-inbox, list-history.
Messaging between agents within a repo (local) or across repos (global).

Purpose: Comms group — send (local/global), check-inbox, purge-inbox, list-history.
Rationale: Extracted into own module for single-responsibility CLI command grouping.
Responsibility: Comms group — send (local/global), check-inbox, purge-inbox, list-history. NOT responsible for unrelated concerns.
Organization: Click command group with subcommands."""

from __future__ import annotations

import click

from minion.cli.main import _agent_option, _output


def register_commands(cli: click.Group) -> None:
    """Attach the comms group and its subcommands to the root CLI."""

    @cli.group("comms")
    @click.pass_context
    def comms_group(ctx: click.Context) -> None:
        """Messaging. Use 'send local' or 'send global' to be explicit about routing."""
        pass

    @comms_group.group("send")
    @click.pass_context
    def send_group(ctx: click.Context) -> None:
        """Send messages to agents. Use 'local' or 'global' subcommand."""
        pass

    @send_group.command("local")
    @click.option("--from", "-f", "from_agent", required=True)
    @click.option("--to", "-t", "to_agent", required=True)
    @click.option("--message", "-m", required=True)
    @click.option("--cc", default="")
    @click.pass_context
    def send_local(ctx: click.Context, from_agent: str, to_agent: str, message: str, cc: str) -> None:
        """Send to a LOCAL agent (same repo) or 'all' for broadcast.

        \b
        Local only — delivers to agents in THIS repo's .work/minion.db.
        Target must be registered in the same project.
        For cross-repo, use: minion comms send global"""
        from minion.comms import send as _send
        _output(_send(from_agent, to_agent, message, cc), ctx.obj["human"])

    @send_group.command("global")
    @click.option("--from", "-f", "from_agent", required=True)
    @click.option("--to", "-t", "to_agent", required=True)
    @click.option("--message", "-m", required=True)
    @click.pass_context
    def send_global_via_comms(ctx: click.Context, from_agent: str, to_agent: str, message: str) -> None:
        """Send to an agent in ANY repo via the coordinator.

        \b
        Routes through ~/.minion/coordinator.db to find the target agent's
        project and delivers to that project's .work/minion.db.
        The target agent's poll picks it up."""
        from minion.comms import send_global as _send_global
        _output(_send_global(from_agent, to_agent, message), ctx.obj["human"])

    @comms_group.command("check-inbox")
    @_agent_option(required=True)
    @click.option("--silent", is_flag=True, default=False,
                  help="Raw message content only, no JSON. Empty output if no messages. For hooks.")
    @click.pass_context
    def check_inbox(ctx: click.Context, agent: str, silent: bool) -> None:
        """Check and clear unread messages.

        Use --silent for PostToolUse hooks: prints only message content,
        nothing if inbox is empty. Designed for high-frequency automated calls."""
        if silent:
            from minion.comms import check_inbox_silent as _check_inbox_silent
            output = _check_inbox_silent(agent)
            if output:
                click.echo(output)
        else:
            from minion.comms import check_inbox as _check_inbox
            _output(_check_inbox(agent), ctx.obj["human"])

    @comms_group.command("purge-inbox")
    @_agent_option(required=True)
    @click.option("--older-than-hours", default=2, type=int)
    @click.pass_context
    def purge_inbox(ctx: click.Context, agent: str, older_than_hours: int) -> None:
        """Delete old messages from inbox."""
        from minion.comms import purge_inbox as _purge_inbox
        _output(_purge_inbox(agent, older_than_hours), ctx.obj["human"])

    @comms_group.command("list-history")
    @click.option("--count", default=20, type=int)
    @click.pass_context
    def list_history(ctx: click.Context, count: int) -> None:
        """Return the last N messages across all agents."""
        from minion.comms import get_history as _get_history
        _output(_get_history(count), ctx.obj["human"])
