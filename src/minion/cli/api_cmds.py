"""API group — start/stop/status/restart the network API server daemon.

Manages the API server as a background service via ~/.minion/api-server.json state.
"""

from __future__ import annotations

import click

from minion.cli.main import _output


def register_commands(cli: click.Group) -> None:
    """Attach the api group and its subcommands to the root CLI."""

    @cli.group("api")
    @click.pass_context
    def api_group(ctx: click.Context) -> None:
        """API server daemon — start/stop/status/restart.

        \b
        Manages the network API server as a background service.
        State tracked in ~/.minion/api-server.json.
        Logs written to ~/.minion/api-server.log.

        \b
        Quick start:
          minion api start           # Start on default port 8377
          minion api status          # Check if running + health
          minion api stop            # Graceful shutdown

        \b
        TLS is enabled by default — certs auto-generated on first start.
        Set MINION_NETWORK_INSECURE=1 to run plain HTTP (dev only).
        """
        pass

    @api_group.command("start")
    @click.option("--port", default=8377, type=int, help="TCP port (default: 8377)")
    @click.pass_context
    def api_start(ctx: click.Context, port: int) -> None:
        """Start the API server as a background daemon.

        \b
        Forks the server to background and returns immediately.
        Auto-generates TLS cert if missing (~/.minion/tls/).
        Fails if server is already running — stop first.

        \b
        Examples:
          minion api start                 # Default port 8377, TLS on
          minion api start --port 9000     # Custom port
          MINION_NETWORK_INSECURE=1 minion api start  # Plain HTTP
        """
        from minion.api.daemon import start
        result = start(port=port)
        _output(result, ctx.obj["human"], ctx.obj["compact"])

    @api_group.command("stop")
    @click.pass_context
    def api_stop(ctx: click.Context) -> None:
        """Stop the API server daemon.

        \b
        Sends SIGTERM for graceful shutdown (5s timeout).
        Falls back to SIGKILL if process doesn't exit.
        Clears state file on success.

        \b
        Example:
          minion api stop
        """
        from minion.api.daemon import stop
        result = stop()
        _output(result, ctx.obj["human"], ctx.obj["compact"])

    @api_group.command("status")
    @click.pass_context
    def api_status(ctx: click.Context) -> None:
        """Check API server daemon status.

        \b
        Reports: running/stopped, PID, port, TLS, uptime.
        Performs HTTP /health check to verify server is responsive.
        Clears stale state if PID is dead.

        \b
        Example:
          minion api status
        """
        from minion.api.daemon import status
        result = status()
        _output(result, ctx.obj["human"], ctx.obj["compact"])

    @api_group.command("restart")
    @click.option("--port", default=None, type=int, help="Override port on restart")
    @click.pass_context
    def api_restart(ctx: click.Context, port: int | None) -> None:
        """Restart the API server daemon (stop + start).

        \b
        Uses the current port from state file unless overridden.
        Waits briefly between stop and start for port release.

        \b
        Examples:
          minion api restart                 # Same port
          minion api restart --port 9000     # New port
        """
        from minion.api.daemon import restart
        result = restart(port=port)
        _output(result, ctx.obj["human"], ctx.obj["compact"])
