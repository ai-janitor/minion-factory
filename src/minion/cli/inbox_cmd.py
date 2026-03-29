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
    @click.option("--last", "-n", "last_n", default=None, type=int, help="Show last N messages globally (includes read)")
    @click.option("--include-read", is_flag=True, help="Include already-read messages")
    @click.pass_context
    def aggregate_inbox(ctx: click.Context, agent: str, channel: str, server: str,
                        last_n: int | None, include_read: bool) -> None:
        """Aggregate inbox — all sources, clearly tagged.

        \b
        Checks both local project inbox and all joined coordinator inboxes.
        Each message is tagged with a source label like:
          local/llama-metal     — from local project comms
          trashcan/llama-metal  — from the trashcan coordinator

        \b
        --last N: show most recent N messages globally across all sources.
        --include-read: include already-read messages.

        \b
        Examples:
          minion inbox --agent trashcan-lead
          minion inbox -a codex-lead --last 5
          minion inbox -a me --include-read --channel llama-metal
        """
        from minion.team import aggregate_inbox as _aggregate
        result = _aggregate(agent=agent, channel=channel, server_url=server,
                            last_n=last_n, include_read=include_read)
        _output(result, ctx.obj["human"], ctx.obj["compact"])
