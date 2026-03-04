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
        """API server daemon — start/stop/status/restart."""
        pass

    @api_group.command("start")
    @click.option("--port", default=8377, type=int, help="TCP port (default: 8377)")
    @click.pass_context
    def api_start(ctx: click.Context, port: int) -> None:
        """Start the API server as a background daemon."""
        from minion.api.daemon import start
        result = start(port=port)
        _output(result, ctx.obj["human"], ctx.obj["compact"])

    @api_group.command("stop")
    @click.pass_context
    def api_stop(ctx: click.Context) -> None:
        """Stop the API server daemon."""
        from minion.api.daemon import stop
        result = stop()
        _output(result, ctx.obj["human"], ctx.obj["compact"])

    @api_group.command("status")
    @click.pass_context
    def api_status(ctx: click.Context) -> None:
        """Check API server daemon status."""
        from minion.api.daemon import status
        result = status()
        _output(result, ctx.obj["human"], ctx.obj["compact"])

    @api_group.command("restart")
    @click.option("--port", default=None, type=int, help="Override port on restart")
    @click.pass_context
    def api_restart(ctx: click.Context, port: int | None) -> None:
        """Restart the API server daemon."""
        from minion.api.daemon import restart
        result = restart(port=port)
        _output(result, ctx.obj["human"], ctx.obj["compact"])
