"""Global group — who, send, deregister, prune.

Cross-repo coordination via ~/.minion/coordinator.db.
"""

from __future__ import annotations

import click

from minion.cli.main import _output


def register_commands(cli: click.Group) -> None:
    """Attach the global group and its subcommands to the root CLI."""

    @cli.group("global")
    @click.pass_context
    def global_group(ctx: click.Context) -> None:
        """Cross-repo coordination via the global coordinator DB (~/.minion/coordinator.db).

        Agents register locally AND globally. The coordinator enables cross-repo
        message routing and a unified view of all agents across all projects."""
        pass

    @global_group.command("who")
    @click.pass_context
    def global_who(ctx: click.Context) -> None:
        """List all agents across ALL projects from the coordinator DB.

        Shows every registered agent with their project_path, so you can see
        which repo each agent lives in. Useful for cross-repo coordination."""
        from minion.comms import who_global as _who_global
        _output(_who_global(), ctx.obj["human"])

    @global_group.command("send")
    @click.option("--from", "from_agent", required=True, help="Sender agent name")
    @click.option("--to", "to_agent", required=True, help="Target agent name (can be in a different repo)")
    @click.option("--message", required=True, help="Message content")
    @click.pass_context
    def global_send(ctx: click.Context, from_agent: str, to_agent: str, message: str) -> None:
        """Send a message to an agent in ANY repo via the coordinator.

        ALWAYS routes through the coordinator DB — never delivers to local DB.
        Looks up the target agent's project_path and writes the message to that
        project's .work/minion.db. The target agent's poll picks it up."""
        from minion.comms import send_global as _send_global
        _output(_send_global(from_agent, to_agent, message), ctx.obj["human"])

    @global_group.command("deregister")
    @click.option("--name", required=True, help="Agent name to remove from coordinator")
    @click.pass_context
    def global_deregister(ctx: click.Context, name: str) -> None:
        """Remove an agent from the global coordinator DB. Lead-only.

        Shows the agent's last_active and project_path before removing."""
        from minion.auth import require_class as _rc
        _rc("lead")(lambda: None)()
        from minion.comms import deregister_global as _deregister_global
        _output(_deregister_global(name), ctx.obj["human"])

    @global_group.command("prune")
    @click.option("--stale", required=True, type=str, help="Stale threshold, e.g. '30m' or '2h'")
    @click.pass_context
    def global_prune(ctx: click.Context, stale: str) -> None:
        """Remove agents that haven't been active in N minutes/hours. Lead-only.

        Examples: --stale 30m (30 minutes), --stale 2h (2 hours)."""
        from minion.auth import require_class as _rc
        _rc("lead")(lambda: None)()
        # Parse duration string
        stale = stale.strip().lower()
        if stale.endswith("h"):
            minutes = int(stale[:-1]) * 60
        elif stale.endswith("m"):
            minutes = int(stale[:-1])
        else:
            minutes = int(stale)
        from minion.comms import prune_global as _prune_global
        _output(_prune_global(minutes), ctx.obj["human"])
