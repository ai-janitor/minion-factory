"""Backlog group — add, list, show, update, promote, kill, defer, reindex.

Capture and triage ideas, bugs, requests, smells, and tech debt.
"""

from __future__ import annotations

import json
import sys

import click


def _echo_error(data: dict[str, object], exit_code: int = 1) -> None:
    """Print error JSON to stderr and exit with given code."""
    click.echo(json.dumps(data, indent=2), err=True)
    sys.exit(exit_code)


def register_commands(cli: click.Group) -> None:
    """Attach the backlog group and its subcommands to the root CLI."""

    @cli.group("backlog")
    @click.pass_context
    def backlog_group(ctx: click.Context) -> None:
        """Capture and triage ideas, bugs, requests, smells, and tech debt."""
        pass

    @backlog_group.command("add")
    @click.option("--type", "-t", "item_type", required=True, type=click.Choice(["idea", "bug", "request", "smell", "debt"]))
    @click.option("--title", "-T", required=True, help="Short descriptive title")
    @click.option("--source", "-s", default="human", help="Who captured this (default: human)")
    @click.option("--description", "-d", default="", help="Longer description of the item")
    @click.option("--priority", "-p", default="unset", type=click.Choice(["unset", "low", "medium", "high", "critical"]))
    @click.option("--flow-hint", "-f", default="", help="DAG flow type hint (e.g. implementation, feature, chore, build)")
    @click.pass_context
    def backlog_add(ctx: click.Context, item_type: str, title: str, source: str, description: str, priority: str, flow_hint: str) -> None:
        """Add a new item to the backlog."""
        from minion.backlog import add as _add
        try:
            result = _add(item_type, title, source, description, priority, flow_hint=flow_hint)
        except ValueError as e:
            _echo_error({"error": str(e)})
        click.echo(json.dumps(result, indent=2))
        if not flow_hint:
            click.echo(
                "\n\u26a0 No --flow-hint set. Run `minion backlog update <path> --flow-hint <dag>` "
                "when you have clarity.\n  Available DAGs: minion flow list --verbose",
                err=True,
            )

    @backlog_group.command("list")
    @click.option("--type", "-t", "item_type", default=None, type=click.Choice(["idea", "bug", "request", "smell", "debt"]))
    @click.option("--priority", "-p", default=None, type=click.Choice(["unset", "low", "medium", "high", "critical"]))
    @click.option("--status", "-s", default="open", type=click.Choice(["open", "promoted", "killed", "deferred", "closed"]))
    @click.pass_context
    def backlog_list(ctx: click.Context, item_type: str | None, priority: str | None, status: str | None) -> None:
        """List backlog items with optional filters."""
        from minion.backlog import list_items as _list_items
        try:
            result = _list_items(item_type, priority, status)
        except ValueError as e:
            _echo_error({"error": str(e)})
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
    @click.option("--id", "-i", "item_id", type=int, default=None, help="Look up by backlog ID")
    @click.pass_context
    def backlog_show(ctx: click.Context, path: str | None, item_id: int | None) -> None:
        """Show a single backlog item by file path or --id."""
        from minion.backlog import get_item as _get_item
        if not path and item_id is None:
            _echo_error({"error": "Provide PATH or --id"}, exit_code=2)
        try:
            if item_id is not None:
                result = _get_item(item_id=item_id)
            else:
                result = _get_item(file_path=path)
        except ValueError as e:
            _echo_error({"error": str(e)})
        if result is None:
            _echo_error({"error": "Backlog item not found."})
        click.echo(json.dumps(result, indent=2))

    @backlog_group.command("update")
    @click.argument("path", required=False, default=None)
    @click.option("--id", "-i", "item_id", type=int, default=None, help="Look up by backlog ID (alternative to path)")
    @click.option("--priority", "-p", default=None, type=click.Choice(["unset", "low", "medium", "high", "critical"]))
    @click.option("--status", "-s", default=None, type=click.Choice(["open", "promoted", "killed", "deferred", "closed"]))
    @click.option("--flow-hint", "-f", default=None, help="DAG flow type hint (e.g. implementation, feature, chore, build)")
    @click.pass_context
    def backlog_update(ctx: click.Context, path: str | None, item_id: int | None, priority: str | None, status: str | None, flow_hint: str | None) -> None:
        """Update priority and/or status of a backlog item by path or --id."""
        if not path and item_id is None:
            _echo_error({"error": "Provide PATH or --id"}, exit_code=2)
        from minion.backlog import update_item as _update_item
        try:
            result = _update_item(path, priority, status, flow_hint=flow_hint, item_id=item_id)
        except ValueError as e:
            _echo_error({"error": str(e)})
        click.echo(json.dumps(result, indent=2))

    @backlog_group.command("promote")
    @click.argument("path", required=False, default=None)
    @click.option("--agent", "-a", required=True, help="Agent performing the promotion (must be lead class)")
    @click.option("--id", "-i", "item_id", default=None, type=int, help="Backlog item ID (alternative to path)")
    @click.option("--ids", "item_ids", default=None,
                  help="Comma-separated backlog IDs for batch promotion (e.g. --ids 275,276,277). "
                       "Each item promoted independently with its own requirement. Cannot combine with PATH, --id, --count, or --slugs.")
    @click.option("--origin", "-o", default=None, type=click.Choice(["bug", "feature"]), help="Requirement origin override")
    @click.option("--slug", "-s", default=None, help="Override the auto-derived requirement slug (single promote)")
    @click.option("--flow", "-f", default="requirement", type=click.Choice(["requirement", "requirement-lite"]),
                  help="Lifecycle flow: 'requirement' (full 9-stage, default) or 'requirement-lite' (4-stage shortcut)")
    @click.option("--count", "-n", default=1, type=int,
                  help="Number of requirements to create (default 1). A complex backlog item may decompose into N independent requirements.")
    @click.option("--slugs", default=None,
                  help="Comma-separated list of N slug names. MANDATORY when --count > 1. Example: --slugs 'auth-api,auth-ui,auth-tests'")
    @click.pass_context
    def backlog_promote(ctx: click.Context, path: str | None, agent: str, item_id: int | None, item_ids: str | None, origin: str | None, slug: str | None, flow: str, count: int, slugs: str | None) -> None:
        """Promote backlog item(s) into the requirement pipeline.

        Creates one or more requirements from a single backlog item. By default,
        creates exactly 1 requirement (existing behavior). Use --count N with
        --slugs to decompose a complex backlog item into N independent requirements.

        Use --ids for batch promotion of multiple independent backlog items.
        Each item is promoted independently with its own requirement.
        Returns a JSON object with status, count, results array, and optional errors array.

        A backlog item that has already been promoted can be re-promoted with --count
        to add additional requirements (the 'already promoted' guard is lifted for
        multi-promote).

        Requires lead class.
        """
        # --- Batch mode: --ids promotes multiple independent backlog items ---
        if item_ids:
            if path or item_id:
                _echo_error({"error": "--ids cannot be combined with PATH or --id. Use --ids alone for batch."}, exit_code=2)
            if count > 1 or slugs:
                _echo_error({"error": "--ids cannot be combined with --count/--slugs. Each batch item creates exactly 1 requirement."}, exit_code=2)

            id_list = [s.strip() for s in item_ids.split(",") if s.strip()]
            if not id_list:
                _echo_error({"error": "--ids requires at least one ID."}, exit_code=2)

            # Validate all IDs are integers before starting any promotions
            parsed_ids: list[int] = []
            for raw_id in id_list:
                try:
                    parsed_ids.append(int(raw_id))
                except ValueError:
                    _echo_error({"error": f"Invalid backlog ID in --ids: '{raw_id}'. All values must be integers."}, exit_code=2)

            from minion.backlog import get_item as _get_item
            from minion.backlog import promote as _promote

            results: list[dict] = []
            errors: list[dict] = []
            for bid in parsed_ids:
                try:
                    item = _get_item(item_id=bid)
                    if item is None:
                        errors.append({"id": bid, "error": f"Backlog item #{bid} not found."})
                        continue
                    if "error" in item:
                        errors.append({"id": bid, "error": item["error"]})
                        continue
                    result = _promote(item["file_path"], origin, slug=slug, flow=flow, agent_name=agent)
                    result["backlog_id"] = bid
                    results.append(result)
                except (ValueError, RuntimeError) as e:
                    errors.append({"id": bid, "error": str(e)})

            batch_output: dict = {"status": "batch_promoted", "count": len(results), "results": results}
            if errors:
                batch_output["errors"] = errors
            click.echo(json.dumps(batch_output, indent=2))
            return

        # --- Single mode: existing behavior ---
        if not path and not item_id:
            _echo_error({"error": "Provide a path argument, --id <N>, or --ids <N,N,...>."}, exit_code=2)
        # Validate --count / --slugs consistency
        if count < 1:
            _echo_error({"error": "--count must be >= 1."}, exit_code=2)
        if count > 1 and not slugs:
            _echo_error({"error": "--slugs is required when --count > 1. Provide comma-separated slug names."}, exit_code=2)
        if slugs and count == 1:
            _echo_error({"error": "--slugs requires --count > 1. For a single promote, use --slug instead."}, exit_code=2)
        slug_list: list[str] | None = None
        if slugs:
            slug_list = [s.strip() for s in slugs.split(",") if s.strip()]
            if len(slug_list) != count:
                _echo_error({"error": f"--slugs has {len(slug_list)} items but --count is {count}. They must match."}, exit_code=2)
        if item_id and not path:
            from minion.backlog import get_item as _get_item
            item = _get_item(item_id=item_id)
            if "error" in item:
                _echo_error(item)
            path = item["file_path"]
        from minion.backlog import promote as _promote
        try:
            result = _promote(path, origin, slug=slug, flow=flow, agent_name=agent,
                              count=count, slugs=slug_list)
        except ValueError as e:
            _echo_error({"error": str(e)})
        click.echo(json.dumps(result, indent=2))

    @backlog_group.command("kill")
    @click.argument("path")
    @click.option("--reason", "-r", required=True, help="Why this item is being killed")
    @click.pass_context
    def backlog_kill(ctx: click.Context, path: str, reason: str) -> None:
        """Mark a backlog item as killed."""
        from minion.backlog import kill as _kill
        try:
            result = _kill(path, reason)
        except ValueError as e:
            _echo_error({"error": str(e)})
        click.echo(json.dumps(result, indent=2))

    @backlog_group.command("defer")
    @click.argument("path")
    @click.option("--until", "-u", required=True, help="Date or milestone to defer until")
    @click.pass_context
    def backlog_defer(ctx: click.Context, path: str, until: str) -> None:
        """Defer a backlog item until a later date or milestone."""
        from minion.backlog import defer as _defer
        try:
            result = _defer(path, until)
        except ValueError as e:
            _echo_error({"error": str(e)})
        click.echo(json.dumps(result, indent=2))

    @backlog_group.command("lineage")
    @click.argument("path", required=False, default=None)
    @click.option("--id", "-i", "item_id", type=int, default=None, help="Look up by backlog ID")
    @click.pass_context
    def backlog_lineage(ctx: click.Context, path: str | None, item_id: int | None) -> None:
        """Full audit trail from backlog item to task closure."""
        from minion.backlog import lineage as _lineage
        if not path and item_id is None:
            _echo_error({"error": "Provide PATH or --id"}, exit_code=2)
        try:
            result = _lineage(file_path=path, item_id=item_id)
        except ValueError as e:
            _echo_error({"error": str(e)})
        click.echo(json.dumps(result, indent=2))

    @backlog_group.command("reindex")
    @click.pass_context
    def backlog_reindex(ctx: click.Context) -> None:
        """Rebuild the backlog DB index by scanning the filesystem."""
        from minion.backlog import reindex as _reindex
        try:
            result = _reindex()
        except ValueError as e:
            _echo_error({"error": str(e)})
        click.echo(json.dumps(result, indent=2))

    @backlog_group.command("fast-track")
    @click.option("--agent", "-a", required=True, help="Agent performing the fast-track (must be lead class)")
    @click.option("--type", "-t", "item_type", required=True, type=click.Choice(["idea", "bug", "request", "smell", "debt"]))
    @click.option("--title", "-T", required=True, help="Short descriptive title")
    @click.option("--description", "-d", required=True, help="Longer description of the item")
    @click.option("--priority", "-p", default="medium", type=click.Choice(["unset", "low", "medium", "high", "critical"]))
    @click.option("--task-type", "-k", "task_type", default="feature", type=click.Choice(["bugfix", "build", "chore", "feature", "hotfix", "implementation", "investigation", "requirement", "research"]), help="DAG flow type for the created task")
    @click.option("--flow-hint", "-f", default="", help="Flow hint for the backlog item (defaults to task-type if omitted)")
    @click.option("--req-flow", default="requirement-lite", type=click.Choice(["requirement", "requirement-lite"]), help="Requirement lifecycle flow (default: requirement-lite)")
    @click.option("--slug", "-s", default=None, help="Override the auto-derived requirement slug")
    @click.pass_context
    def backlog_fast_track(ctx: click.Context, agent: str, item_type: str, title: str,
                           description: str, priority: str, task_type: str, flow_hint: str,
                           req_flow: str, slug: str | None) -> None:
        """Composite add+promote+define in one shot. Requires lead class.

        Creates a backlog item, promotes it to a requirement, and defines a task
        — all in one command. Eliminates the 3-step chain that causes flag-mismatch errors.

        Returns a combined JSON with backlog_id, requirement_id, requirement_path, task_id.
        """
        from minion.backlog import fast_track as _fast_track
        try:
            result = _fast_track(
                agent_name=agent,
                item_type=item_type,
                title=title,
                description=description,
                priority=priority,
                task_type=task_type,
                flow_hint=flow_hint,
                req_flow=req_flow,
                slug=slug,
            )
        except Exception as e:
            _echo_error({"error": str(e)})
        if "warnings" in result:
            for w in result["warnings"]:
                click.echo(f"\n⚠ {w}", err=True)
        click.echo(json.dumps(result, indent=2))
