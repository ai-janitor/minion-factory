"""Coordinator group — preferred CLI for the coordinator daemon.

Delegates to the same daemon.py functions as `minion api`, but branded
as the explicit coordinator role. `minion api` still works for backward compat.

Purpose: Coordinator CLI — start/stop/status/restart the coordinator daemon.
Rationale: Makes the coordinator an explicit first-class concept, not just "the API server".
Responsibility: CLI wrappers for daemon lifecycle + coordinator-specific commands."""

from __future__ import annotations

import click

from minion.cli.main import _output


def register_commands(cli: click.Group) -> None:
    """Attach the coordinator group and its subcommands to the root CLI."""

    @cli.group("coordinator")
    @click.pass_context
    def coordinator_group(ctx: click.Context) -> None:
        """Coordinator daemon — the team hub.

        \b
        The coordinator is the network API server that all team agents
        register with. One machine runs the coordinator; others connect.

        \b
        Lifecycle:
          minion coordinator start      # Start daemon (auto-generates token + TLS)
          minion coordinator stop
          minion coordinator status
          minion coordinator restart

        \b
        Monitoring:
          minion coordinator snapshot    # Consolidated status snapshot
        """
        pass

    @coordinator_group.command("start")
    @click.option("--port", "-P", default=8377, type=int, help="TCP port (default: 8377)")
    @click.option("-p", "--password-file", default=None, type=click.Path(exists=True),
                  help="Read token from file (first line)")
    @click.option("--insecure", "-I", is_flag=True, help="No auth (dev only)")
    @click.pass_context
    def coord_start(ctx: click.Context, port: int, password_file: str | None, insecure: bool) -> None:
        """Start the coordinator daemon.

        \b
        Auth is ON by default. Token auto-generated on first start and
        saved to ~/.minion/.api-token. TLS cert auto-generated.

        \b
        Examples:
          minion coordinator start                # Auto-generates token
          minion coordinator start -p ~/token     # Read token from file
          minion coordinator start --insecure     # Dev mode, no auth
        """
        # Reuse the exact same logic as `minion api start`
        import getpass
        import sys

        token = ""
        generated = False
        if not insecure:
            if password_file:
                with open(password_file) as f:
                    token = f.readline().strip()
                if not token:
                    raise click.UsageError(f"Password file '{password_file}' is empty.")
            if not token:
                from minion.defaults import resolve_cluster_token
                token = resolve_cluster_token()
            if not token and sys.stdin.isatty():
                token = getpass.getpass("Cluster auth token: ")
            if not token:
                from minion.api.daemon import _read_token
                token = _read_token()
            if not token:
                import secrets
                token = secrets.token_urlsafe(32)
                generated = True

        from minion.api.daemon import start, _token_file
        result = start(port=port, token=token)
        if generated and result.get("status") == "started":
            token_path = str(_token_file())
            result["token_generated"] = True
            result["token_path"] = token_path
            result["token"] = token
        _output(result, ctx.obj["human"], ctx.obj["compact"])

    @coordinator_group.command("stop")
    @click.pass_context
    def coord_stop(ctx: click.Context) -> None:
        """Stop the coordinator daemon."""
        from minion.api.daemon import stop
        _output(stop(), ctx.obj["human"], ctx.obj["compact"])

    @coordinator_group.command("status")
    @click.pass_context
    def coord_status(ctx: click.Context) -> None:
        """Check coordinator daemon status."""
        from minion.api.daemon import status
        _output(status(), ctx.obj["human"], ctx.obj["compact"])

    @coordinator_group.command("restart")
    @click.option("--port", "-P", default=None, type=int, help="Override port on restart")
    @click.pass_context
    def coord_restart(ctx: click.Context, port: int | None) -> None:
        """Restart the coordinator daemon."""
        from minion.api.daemon import restart
        _output(restart(port=port), ctx.obj["human"], ctx.obj["compact"])

    @coordinator_group.command("snapshot")
    @click.option("--server", "-s", default="", help="API server URL (auto-detected if omitted)")
    @click.pass_context
    def coord_snapshot(ctx: click.Context, server: str) -> None:
        """Consolidated coordinator status snapshot.

        \b
        Returns server info, auth state, agents, unread messages, alerts,
        and projects in one call. Same data the menu bar app polls.

        \b
        Examples:
          minion coordinator snapshot
          minion coordinator snapshot -s https://192.168.0.31:8377
        """
        from minion.team import _get_team_client
        client, err = _get_team_client(server)
        if err:
            _output({"error": err}, ctx.obj["human"], ctx.obj["compact"])
            return
        _output(client.coordinator_status(), ctx.obj["human"], ctx.obj["compact"])
