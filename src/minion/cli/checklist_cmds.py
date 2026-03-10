"""Checklist group — show agent checklists, print templates, generate from template.

Purpose: CLI commands for checklist template access, agent checklist viewing, and generation.
Rationale: Templates ship as package data; runtime checklists live in .work/checklists/.
           This CLI surfaces both without requiring agents to know paths.
Responsibility: `minion checklist show`, `minion checklist template`, `minion checklist generate` commands.
Organization: Click command group with subcommands."""

from __future__ import annotations

import click

from minion.cli.main import _output


def register_commands(cli: click.Group) -> None:
    """Attach the checklist group and its subcommands to the root CLI."""

    @cli.group("checklist")
    @click.pass_context
    def checklist_group(ctx: click.Context) -> None:
        """View agent checklists and print checklist templates."""
        pass

    @checklist_group.command("show")
    @click.argument("agent_name")
    @click.pass_context
    def checklist_show(ctx: click.Context, agent_name: str) -> None:
        """Read and display an agent's checklist.

        Checks .work/checklists/ for the agent's checklist file.
        """
        import os
        from minion.checklist import read_checklist

        # Try project-local .work/checklists/
        content = read_checklist(agent_name)

        if content is None:
            # Fall back to explicit project-local .work/checklists/ with lead- prefix
            work_dir = os.path.join(os.getcwd(), ".work", "checklists")
            for pattern in (f"lead-{agent_name}.md", f"{agent_name}.md"):
                path = os.path.join(work_dir, pattern)
                if os.path.exists(path):
                    with open(path, encoding="utf-8") as f:
                        content = f.read()
                    break

        if content is None:
            _output(
                {"status": "not_found", "agent": agent_name, "message": f"No checklist found for '{agent_name}'."},
                ctx.obj["human"],
                ctx.obj["compact"],
            )
        else:
            if ctx.obj["human"]:
                click.echo(content)
            else:
                _output(
                    {"status": "ok", "agent": agent_name, "content": content},
                    ctx.obj["human"],
                    ctx.obj["compact"],
                )

    @checklist_group.command("template")
    @click.argument("template_type", type=click.Choice(["napoleon", "lead", "worker"]))
    @click.pass_context
    def checklist_template(ctx: click.Context, template_type: str) -> None:
        """Print a checklist template (napoleon, lead, or worker)."""
        from minion.checklist import get_template_path

        try:
            path = get_template_path(template_type)
            content = path.read_text(encoding="utf-8")
            if ctx.obj["human"]:
                click.echo(content)
            else:
                _output(
                    {"status": "ok", "template": template_type, "path": str(path), "content": content},
                    ctx.obj["human"],
                    ctx.obj["compact"],
                )
        except (ValueError, FileNotFoundError) as exc:
            _output(
                {"status": "error", "message": str(exc)},
                ctx.obj["human"],
                ctx.obj["compact"],
            )

    @checklist_group.command("generate")
    @click.option("-a", "--agent", required=True, help="Agent name")
    @click.option("--task-id", type=int, help="Task ID to look up phase and class")
    @click.option(
        "--type",
        "template_type",
        type=click.Choice(["napoleon", "lead", "worker"]),
        help="Manual template override",
    )
    @click.pass_context
    def checklist_generate(ctx: click.Context, agent: str, task_id: int | None, template_type: str | None) -> None:
        """Generate a checklist from template, write to .work/checklists/<agent>.md.

        Resolution order:
        1. If --task-id: look up task's status (phase) and assigned agent's class,
           try <class>-<phase> template first, then class default.
        2. If --type: use that template directly.
        3. Error if nothing resolves.
        """
        import sqlite3

        from minion.checklist import get_checklist_dir, resolve_template, get_template_path, write_checklist
        from minion.defaults import resolve_db_path

        template_path = None
        resolved_task_id = task_id

        # Step 1: If --task-id provided, look up task to get phase and agent class
        if task_id is not None:
            try:
                db_path = resolve_db_path()
                conn = sqlite3.connect(db_path)
                conn.row_factory = sqlite3.Row

                # Get task status (phase) and assigned agent
                row = conn.execute(
                    "SELECT status, assigned_to, flow_type FROM tasks WHERE id = ?",
                    (task_id,),
                ).fetchone()

                if row is None:
                    _output(
                        {"status": "error", "message": f"Task #{task_id} not found."},
                        ctx.obj["human"],
                        ctx.obj["compact"],
                    )
                    conn.close()
                    return

                phase = row["status"]
                assigned_to = row["assigned_to"]

                # Look up assigned agent's class
                agent_class = None
                if assigned_to:
                    agent_row = conn.execute(
                        "SELECT agent_class FROM agents WHERE name = ?",
                        (assigned_to,),
                    ).fetchone()
                    if agent_row:
                        agent_class = agent_row["agent_class"]

                conn.close()

                # Try to resolve template from class + phase
                if agent_class:
                    try:
                        template_path = resolve_template(agent_class, phase)
                    except ValueError:
                        pass  # Fall through to --type or error

            except (sqlite3.Error, OSError) as exc:
                _output(
                    {"status": "error", "message": f"DB error looking up task #{task_id}: {exc}"},
                    ctx.obj["human"],
                    ctx.obj["compact"],
                )
                return

        # Step 2: If no template resolved yet, use --type flag
        if template_path is None and template_type is not None:
            try:
                template_path = get_template_path(template_type)
            except (ValueError, FileNotFoundError) as exc:
                _output(
                    {"status": "error", "message": str(exc)},
                    ctx.obj["human"],
                    ctx.obj["compact"],
                )
                return

        # Step 3: Error if nothing resolved
        if template_path is None:
            _output(
                {
                    "status": "error",
                    "message": "Cannot resolve template. Provide --task-id (with assigned agent) or --type.",
                },
                ctx.obj["human"],
                ctx.obj["compact"],
            )
            return

        # Read template and substitute placeholders
        content = template_path.read_text(encoding="utf-8")
        content = content.replace("<name>", agent)
        if resolved_task_id is not None:
            content = content.replace("<task-id>", str(resolved_task_id))

        # Write to project-local .work/checklists/<agent>.md
        output_path = write_checklist(agent, content)

        _output(
            {"status": "ok", "agent": agent, "path": str(output_path), "message": f"Checklist written to {output_path}"},
            ctx.obj["human"],
            ctx.obj["compact"],
        )
