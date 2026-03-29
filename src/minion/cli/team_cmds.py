"""Team group — network-first multi-machine team coordination CLI.

Commands: join, who, send, inbox, channels.
All route through the network API tier via first-class channels.

Purpose: Team group — network-first multi-machine team coordination CLI.
Rationale: Eliminates local/global/API confusion with one unified command set.
Responsibility: CLI wrappers for minion.team functions. NOT responsible for
  network transport, daemon lifecycle, or local DB comms."""

from __future__ import annotations

import click

from minion.cli.main import _output


def register_commands(cli: click.Group) -> None:
    """Attach the team group and its subcommands to the root CLI."""

    @cli.group("team")
    @click.pass_context
    def team_group(ctx: click.Context) -> None:
        """Network-first team coordination.

        \b
        Join a channel, see who's on it, send messages, check inbox.
        All commands route through the network API tier — no need to think
        about local vs global vs API.

        \b
        Quick start:
          minion team join --agent myname --class lead
          minion team who
          minion team send --from myname --to peer --message "hello"
          minion team inbox --agent myname
          minion team channels
        """
        pass

    @team_group.command("join")
    @click.option("--agent", "-a", required=True, help="Your agent name")
    @click.option("--class", "-c", "agent_class", default="coder", help="Agent class (lead, coder, recon, etc.)")
    @click.option("--model", "-m", default="", help="Model name (informational)")
    @click.option("--project", "-p", "project_dir", default=None, help="Project directory (default: cwd)")
    @click.option("--channel", "-ch", default="", help="Channel name (default: derived from project dir)")
    @click.option("--server", "-s", default="", help="API server URL (auto-detected if omitted)")
    @click.pass_context
    def team_join(ctx: click.Context, agent: str, agent_class: str, model: str,
                  project_dir: str | None, channel: str, server: str) -> None:
        """Join a project channel on the network tier.

        \b
        Registers your agent and joins the channel. Channel name defaults
        to the project directory name (e.g., "llama-metal").

        \b
        Examples:
          minion team join --agent trashcan-lead --class lead
          minion team join -a metal-coder -c coder --channel llama-metal
        """
        from minion.team import join
        result = join(
            agent=agent,
            agent_class=agent_class,
            model=model,
            project_dir=project_dir or ctx.obj.get("project_dir") or "",
            channel=channel,
            server_url=server,
        )
        _output(result, ctx.obj["human"], ctx.obj["compact"])

    @team_group.command("who")
    @click.option("--project", "-p", "project_dir", default=None, help="Project directory (default: cwd)")
    @click.option("--channel", "-ch", default="", help="Channel name (default: derived from project dir)")
    @click.option("--server", "-s", default="", help="API server URL")
    @click.pass_context
    def team_who(ctx: click.Context, project_dir: str | None, channel: str, server: str) -> None:
        """List all team members in a channel across all machines.

        \b
        Examples:
          minion team who
          minion team who --channel llama-metal
        """
        from minion.team import who
        result = who(
            project_dir=project_dir or ctx.obj.get("project_dir") or "",
            channel=channel,
            server_url=server,
        )
        _output(result, ctx.obj["human"], ctx.obj["compact"])

    @team_group.command("send")
    @click.option("--from", "-f", "from_agent", required=True, help="Sender agent name")
    @click.option("--to", "-t", "to_agent", required=True, help="Recipient agent name")
    @click.option("--message", "-m", required=True, help="Message text")
    @click.option("--channel", "-ch", default="", help="Channel name (default: derived from cwd)")
    @click.option("--server", "-s", default="", help="API server URL")
    @click.pass_context
    def team_send(ctx: click.Context, from_agent: str, to_agent: str,
                  message: str, channel: str, server: str) -> None:
        """Send a message to a team member, scoped to a channel.

        \b
        Examples:
          minion team send --from trashcan-lead --to codex-lead --message "status?"
          minion team send -f me -t peer -m "done" --channel llama-metal
        """
        from minion.team import send
        result = send(
            from_agent=from_agent,
            to_agent=to_agent,
            message=message,
            channel=channel,
            server_url=server,
        )
        _output(result, ctx.obj["human"], ctx.obj["compact"])

    @team_group.command("inbox")
    @click.option("--agent", "-a", required=True, help="Agent name to check inbox for")
    @click.option("--channel", "-ch", default="", help="Channel name (default: all channels)")
    @click.option("--server", "-s", default="", help="API server URL (default: all joined coordinators)")
    @click.pass_context
    def team_inbox(ctx: click.Context, agent: str, channel: str, server: str) -> None:
        """Check unread messages for an agent.

        \b
        By default, aggregates unread messages across ALL joined coordinators.
        Each message is tagged with its coordinator URL.
        Use --server to scope to one coordinator, --channel for one channel.

        \b
        Examples:
          minion team inbox --agent trashcan-lead
          minion team inbox -a codex-lead --channel llama-metal
          minion team inbox -a me --server https://192.168.0.31:8377
        """
        from minion.team import inbox
        result = inbox(agent=agent, channel=channel, server_url=server)
        _output(result, ctx.obj["human"], ctx.obj["compact"])

    @team_group.command("channels")
    @click.option("--server", "-s", default="", help="API server URL")
    @click.pass_context
    def team_channels(ctx: click.Context, server: str) -> None:
        """List all channels on the network tier.

        \b
        Shows channel name, member count, and unread message count.

        \b
        Examples:
          minion team channels
        """
        from minion.team import channels
        result = channels(server_url=server)
        _output(result, ctx.obj["human"], ctx.obj["compact"])

    @team_group.command("coordinators")
    @click.pass_context
    def team_coordinators(ctx: click.Context) -> None:
        """List all coordinators this CLI has joined.

        \b
        Shows coordinator URLs and the identities (channel/agent) joined on each.

        \b
        Examples:
          minion team coordinators
        """
        from minion.team import coordinators
        _output(coordinators(), ctx.obj["human"], ctx.obj["compact"])

    @team_group.command("identities")
    @click.pass_context
    def team_identities(ctx: click.Context) -> None:
        """List all saved team identities.

        \b
        Shows every coordinator/channel/agent combination this CLI has joined.

        \b
        Examples:
          minion team identities
        """
        from minion.team import identities
        _output(identities(), ctx.obj["human"], ctx.obj["compact"])
