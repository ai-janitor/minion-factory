"""Backlog group — add, list, show, update, promote, kill, defer, reindex.

Capture and triage ideas, bugs, requests, smells, and tech debt.
"""

from __future__ import annotations

import json
import sys

import click


def register_commands(cli: click.Group) -> None:
    """Attach the backlog group and its subcommands to the root CLI."""

    @cli.group("backlog")
    @click.pass_context
    def backlog_group(ctx: click.Context) -> None:
        """Capture and triage ideas, bugs, requests, smells, and tech debt."""
        pass

    @backlog_group.command("add")
    @click.option("--type", "item_type", required=True, type=click.Choice(["idea", "bug", "request", "smell", "debt"]))
    @click.option("--title", required=True, help="Short descriptive title")
    @click.option("--source", default="human", help="Who captured this (default: human)")
    @click.option("--description", default="", help="Longer description of the item")
    @click.option("--priority", default="unset", type=click.Choice(["unset", "low", "medium", "high", "critical"]))
    @click.option("--flow-hint", default="", help="DAG flow type hint (e.g. implementation, feature, chore, build)")
    @click.pass_context
    def backlog_add(ctx: click.Context, item_type: str, title: str, source: str, description: str, priority: str, flow_hint: str) -> None:
        """Add a new item to the backlog."""
        from minion.backlog import add as _add
        try:
            result = _add(item_type, title, source, description, priority, flow_hint=flow_hint)
        except ValueError as e:
            click.echo(json.dumps({"error": str(e)}, indent=2))
            sys.exit(1)
        click.echo(json.dumps(result, indent=2))
        if not flow_hint:
            click.echo(
                "\n\u26a0 No --flow-hint set. Run `minion backlog update <path> --flow-hint <dag>` "
                "when you have clarity.\n  Available DAGs: minion flow list --verbose",
                err=True,
            )

    @backlog_group.command("list")
    @click.option("--type", "item_type", default=None, type=click.Choice(["idea", "bug", "request", "smell", "debt"]))
    @click.option("--priority", default=None, type=click.Choice(["unset", "low", "medium", "high", "critical"]))
    @click.option("--status", default="open", type=click.Choice(["open", "promoted", "killed", "deferred"]))
    @click.pass_context
    def backlog_list(ctx: click.Context, item_type: str | None, priority: str | None, status: str | None) -> None:
        """List backlog items with optional filters."""
        from minion.backlog import list_items as _list_items
        try:
            result = _list_items(item_type, priority, status)
        except ValueError as e:
            click.echo(json.dumps({"error": str(e)}, indent=2))
            sys.exit(1)
        click.echo(json.dumps(result, indent=2))
        missing = [r for r in result if not r.get("flow_hint")]
        if missing:
            click.echo(
                f"\n\u26a0 {len(missing)} item(s) missing --flow-hint: "
                f"{', '.join('#' + str(r['id']) for r in missing[:10])}"
                f"{'...' if len(missing) > 10 else ''}"
                f"\n  Set with: minion backlog update <path> --flow-hint <dag>",
                err=True,
            )

    @backlog_group.command("show")
    @click.argument("path", required=False, default=None)
    @click.option("--id", "item_id", type=int, default=None, help="Look up by backlog ID")
    @click.pass_context
    def backlog_show(ctx: click.Context, path: str | None, item_id: int | None) -> None:
        """Show a single backlog item by file path or --id."""
        from minion.backlog import get_item as _get_item
        if not path and item_id is None:
            click.echo(json.dumps({"error": "Provide PATH or --id"}, indent=2))
            sys.exit(1)
        try:
            if item_id is not None:
                result = _get_item(item_id=item_id)
            else:
                result = _get_item(file_path=path)
        except ValueError as e:
            click.echo(json.dumps({"error": str(e)}, indent=2))
            sys.exit(1)
        if result is None:
            click.echo(json.dumps({"error": "Backlog item not found."}, indent=2))
            sys.exit(1)
        click.echo(json.dumps(result, indent=2))

    @backlog_group.command("update")
    @click.argument("path")
    @click.option("--priority", default=None, type=click.Choice(["unset", "low", "medium", "high", "critical"]))
    @click.option("--status", default=None, type=click.Choice(["open", "promoted", "killed", "deferred"]))
    @click.option("--flow-hint", default=None, help="DAG flow type hint (e.g. implementation, feature, chore, build)")
    @click.pass_context
    def backlog_update(ctx: click.Context, path: str, priority: str | None, status: str | None, flow_hint: str | None) -> None:
        """Update priority and/or status of a backlog item."""
        from minion.backlog import update_item as _update_item
        try:
            result = _update_item(path, priority, status, flow_hint=flow_hint)
        except ValueError as e:
            click.echo(json.dumps({"error": str(e)}, indent=2))
            sys.exit(1)
        click.echo(json.dumps(result, indent=2))

    @backlog_group.command("promote")
    @click.argument("path", required=False, default=None)
    @click.option("--id", "item_id", default=None, type=int, help="Backlog item ID (alternative to path)")
    @click.option("--origin", default=None, type=click.Choice(["bug", "feature"]), help="Requirement origin override")
    @click.option("--slug", default=None, help="Override the auto-derived requirement slug")
    @click.option("--flow", default="requirement", type=click.Choice(["requirement", "requirement-lite"]),
                  help="Lifecycle flow: 'requirement' (full 9-stage, default) or 'requirement-lite' (4-stage shortcut)")
    @click.pass_context
    def backlog_promote(ctx: click.Context, path: str | None, item_id: int | None, origin: str | None, slug: str | None, flow: str) -> None:
        """Promote a backlog item into the requirement pipeline."""
        if not path and not item_id:
            click.echo(json.dumps({"error": "Provide a path argument or --id <N>."}, indent=2))
            raise SystemExit(1)
        if item_id and not path:
            from minion.backlog import get_item as _get_item
            item = _get_item(item_id=item_id)
            if "error" in item:
                click.echo(json.dumps(item, indent=2))
                raise SystemExit(1)
            path = item["file_path"]
        from minion.backlog import promote as _promote
        try:
            result = _promote(path, origin, slug=slug, flow=flow)
        except ValueError as e:
            click.echo(json.dumps({"error": str(e)}, indent=2))
            sys.exit(1)
        click.echo(json.dumps(result, indent=2))

    @backlog_group.command("kill")
    @click.argument("path")
    @click.option("--reason", required=True, help="Why this item is being killed")
    @click.pass_context
    def backlog_kill(ctx: click.Context, path: str, reason: str) -> None:
        """Mark a backlog item as killed."""
        from minion.backlog import kill as _kill
        try:
            result = _kill(path, reason)
        except ValueError as e:
            click.echo(json.dumps({"error": str(e)}, indent=2))
            sys.exit(1)
        click.echo(json.dumps(result, indent=2))

    @backlog_group.command("defer")
    @click.argument("path")
    @click.option("--until", required=True, help="Date or milestone to defer until")
    @click.pass_context
    def backlog_defer(ctx: click.Context, path: str, until: str) -> None:
        """Defer a backlog item until a later date or milestone."""
        from minion.backlog import defer as _defer
        try:
            result = _defer(path, until)
        except ValueError as e:
            click.echo(json.dumps({"error": str(e)}, indent=2))
            sys.exit(1)
        click.echo(json.dumps(result, indent=2))

    @backlog_group.command("reindex")
    @click.pass_context
    def backlog_reindex(ctx: click.Context) -> None:
        """Rebuild the backlog DB index by scanning the filesystem."""
        from minion.backlog import reindex as _reindex
        try:
            result = _reindex()
        except ValueError as e:
            click.echo(json.dumps({"error": str(e)}, indent=2))
            sys.exit(1)
        click.echo(json.dumps(result, indent=2))
