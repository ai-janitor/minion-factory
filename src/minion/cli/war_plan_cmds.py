"""War-plan group — show, set, append.
Persistent project war plan stored in .work/intel/.

Purpose: War-plan group — show, set, append.
Rationale: Extracted into own module for single-responsibility CLI command grouping.
Responsibility: War-plan group — show, set, append. NOT responsible for unrelated concerns.
Organization: Click command group with subcommands."""

from __future__ import annotations

import click

from minion.cli.main import _agent_option, _output


def register_commands(cli: click.Group) -> None:
    """Attach the war-plan group and its subcommands to the root CLI."""

    @cli.group("war-plan")
    @click.pass_context
    def war_plan_group(ctx: click.Context) -> None:
        """Set and read the persistent project war plan."""
        pass

    @war_plan_group.command("show")
    @click.pass_context
    def war_plan_show(ctx: click.Context) -> None:
        """Print the current war plan content."""
        from minion.intel import show_war_plan as _show_war_plan
        _output(_show_war_plan(), ctx.obj["human"], ctx.obj["compact"])

    @war_plan_group.command("set")
    @_agent_option(required=True, help="Lead agent setting the war plan")
    @click.option("--text", required=True, help="War plan content to write")
    @click.pass_context
    def war_plan_set(ctx: click.Context, agent: str, text: str) -> None:
        """Overwrite the war plan (lead-only)."""
        from minion.intel import set_war_plan as _set_war_plan
        _output(_set_war_plan(agent, text), ctx.obj["human"], ctx.obj["compact"])

    @war_plan_group.command("append")
    @_agent_option(required=True, help="Lead agent appending to the war plan")
    @click.option("--text", required=True, help="Text to append")
    @click.pass_context
    def war_plan_append(ctx: click.Context, agent: str, text: str) -> None:
        """Append text to the war plan (lead-only)."""
        from minion.intel import append_war_plan as _append_war_plan
        _output(_append_war_plan(agent, text), ctx.obj["human"], ctx.obj["compact"])
