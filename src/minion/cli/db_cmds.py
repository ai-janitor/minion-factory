"""DB maintenance commands — prune old records, check schema version, check integrity.

Purpose: CLI commands for database lifecycle management.
Rationale: Backlog #61 — tables grow unbounded without maintenance tools.
           Backlog #239 — FK integrity checking and orphan cleanup.
Responsibility: Register `minion db prune`, `minion db schema-version`,
                and `minion db check-integrity` commands.
Organization: Follows same pattern as other cli/*_cmds.py modules.

Pseudo-logic:
  - register_commands() creates a `db` Click group
  - `prune` subcommand: parse --days, call prune_old_records(), output result
  - `schema-version` subcommand: show current migration version
  - `check-integrity` subcommand: check FK integrity, optionally fix orphans
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
    @click.option("--days", "-d", default=30, type=int, help="Delete records older than N days (default: 30)")
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

    @db_group.command("check-integrity")
    @click.option("--fix", is_flag=True, default=False, help="Fix orphan references (NULL or delete)")
    @click.pass_context
    def db_check_integrity(ctx: click.Context, fix: bool) -> None:
        """Check FK integrity across all tables. Report orphan rows.

        Without --fix: reports violations only (dry run).
        With --fix: NULLs or deletes orphan references depending on the relationship.

        Examples:
          minion db check-integrity          # report only
          minion db check-integrity --fix    # fix orphans
        """
        from minion.db.connection import get_db
        from minion.db.integrity_check_foreign_keys_and_orphans import (
            check_all_fk_integrity,
            clean_orphans,
            report,
        )
        conn = get_db()
        try:
            if fix:
                # First show what we'll fix, then fix it
                result = clean_orphans(conn, dry_run=False)
                _output(result, ctx.obj["human"])
            else:
                # Report mode — check and display human-readable report
                if ctx.obj["human"]:
                    click.echo(report(conn))
                else:
                    _output(check_all_fk_integrity(conn), ctx.obj["human"])
        finally:
            conn.close()
