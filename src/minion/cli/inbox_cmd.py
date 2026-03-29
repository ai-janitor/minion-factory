"""Top-level aggregate inbox command — minion inbox.

Aggregates messages from all sources: local project DB + all joined
coordinators. Each message tagged with source_label (e.g., local/llama-metal,
trashcan/llama-metal).

Purpose: Aggregate inbox across all message sources.
Rationale: Users need one command to see all messages without knowing
  which transport layer each came from.
Responsibility: CLI wrapper for team.aggregate_inbox. NOT responsible for
  transport details."""

from __future__ import annotations

import click

from minion.cli.main import _output


def register_commands(cli: click.Group) -> None:
    """Attach the top-level inbox command to the root CLI."""

    @cli.command("inbox")
    @click.option("--agent", "-a", required=True, help="Agent name to check inbox for")
    @click.option("--channel", "-ch", default="", help="Filter by channel name")
    @click.option("--server", "-s", default="", help="Filter by server alias or URL")
    @click.pass_context
    def aggregate_inbox(ctx: click.Context, agent: str, channel: str, server: str) -> None:
        """Aggregate inbox — all sources, clearly tagged.

        \b
        Checks both local project inbox and all joined coordinator inboxes.
        Each message is tagged with a source label like:
          local/llama-metal     — from local project comms
          trashcan/llama-metal  — from the trashcan coordinator

        \b
        Use --server or --channel to narrow results.

        \b
        Scoped alternatives:
          minion team inbox -a NAME       — coordinator/team messages only
          minion comms check-inbox -a NAME — local project messages only

        \b
        Examples:
          minion inbox --agent trashcan-lead
          minion inbox -a codex-lead --channel llama-metal
          minion inbox -a me --server trashcan
        """
        from minion.team import aggregate_inbox as _aggregate
        result = _aggregate(agent=agent, channel=channel, server_url=server)
        _output(result, ctx.obj["human"], ctx.obj["compact"])
