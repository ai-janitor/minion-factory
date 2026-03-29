"""API group — server daemon + remote client CLI.
Server: start/stop/status/restart the network API server daemon.
Remote: set-remote + remote-* commands for operating against remote servers.
Manages state via ~/.minion/api-server.json and ~/.minion/remotes.json.

Purpose: API group — server daemon + remote client CLI.
Rationale: Extracted into own module for single-responsibility CLI command grouping.
Responsibility: API group — server daemon + remote client CLI. NOT responsible for unrelated concerns.
Organization: Click command group with subcommands."""

from __future__ import annotations

import os

import click

from minion.cli.main import _output


def register_commands(cli: click.Group) -> None:
    """Attach the api group and its subcommands to the root CLI."""

    @cli.group("api")
    @click.pass_context
    def api_group(ctx: click.Context) -> None:
        """API server daemon + remote client.

        \b
        Server (this machine):
          minion api start           # Start API server daemon
          minion api stop / status / restart

        \b
        Remote (other machines):
          minion api set-remote https://host:8377   # Configure remote
          minion api remote-status [--remote name]  # Health check
          minion api remote-agents [--remote name]  # List agents
          minion api remote-send / remote-inbox / remote-projects / ...

        \b
        Named profiles for multi-machine setups:
          minion api set-remote https://lab1:8377 --name lab1
          minion api remote-agents --remote lab1
        """
        pass

    @api_group.command("start")
    @click.option("--port", "-P", default=8377, type=int, help="TCP port (default: 8377)")
    @click.option("-p", "--password-file", default=None, type=click.Path(exists=True),
                  help="Read token from file (first line). For automation/scripts.")
    @click.option("--insecure", "-I", is_flag=True, help="Allow starting without auth token (dev only)")
    @click.pass_context
    def api_start(ctx: click.Context, port: int, password_file: str | None, insecure: bool) -> None:
        """Start the API server as a background daemon.

        \b
        Auth is ON by default. Token resolution order:
          1. -p /path/to/file   — reads first line (automation/scripts)
          2. MINION_CLUSTER_TOKEN env var (CI/containers)
          3. Interactive prompt via getpass (humans at terminal)
          4. Saved token from previous start (~/.minion/.api-token)
          5. Auto-generate a secure random token (first start)
        Token is saved to ~/.minion/.api-token (chmod 600) and reused
        on restart. On first generation, the token is printed once.

        \b
        Forks the server to background and returns immediately.
        Auto-generates TLS cert if missing (~/.minion/tls/).
        Fails if server is already running — stop first.

        \b
        Examples:
          minion api start                      # Auto-generates token on first run
          minion api start -p ~/.minion/token    # Read from file
          minion api start --insecure            # Dev mode, no auth (NOT recommended)
        """
        import getpass
        import sys

        token = ""
        generated = False
        if not insecure:
            # Priority 1: -p password file
            if password_file:
                with open(password_file) as f:
                    token = f.readline().strip()
                if not token:
                    raise click.UsageError(f"Password file '{password_file}' is empty.")
            # Priority 2: env var
            if not token:
                from minion.defaults import resolve_cluster_token
                token = resolve_cluster_token()
            # Priority 3: interactive prompt — only when stdin is a real TTY (not an agent/pipe)
            if not token and sys.stdin.isatty():
                token = getpass.getpass("Cluster auth token: ")
            # Priority 4: reuse previously saved token from ~/.minion/.api-token
            if not token:
                from minion.api.daemon import _read_token
                token = _read_token()
            # Priority 5: auto-generate a secure random token on first start
            if not token:
                import secrets
                token = secrets.token_urlsafe(32)
                generated = True

        from minion.api.daemon import start, _token_file
        result = start(port=port, token=token)
        # On first-time auto-generation, tell the user where the token lives
        if generated and result.get("status") == "started":
            token_path = str(_token_file())
            result["token_generated"] = True
            result["token_path"] = token_path
            result["token"] = token
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
    @click.option("--port", "-P", default=None, type=int, help="Override port on restart")
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

    # --- Remote client commands ---

    def _resolve_token(password_file: str | None, insecure: bool) -> str:
        """Resolve token from -p file, env var, or getpass prompt.

        --insecure makes token optional but doesn't ignore -p or env var.
        getpass only called when stdin is a real TTY — agents and pipes get a UsageError instead.
        """
        import getpass
        import sys
        token = ""
        if password_file:
            with open(password_file) as f:
                token = f.readline().strip()
            if not token:
                raise click.UsageError(f"Password file '{password_file}' is empty.")
        if not token:
            # SU-16: Route env reads through defaults.py for consistency
            from minion.defaults import resolve_cluster_token
            token = resolve_cluster_token()
        if not token and not insecure and sys.stdin.isatty():
            token = getpass.getpass("Cluster auth token: ")
        if not token and not insecure:
            raise click.UsageError("Auth token required. Use -p <file>, env var, or prompt.")
        return token

    @api_group.command("set-remote")
    @click.argument("url")
    @click.option("--name", "-n", default="default", help="Profile name (default: 'default')")
    @click.option("-p", "--password-file", default=None, type=click.Path(exists=True),
                  help="Read token from file (first line)")
    @click.option("--insecure", "-I", is_flag=True, help="Skip TLS verification (for self-signed certs). Auth token still required.")
    @click.pass_context
    def api_set_remote(ctx: click.Context, url: str, name: str,
                       password_file: str | None, insecure: bool) -> None:
        """Configure a remote API server connection.

        \b
        URL is the remote server address (e.g. https://machine-a:8377).
        Token input: -p file > MINION_CLUSTER_TOKEN env > getpass prompt.
        Use --name for multi-machine profiles.

        \b
        Examples:
          minion api set-remote https://server:8377
          minion api set-remote https://lab1:8377 --name lab1 -p ~/token.txt
          minion api set-remote https://hub:8377 --name hub --insecure  # self-signed TLS
        """
        token = _resolve_token(password_file, insecure)
        from minion.api.remotes import save_remote
        result = save_remote(name=name, url=url, token=token, insecure=insecure)
        _output(result, ctx.obj["human"], ctx.obj["compact"])

    @api_group.command("list-remotes")
    @click.pass_context
    def api_list_remotes(ctx: click.Context) -> None:
        """List configured remote profiles."""
        from minion.api.remotes import list_remotes
        result = list_remotes()
        _output(result, ctx.obj["human"], ctx.obj["compact"])

    @api_group.command("remove-remote")
    @click.argument("name")
    @click.pass_context
    def api_remove_remote(ctx: click.Context, name: str) -> None:
        """Remove a remote profile."""
        from minion.api.remotes import remove_remote
        result = remove_remote(name)
        _output(result, ctx.obj["human"], ctx.obj["compact"])

    # Helper: get remote client or error
    def _get_remote(ctx: click.Context, remote: str | None):
        from minion.api.remotes import get_remote_client
        client, err = get_remote_client(remote)
        if err:
            _output(err, ctx.obj["human"], ctx.obj["compact"])
            raise SystemExit(1)
        return client

    @api_group.command("remote-status")
    @click.option("--remote", "-r", default=None, help="Remote profile name")
    @click.pass_context
    def api_remote_status(ctx: click.Context, remote: str | None) -> None:
        """Health check on remote API server."""
        client = _get_remote(ctx, remote)
        _output(client.health(), ctx.obj["human"], ctx.obj["compact"])

    @api_group.command("remote-agents")
    @click.option("--remote", "-r", default=None, help="Remote profile name")
    @click.pass_context
    def api_remote_agents(ctx: click.Context, remote: str | None) -> None:
        """List agents on remote machine."""
        client = _get_remote(ctx, remote)
        _output(client.who(), ctx.obj["human"], ctx.obj["compact"])

    @api_group.command("remote-send")
    @click.option("--from", "-f", "from_agent", required=True, help="Sender agent name")
    @click.option("--to", "-t", "to_agent", required=True, help="Recipient agent name")
    @click.option("--message", "-m", required=True, help="Message text")
    @click.option("--remote", "-r", default=None, help="Remote profile name")
    @click.pass_context
    def api_remote_send(ctx: click.Context, from_agent: str, to_agent: str,
                        message: str, remote: str | None) -> None:
        """Send a message via remote API server."""
        client = _get_remote(ctx, remote)
        _output(client.send(from_agent, to_agent, message), ctx.obj["human"], ctx.obj["compact"])

    @api_group.command("remote-inbox")
    @click.option("--agent", "-a", required=True, help="Agent name")
    @click.option("--remote", "-r", default=None, help="Remote profile name")
    @click.pass_context
    def api_remote_inbox(ctx: click.Context, agent: str, remote: str | None) -> None:
        """Check inbox on remote machine (uses safe peek + mark-read)."""
        client = _get_remote(ctx, remote)
        # Two-step safe delivery: peek first, mark read after successful display
        result = client.check_inbox(agent, peek=True)
        messages = result.get("messages", [])
        if messages:
            ids = [m["id"] for m in messages if isinstance(m.get("id"), int)]
            if ids:
                client.mark_read(agent, ids, read_via="api_remote_inbox")
        _output(result, ctx.obj["human"], ctx.obj["compact"])

    @api_group.command("remote-projects")
    @click.option("--remote", "-r", default=None, help="Remote profile name")
    @click.pass_context
    def api_remote_projects(ctx: click.Context, remote: str | None) -> None:
        """List projects on remote machine."""
        client = _get_remote(ctx, remote)
        _output(client.list_projects(), ctx.obj["human"], ctx.obj["compact"])

    @api_group.command("remote-overview")
    @click.option("--remote", "-r", default=None, help="Remote profile name")
    @click.pass_context
    def api_remote_overview(ctx: click.Context, remote: str | None) -> None:
        """Cross-project overview from remote machine."""
        client = _get_remote(ctx, remote)
        _output(client.overview(), ctx.obj["human"], ctx.obj["compact"])

    @api_group.command("remote-alerts")
    @click.option("--remote", "-r", default=None, help="Remote profile name")
    @click.pass_context
    def api_remote_alerts(ctx: click.Context, remote: str | None) -> None:
        """Alerts from remote machine."""
        client = _get_remote(ctx, remote)
        _output(client.alerts(), ctx.obj["human"], ctx.obj["compact"])
