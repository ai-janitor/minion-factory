"""DB maintenance commands — prune old records, check schema version.

Purpose: CLI commands for database lifecycle management.
Rationale: Backlog #61 — tables grow unbounded without maintenance tools.
Responsibility: Register `minion db prune` and related commands.
Organization: Follows same pattern as other cli/*_cmds.py modules.

Pseudo-logic:
  - register_commands() creates a `db` Click group
  - `prune` subcommand: parse --days, call prune_old_records(), output result
  - `schema-version` subcommand: show current migration version
"""

from __future__ import annotations

import click

from minion.cli.main import _output


def register_commands(cli: click.Group) -> None:
    """Attach the db group and its subcommands to the root CLI."""

    @cli.group("db")
    @click.pass_context
    def db_group(ctx: click.Context) -> None:
        """Database maintenance — prune old records, check schema version."""
        pass

    @db_group.command("prune")
    @click.option("--days", default=30, type=int, help="Delete records older than N days (default: 30)")
    @click.pass_context
    def db_prune(ctx: click.Context, days: int) -> None:
        """Delete old records from messages, transition_log, invocation_log, compaction_log.

        Prevents unbounded DB growth. Default: remove records older than 30 days.
        Also cleans up orphaned broadcast_reads and runs VACUUM to reclaim space.

        Examples:
          minion db prune              # prune records > 30 days old
          minion db prune --days 7     # prune records > 7 days old
          minion db prune --days 90    # prune records > 90 days old
        """
        if days < 1:
            click.echo("Error: --days must be at least 1", err=True)
            raise SystemExit(1)
        from minion.db.prune import prune_old_records
        result = prune_old_records(max_age_days=days)
        _output(result, ctx.obj["human"])

    @db_group.command("schema-version")
    @click.pass_context
    def db_schema_version(ctx: click.Context) -> None:
        """Show current schema migration version."""
        from minion.db.migrations import _get_current_schema_version
        from minion.db.connection import get_db
        conn = get_db()
        try:
            version = _get_current_schema_version(conn)
            _output({"schema_version": version}, ctx.obj["human"])
        finally:
            conn.close()
