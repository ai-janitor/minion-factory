"""Req group — register, reindex, list, tree, status, update, link, unlinked, orphans, create, decompose, itemize, findings, report.
Track requirements through the decomposition pipeline: seed to completed.

Purpose: Req group — register, reindex, list, tree, status, update, link, unlinked, orphans, create, decompose, itemize, findings, report.
Rationale: Extracted into own module for single-responsibility CLI command grouping.
Responsibility: Req group — register, reindex, list, tree, status, update, link, unlinked, orphans, create, decompose, itemize, findings, report. NOT responsible for unrelated concerns.
Organization: Click command group with subcommands."""

from __future__ import annotations

import click

from minion.cli.main import _agent_option, _output


def register_commands(cli: click.Group) -> None:
    """Attach the req group and its subcommands to the root CLI."""

    @cli.group("req")
    @click.pass_context
    def req_group(ctx: click.Context) -> None:
        """Track requirements through the decomposition pipeline — seed to completed."""
        pass

    @req_group.command("register")
    @click.option("--path", "-p", required=True, help="Path relative to .work/requirements/")
    @click.option("--by", "-b", "created_by", default="human", help="Who is registering (agent name or 'human')")
    @click.pass_context
    def req_register(ctx: click.Context, path: str, created_by: str) -> None:
        """Register a requirement folder in the index."""
        from minion.requirements import register as _register
        _output(_register(path, created_by), ctx.obj["human"], ctx.obj["compact"])

    @req_group.command("reindex")
    @click.option("--work-dir", "-w", default="", help="Path to .work/ directory (default: cwd/.work or -C project-dir/.work)")
    @click.pass_context
    def req_reindex(ctx: click.Context, work_dir: str) -> None:
        """Rebuild the requirements index by scanning the filesystem."""
        from minion.defaults import resolve_work_dir
        from minion.requirements import reindex as _reindex
        if work_dir:
            wd = work_dir
        else:
            project_dir = ctx.obj.get("project_dir")
            wd = str(resolve_work_dir(project_dir))
        _output(_reindex(wd), ctx.obj["human"], ctx.obj["compact"])

    @req_group.command("list")
    @click.option("--stage", "-s", default=None, type=click.Choice(["seed", "itemizing", "itemized", "investigating", "findings_ready", "decomposing", "tasked", "in_progress", "completed"]))
    @click.option("--origin", "-o", default="", help="Filter by origin (feature, bug, ...)")
    @click.pass_context
    def req_list(ctx: click.Context, stage: str, origin: str) -> None:
        """List all requirements with optional filters."""
        from minion.requirements import list_requirements as _list
        _output(_list(stage, origin), ctx.obj["human"], ctx.obj["compact"])

    @req_group.command("tree")
    @click.argument("path")
    @click.pass_context
    def req_tree(ctx: click.Context, path: str) -> None:
        """Show the decomposition tree rooted at PATH (accepts ID or path)."""
        from minion.requirements import resolve_path, get_tree as _tree
        path = resolve_path(path)
        _output(_tree(path), ctx.obj["human"], ctx.obj["compact"])

    @req_group.command("status")
    @click.argument("path")
    @click.pass_context
    def req_status(ctx: click.Context, path: str) -> None:
        """Show a requirement, its linked tasks, and completion percentage (accepts ID or path)."""
        from minion.requirements import resolve_path, get_status as _status
        path = resolve_path(path)
        _output(_status(path), ctx.obj["human"], ctx.obj["compact"])

    @req_group.command("update")
    @click.option("--path", "-p", required=True, help="Requirement path relative to .work/requirements/")
    @click.option("--stage", "-s", required=True, type=click.Choice(["seed", "itemizing", "itemized", "investigating", "findings_ready", "decomposing", "tasked", "in_progress", "completed"]))
    @click.option("--skip", "-S", "skip_stages", is_flag=True, default=False, help="Walk through all intermediate stages to reach target (lead only).")
    @_agent_option(default="", help="Caller agent name; must be 'lead' to use --skip.")
    @click.pass_context
    def req_update(ctx: click.Context, path: str, stage: str, skip_stages: bool, agent: str) -> None:
        """Advance a requirement's stage (accepts ID or path). Use --skip --agent lead to jump multiple stages at once."""
        from minion.requirements import resolve_path, update_stage as _update
        path = resolve_path(path)
        _output(_update(path, stage, skip=skip_stages, agent=agent), ctx.obj["human"], ctx.obj["compact"])

    @req_group.command("link")
    @click.option("--task", "-t", "task_id", required=True, type=int, help="Task ID to link")
    @click.option("--path", "-p", required=True, help="Requirement path relative to .work/requirements/")
    @click.pass_context
    def req_link(ctx: click.Context, task_id: int, path: str) -> None:
        """Link a task to its source requirement (accepts ID or path)."""
        from minion.requirements import resolve_path, link_task as _link
        path = resolve_path(path)
        _output(_link(task_id, path), ctx.obj["human"], ctx.obj["compact"])

    @req_group.command("unlinked")
    @click.pass_context
    def req_unlinked(ctx: click.Context) -> None:
        """List tasks with no requirement_path (orphan tasks)."""
        from minion.requirements import get_unlinked_tasks as _unlinked
        _output(_unlinked(), ctx.obj["human"], ctx.obj["compact"])

    @req_group.command("orphans")
    @click.pass_context
    def req_orphans(ctx: click.Context) -> None:
        """List leaf requirements with no linked tasks (work never started)."""
        from minion.requirements import get_orphans as _orphans
        _output(_orphans(), ctx.obj["human"], ctx.obj["compact"])

    @req_group.command("create")
    @click.option("--path", "-p", required=True, help="Path relative to .work/requirements/")
    @click.option("--title", "-t", required=True, help="Requirement title")
    @click.option("--description", "-d", default="", help="Requirement description")
    @click.option("--by", "-b", "created_by", default="human")
    @click.pass_context
    def req_create(ctx: click.Context, path: str, title: str, description: str, created_by: str) -> None:
        """Create a requirement folder with README and register it."""
        from minion.requirements import create as _create
        _output(_create(path, title, description, created_by), ctx.obj["human"], ctx.obj["compact"])

    @req_group.command("decompose")
    @click.option("--path", "-p", required=True, help="Parent requirement path")
    @click.option("--spec", "-s", default=None, help="YAML spec file for children. Use '-' to read from stdin.")
    @click.option(
        "--inline", "-i", default=None,
        help=(
            "Inline YAML string (alternative to --spec file). "
            "Required shape: 'children:' with a list of {slug, title, description, task_type}. "
            "Example: 'children:\\n  - slug: add-logout\\n    title: \"Add logout button\"\\n"
            "    description: \"Header logout that clears session\"\\n    task_type: feature'"
        ),
    )
    @click.option("--by", "-b", "agent_name", default="lead")
    @click.pass_context
    def req_decompose(ctx: click.Context, path: str, spec: str | None, inline: str | None, agent_name: str) -> None:
        """Decompose a requirement into children from a spec file or inline YAML.

        Accepts a spec in three ways:
          --spec <file>       YAML file on disk
          --spec -            Read YAML from stdin
          --inline '<yaml>'   Pass YAML directly as a string argument

        Spec shape (YAML):

            children:
              - slug: add-logout-button
                title: "Add Logout button to header"
                description: "Header logout that clears session and redirects."
                task_type: feature           # one of: feature, bugfix, chore, build
              - slug: ...

        Each child requires slug, title, description, and task_type. Backlog #317.
        """
        import sys
        import yaml as _yaml
        from minion.requirements.decompose import decompose as _decompose, _load_spec

        if inline is not None:
            try:
                spec_data = _yaml.safe_load(inline)
            except _yaml.YAMLError as exc:
                _output({"error": f"Invalid inline YAML: {exc}"}, ctx.obj["human"], ctx.obj["compact"])
                ctx.exit(1)
                return
            if not isinstance(spec_data, dict) or "children" not in spec_data:
                _output({"error": "Inline YAML must contain a 'children' key. See `req decompose --help` for the expected shape."}, ctx.obj["human"], ctx.obj["compact"])
                ctx.exit(1)
                return
            # Backlog #317: validate per-child shape loudly so silent zero-children
            # results stop happening. Required keys per child: slug, title, description.
            children = spec_data.get("children")
            if not isinstance(children, list) or not children:
                _output({"error": "Inline YAML 'children' must be a non-empty list. See `req decompose --help`."}, ctx.obj["human"], ctx.obj["compact"])
                ctx.exit(1)
                return
            required_keys = ("slug", "title", "description")
            for i, child in enumerate(children, start=1):
                if not isinstance(child, dict):
                    _output({"error": f"Child #{i} is not a dict. See `req decompose --help` for the expected shape."}, ctx.obj["human"], ctx.obj["compact"])
                    ctx.exit(1)
                    return
                missing = [k for k in required_keys if not child.get(k)]
                if missing:
                    _output({"error": f"Child #{i} missing required keys: {', '.join(missing)}. See `req decompose --help`."}, ctx.obj["human"], ctx.obj["compact"])
                    ctx.exit(1)
                    return
        elif spec == "-":
            try:
                spec_data = _yaml.safe_load(sys.stdin.read())
            except _yaml.YAMLError as exc:
                _output({"error": f"Invalid YAML from stdin: {exc}"}, ctx.obj["human"], ctx.obj["compact"])
                ctx.exit(1)
                return
        elif spec is not None:
            import os as _os
            if not _os.path.exists(spec):
                _output({"error": f"Spec file not found: {spec}"}, ctx.obj["human"], ctx.obj["compact"])
                ctx.exit(1)
                return
            spec_data = _load_spec(spec)
        else:
            _output({"error": "One of --spec or --inline is required."}, ctx.obj["human"], ctx.obj["compact"])
            ctx.exit(1)
            return

        from minion.requirements import resolve_path
        path = resolve_path(path)
        _output(_decompose(path, spec_data, agent_name), ctx.obj["human"], ctx.obj["compact"])

    @req_group.command("itemize")
    @click.option("--path", "-p", required=True, help="Requirement path")
    @click.option("--spec", "-s", required=True, type=click.Path(exists=True), help="YAML spec file with items")
    @click.option("--by", "-b", "created_by", default="lead")
    @click.pass_context
    def req_itemize(ctx: click.Context, path: str, spec: str, created_by: str) -> None:
        """Write itemized-requirements.md from a spec file (accepts ID or path)."""
        import yaml
        with open(spec) as f:
            spec_data = yaml.safe_load(f)
        from minion.requirements import resolve_path, itemize as _itemize
        path = resolve_path(path)
        _output(_itemize(path, spec_data, created_by), ctx.obj["human"], ctx.obj["compact"])

    @req_group.command("findings")
    @click.option("--path", "-p", required=True, help="Requirement path")
    @click.option("--spec", "-s", required=True, type=click.Path(exists=True), help="YAML spec file with findings")
    @click.option("--by", "-b", "created_by", default="lead")
    @click.pass_context
    def req_findings(ctx: click.Context, path: str, spec: str, created_by: str) -> None:
        """Write findings.md from a spec file (accepts ID or path)."""
        import yaml
        with open(spec) as f:
            spec_data = yaml.safe_load(f)
        from minion.requirements import resolve_path, findings as _findings
        path = resolve_path(path)
        _output(_findings(path, spec_data, created_by), ctx.obj["human"], ctx.obj["compact"])

    @req_group.command("report")
    @click.argument("path")
    @click.option("--raw", "-r", is_flag=True, default=False, help="Output raw JSON instead of formatted markdown.")
    @click.pass_context
    def req_report(ctx: click.Context, path: str, raw: bool) -> None:
        """Roll up the full requirement lineage (accepts ID or path)."""
        from minion.requirements import resolve_path, report as _report, format_report as _fmt
        path = resolve_path(path)
        data = _report(path)
        if raw:
            _output(data, ctx.obj["human"], ctx.obj["compact"])
        else:
            click.echo(_fmt(data))
