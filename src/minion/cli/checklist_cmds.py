"""Checklist group — show agent checklists, print templates.

Purpose: CLI commands for checklist template access and agent checklist viewing.
Rationale: Templates ship as package data; runtime checklists live in ~/.minion_work/checklists/.
           This CLI surfaces both without requiring agents to know paths.
Responsibility: `minion checklist show` and `minion checklist template` commands.
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

        Checks ~/.minion_work/checklists/ first, then .work/checklists/ for backward compat.
        """
        import os
        from minion.checklist import read_checklist

        # Try global location first
        content = read_checklist(agent_name)

        if content is None:
            # Fall back to project-local .work/checklists/
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
