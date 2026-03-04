"""API group — start/stop/status/restart the network API server daemon.

Manages the API server as a background service via ~/.minion/api-server.json state.
"""

from __future__ import annotations

import os

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
          minion api start           # Prompts for auth token
          minion api status          # Check if running + health
          minion api stop            # Graceful shutdown

        \b
        TLS is enabled by default — certs auto-generated on first start.
        Set MINION_NETWORK_INSECURE=1 to run plain HTTP (dev only).
        """
        pass

    @api_group.command("start")
    @click.option("--port", default=8377, type=int, help="TCP port (default: 8377)")
    @click.option("-p", "--password-file", default=None, type=click.Path(exists=True),
                  help="Read token from file (first line). For automation/scripts.")
    @click.option("--insecure", is_flag=True, help="Allow starting without auth token (dev only)")
    @click.pass_context
    def api_start(ctx: click.Context, port: int, password_file: str | None, insecure: bool) -> None:
        """Start the API server as a background daemon.

        \b
        Auth token is required (unless --insecure). Three input methods
        in priority order:
          1. -p /path/to/file   — reads first line (automation/scripts)
          2. MINION_CLUSTER_TOKEN env var (CI/containers)
          3. Interactive prompt via getpass (humans at terminal)
        Token is hashed and saved so restart doesn't need re-entry.

        \b
        Forks the server to background and returns immediately.
        Auto-generates TLS cert if missing (~/.minion/tls/).
        Fails if server is already running — stop first.

        \b
        Examples:
          minion api start                      # Prompts for token
          minion api start -p ~/.minion/token    # Read from file
          minion api start --insecure            # Dev mode, no auth
        """
        import getpass

        token = ""
        if not insecure:
            # Priority 1: -p password file
            if password_file:
                with open(password_file) as f:
                    token = f.readline().strip()
                if not token:
                    raise click.UsageError(f"Password file '{password_file}' is empty.")
            # Priority 2: env var
            if not token:
                token = os.environ.get("MINION_CLUSTER_TOKEN", "")
            # Priority 3: interactive prompt
            if not token:
                token = getpass.getpass("Cluster auth token: ")
            if not token:
                raise click.UsageError(
                    "Auth token is required.\n"
                    "Provide via: -p <file>, MINION_CLUSTER_TOKEN env var, or interactive prompt.\n"
                    "Use --insecure to skip auth (dev only)."
                )

        from minion.api.daemon import start
        result = start(port=port, token=token)
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
