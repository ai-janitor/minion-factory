"""Team group — network-first multi-machine team coordination CLI.

Commands: join, who, send, inbox.
All route through the network API tier as source of truth.

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
        Join a project team, see who's on it, send messages, check inbox.
        All commands route through the network API tier — no need to think
        about local vs global vs API.

        \b
        Quick start:
          minion team join --agent myname --class lead
          minion team who
          minion team send --from myname --to peer --message "hello"
          minion team inbox --agent myname
        """
        pass

    @team_group.command("join")
    @click.option("--agent", "-a", required=True, help="Your agent name")
    @click.option("--class", "-c", "agent_class", default="coder", help="Agent class (lead, coder, recon, etc.)")
    @click.option("--model", "-m", default="", help="Model name (informational)")
    @click.option("--project", "-p", "project_dir", default=None, help="Project directory (default: cwd)")
    @click.option("--server", "-s", default="", help="API server URL (auto-detected if omitted)")
    @click.pass_context
    def team_join(ctx: click.Context, agent: str, agent_class: str, model: str,
                  project_dir: str | None, server: str) -> None:
        """Join a project team on the network tier.

        \b
        Registers your agent with the API server, then prints the team roster.
        The API server is auto-detected (local running instance or MINION_NETWORK_URL).

        \b
        Examples:
          minion team join --agent trashcan-lead --class lead --model claude-sonnet-4-6
          minion team join -a metal-coder -c coder -p ~/projects/llama-metal
        """
        from minion.team import join
        result = join(
            agent=agent,
            agent_class=agent_class,
            model=model,
            project_dir=project_dir or ctx.obj.get("project_dir") or "",
            server_url=server,
        )
        _output(result, ctx.obj["human"], ctx.obj["compact"])

    @team_group.command("who")
    @click.option("--project", "-p", "project_dir", default=None, help="Project directory (default: cwd)")
    @click.option("--server", "-s", default="", help="API server URL")
    @click.pass_context
    def team_who(ctx: click.Context, project_dir: str | None, server: str) -> None:
        """List all team members for this project across all machines.

        \b
        Shows name, machine, class, model, and presence for every agent
        registered to the same project on the network tier.

        \b
        Examples:
          minion team who
          minion team who -p ~/projects/llama-metal
        """
        from minion.team import who
        result = who(
            project_dir=project_dir or ctx.obj.get("project_dir") or "",
            server_url=server,
        )
        _output(result, ctx.obj["human"], ctx.obj["compact"])

    @team_group.command("send")
    @click.option("--from", "-f", "from_agent", required=True, help="Sender agent name")
    @click.option("--to", "-t", "to_agent", required=True, help="Recipient agent name")
    @click.option("--message", "-m", required=True, help="Message text")
    @click.option("--server", "-s", default="", help="API server URL")
    @click.pass_context
    def team_send(ctx: click.Context, from_agent: str, to_agent: str,
                  message: str, server: str) -> None:
        """Send a message to a team member via the network tier.

        \b
        No need to choose between local/global/API — this always routes
        through the network tier.

        \b
        Examples:
          minion team send --from trashcan-lead --to codex-lead --message "status?"
          minion team send -f me -t peer -m "done with task 3"
        """
        from minion.team import send
        result = send(
            from_agent=from_agent,
            to_agent=to_agent,
            message=message,
            server_url=server,
        )
        _output(result, ctx.obj["human"], ctx.obj["compact"])

    @team_group.command("inbox")
    @click.option("--agent", "-a", required=True, help="Agent name to check inbox for")
    @click.option("--server", "-s", default="", help="API server URL")
    @click.pass_context
    def team_inbox(ctx: click.Context, agent: str, server: str) -> None:
        """Check unread messages for an agent on the network tier.

        \b
        Fetches and marks as read all unread messages addressed to the agent.

        \b
        Examples:
          minion team inbox --agent trashcan-lead
          minion team inbox -a codex-lead
        """
        from minion.team import inbox
        result = inbox(agent=agent, server_url=server)
        _output(result, ctx.obj["human"], ctx.obj["compact"])
