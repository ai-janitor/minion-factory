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
    @click.option("--last", "-n", "last_n", default=None, type=int, help="Show last N messages (includes read)")
    @click.option("--include-read", is_flag=True, help="Include already-read messages")
    @click.pass_context
    def team_inbox(ctx: click.Context, agent: str, channel: str, server: str,
                   last_n: int | None, include_read: bool) -> None:
        """Check messages for an agent.

        \b
        Default: unread messages only.
        --last N: show most recent N messages (including read).
        --include-read: include already-read messages.

        \b
        Each message shows read provenance (read_by_agent, read_at, read_via).

        \b
        Examples:
          minion team inbox --agent trashcan-lead
          minion team inbox -a codex-lead --last 5
          minion team inbox -a me --include-read --channel llama-metal
        """
        from minion.team import inbox
        result = inbox(agent=agent, channel=channel, server_url=server,
                       last_n=last_n, include_read=include_read)
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

    @team_group.command("ping")
    @click.option("--from", "-f", "from_agent", required=True, help="Sender agent name")
    @click.option("--to", "-t", "to_agent", required=True, help="Target agent name")
    @click.option("--server", "-s", default="", help="API server URL or alias")
    @click.pass_context
    def team_ping(ctx: click.Context, from_agent: str, to_agent: str, server: str) -> None:
        """Send a ping and verify round-trip delivery.

        \b
        Sends a timestamped message and immediately checks the target's
        inbox to confirm delivery. Reports status and latency.

        \b
        Examples:
          minion team ping --from trashcan-lead --to codex-lead
        """
        from minion.team import ping
        result = ping(from_agent=from_agent, to_agent=to_agent, server_url=server)
        _output(result, ctx.obj["human"], ctx.obj["compact"])

    @team_group.command("clone")
    @click.argument("channel")
    @click.option("--target", "-t", default="", help="Target directory (default: ./<channel-name>)")
    @click.option("--server", "-s", default="", help="API server URL or alias")
    @click.pass_context
    def team_clone(ctx: click.Context, channel: str, target: str, server: str) -> None:
        """Clone a project workspace from the coordinator's git info.

        \b
        Reads git_remote and git_branch from the channel metadata
        and clones the repo. Git info is set automatically when
        agents join from a machine that has the repo.

        \b
        Examples:
          minion team clone llama-metal
          minion team clone llama-metal --target ~/projects/llama-metal
        """
        from minion.team import clone
        result = clone(channel=channel, target_dir=target, server_url=server)
        _output(result, ctx.obj["human"], ctx.obj["compact"])

    @team_group.command("poll")
    @click.option("--agent", "-a", required=True, help="Agent name to poll as")
    @click.option("--channel", "-ch", default="", help="Channel filter")
    @click.option("--server", "-s", default="", help="Server alias or URL")
    @click.option("--interval", "-i", default=5, type=int, help="Poll interval in seconds (default: 5)")
    @click.option("--mode", type=click.Choice(["foreground", "notify"]), default="foreground",
                  help="foreground=delivery (marks read), notify=hint only (stays unread)")
    def team_poll(agent: str, channel: str, server: str, interval: int, mode: str) -> None:
        """Live poll loop — delivers messages as they arrive.

        \b
        foreground (default): prints full messages, marks read after display.
        notify: prints unread hints only, messages stay unread for manual inbox.

        \b
        Ctrl+C to stop. Only one poller per agent allowed.

        \b
        Examples:
          minion team poll --agent trashcan-lead
          minion team poll -a me --mode notify --interval 10
        """
        from minion.team_poll import run_poll_loop
        run_poll_loop(agent=agent, server_url=server, channel=channel,
                      interval=interval, mode=mode)

    @team_group.command("poll-stop")
    @click.option("--agent", "-a", required=True, help="Agent name to stop polling")
    @click.pass_context
    def team_poll_stop(ctx: click.Context, agent: str) -> None:
        """Stop a running poll loop for an agent."""
        from minion.team_poll import stop_poller
        _output(stop_poller(agent), ctx.obj["human"], ctx.obj["compact"])

    @team_group.command("poll-list")
    @click.pass_context
    def team_poll_list(ctx: click.Context) -> None:
        """List active poll loops."""
        from minion.team_poll import list_pollers
        _output({"pollers": list_pollers()}, ctx.obj["human"], ctx.obj["compact"])

    @team_group.command("backlog")
    @click.option("--channel", "-ch", default="", help="Channel/project name (default: from cwd)")
    @click.option("--server", "-s", default="", help="Server alias or URL")
    @click.option("--status", default=None, help="Filter by status (open, promoted, killed, deferred)")
    @click.option("--priority", default=None, help="Filter by priority (high, medium, low)")
    @click.pass_context
    def team_backlog(ctx: click.Context, channel: str, server: str,
                     status: str | None, priority: str | None) -> None:
        """View backlog for a channel/project.

        \b
        Examples:
          minion team backlog
          minion team backlog --channel llama-metal --status open
        """
        from minion.team import _get_team_client, _channel_name
        channel = channel or _channel_name(ctx.obj.get("project_dir") or "")
        client, err = _get_team_client(server)
        if err:
            _output({"error": err}, ctx.obj["human"], ctx.obj["compact"])
            return
        kwargs = {}
        if status:
            kwargs["status"] = status
        if priority:
            kwargs["priority"] = priority
        _output(client.project_backlog(channel, **kwargs), ctx.obj["human"], ctx.obj["compact"])

    @team_group.command("tasks")
    @click.option("--channel", "-ch", default="", help="Channel/project name (default: from cwd)")
    @click.option("--server", "-s", default="", help="Server alias or URL")
    @click.option("--status", default=None, help="Filter by status (open, assigned, in_progress, closed)")
    @click.option("--assigned-to", default=None, help="Filter by assignee")
    @click.pass_context
    def team_tasks(ctx: click.Context, channel: str, server: str,
                   status: str | None, assigned_to: str | None) -> None:
        """View tasks for a channel/project.

        \b
        Examples:
          minion team tasks
          minion team tasks --channel llama-metal --status open
          minion team tasks --assigned-to metal-coder
        """
        from minion.team import _get_team_client, _channel_name
        channel = channel or _channel_name(ctx.obj.get("project_dir") or "")
        client, err = _get_team_client(server)
        if err:
            _output({"error": err}, ctx.obj["human"], ctx.obj["compact"])
            return
        kwargs = {}
        if status:
            kwargs["status"] = status
        if assigned_to:
            kwargs["assigned_to"] = assigned_to
        _output(client.project_tasks(channel, **kwargs), ctx.obj["human"], ctx.obj["compact"])

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
