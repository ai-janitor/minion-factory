"""Network group — serve, gen-cert, status, who, outbox.
Cross-machine agent comms via API GLOBAL tier.

Purpose: Network group — serve, gen-cert, status, who, outbox.
Rationale: Extracted into own module for single-responsibility CLI command grouping.
Responsibility: Network group — serve, gen-cert, status, who, outbox. NOT responsible for unrelated concerns.
Organization: Click command group with subcommands."""

from __future__ import annotations

import sys

import click

from minion.cli.main import _output


def register_commands(cli: click.Group) -> None:
    """Attach the network group and its subcommands to the root CLI."""

    @cli.group("network")
    @click.pass_context
    def network_group(ctx: click.Context) -> None:
        """Cross-machine agent comms — API GLOBAL tier."""
        pass

    @network_group.command("serve")
    @click.option("--port", default=8377, type=int, help="TCP port (default: 8377)")
    @click.option("--db-path", default="", help="SQLite DB path (default: ~/.minion/network.db)")
    @click.option("--token", default="", help="Cluster auth token (or set MINION_CLUSTER_TOKEN)")
    @click.option("--no-auth", is_flag=True, default=False, help="Allow starting without auth token (DEVELOPMENT ONLY)")
    @click.pass_context
    def network_serve(ctx: click.Context, port: int, db_path: str, token: str, no_auth: bool) -> None:
        """Start the API GLOBAL coordinator server."""
        from minion.network.server import serve as _serve
        _serve(port=port, db_path=db_path, token=token, allow_no_auth=no_auth)

    @network_group.command("gen-cert")
    @click.pass_context
    def network_gen_cert(ctx: click.Context) -> None:
        """Generate a self-signed TLS certificate for the network server."""
        from minion.network.server import gen_cert
        result = gen_cert()
        _output({"status": "created", **result}, ctx.obj["human"], ctx.obj["compact"])

    @network_group.command("status")
    @click.pass_context
    def network_status(ctx: click.Context) -> None:
        """Check network server health and list remote agents."""
        from minion.network.client import get_client
        net = get_client()
        if not net.configured:
            _output({"error": "MINION_NETWORK_URL not set. Network tier disabled."}, ctx.obj["human"], ctx.obj["compact"])
            sys.exit(1)
        health = net.health()
        agents = net.who()
        _output({"health": health, "agents": agents.get("agents", [])}, ctx.obj["human"], ctx.obj["compact"])

    @network_group.command("who")
    @click.pass_context
    def network_who(ctx: click.Context) -> None:
        """List agents registered on the network tier."""
        from minion.network.client import get_client
        net = get_client()
        if not net.configured:
            _output({"error": "MINION_NETWORK_URL not set."}, ctx.obj["human"], ctx.obj["compact"])
            sys.exit(1)
        _output(net.who(), ctx.obj["human"], ctx.obj["compact"])

    @network_group.command("outbox")
    @click.pass_context
    def network_outbox(ctx: click.Context) -> None:
        """Show queued messages waiting for network delivery."""
        from minion.network.outbox import outbox_count
        _output({"queued_messages": outbox_count()}, ctx.obj["human"], ctx.obj["compact"])

    @network_group.command("projects")
    @click.pass_context
    def network_projects(ctx: click.Context) -> None:
        """List all projects registered on the network server."""
        from minion.network.client import get_client
        net = get_client()
        if not net.configured:
            _output({"error": "MINION_NETWORK_URL not set."}, ctx.obj["human"], ctx.obj["compact"])
            sys.exit(1)
        _output(net.list_projects(), ctx.obj["human"], ctx.obj["compact"])

    @network_group.command("overview")
    @click.pass_context
    def network_overview(ctx: click.Context) -> None:
        """Cross-project overview — agents, tasks, alerts aggregated."""
        from minion.network.client import get_client
        net = get_client()
        if not net.configured:
            _output({"error": "MINION_NETWORK_URL not set."}, ctx.obj["human"], ctx.obj["compact"])
            sys.exit(1)
        _output(net.overview(), ctx.obj["human"], ctx.obj["compact"])

    @network_group.command("alerts")
    @click.pass_context
    def network_alerts(ctx: click.Context) -> None:
        """Cross-project alert feed — HP warnings, stale agents, blocked tasks."""
        from minion.network.client import get_client
        net = get_client()
        if not net.configured:
            _output({"error": "MINION_NETWORK_URL not set."}, ctx.obj["human"], ctx.obj["compact"])
            sys.exit(1)
        _output(net.alerts(), ctx.obj["human"], ctx.obj["compact"])

    @network_group.command("project-agents")
    @click.option("--project", required=True, help="Project name")
    @click.pass_context
    def network_project_agents(ctx: click.Context, project: str) -> None:
        """List agents in a specific project via the network server."""
        from minion.network.client import get_client
        net = get_client()
        if not net.configured:
            _output({"error": "MINION_NETWORK_URL not set."}, ctx.obj["human"], ctx.obj["compact"])
            sys.exit(1)
        _output(net.project_agents(project), ctx.obj["human"], ctx.obj["compact"])
