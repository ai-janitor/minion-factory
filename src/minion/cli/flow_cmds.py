"""Flow group — list, show, next-status, transition.
Inspect task flow DAGs: stages, transitions, and routing rules.

Purpose: Flow group — list, show, next-status, transition.
Rationale: Extracted into own module for single-responsibility CLI command grouping.
Responsibility: Flow group — list, show, next-status, transition. NOT responsible for unrelated concerns.
Organization: Click command group with subcommands."""

from __future__ import annotations

import sys

import click

from minion.cli.main import _agent_option, _output


def register_commands(cli: click.Group) -> None:
    """Attach the flow group and its subcommands to the root CLI."""

    @cli.group("flow")
    @click.pass_context
    def flow_group(ctx: click.Context) -> None:
        """Inspect task flow DAGs — see stages, transitions, and routing rules."""
        pass

    @flow_group.command("list")
    @click.option("--verbose", "-v", is_flag=True, help="Show description, pipeline, and stage count for each flow")
    @click.pass_context
    def list_flows_cmd(ctx: click.Context, verbose: bool) -> None:
        """List available task flow types."""
        if verbose:
            from minion.tasks.loader import list_flows_detailed
            _output({"flows": list_flows_detailed()}, ctx.obj["human"], ctx.obj["compact"])
        else:
            from minion.tasks import list_flows
            _output({"flows": list_flows()}, ctx.obj["human"])

    @flow_group.command("show")
    @click.argument("type_name")
    @click.pass_context
    def show_flow(ctx: click.Context, type_name: str) -> None:
        """Show a flow's stages and transitions."""
        from minion.tasks.loader import load_flow
        try:
            flow = load_flow(type_name)
        except FileNotFoundError as e:
            _output({"error": str(e)})
            sys.exit(1)
        stages = []
        for name, stage in flow.stages.items():
            stages.append({
                "name": name,
                "description": stage.description,
                "next": stage.next,
                "fail": stage.fail,
                "workers": stage.workers,
                "requires": stage.requires,
                "terminal": stage.terminal,
                "skip": stage.skip,
            })
        _output({"name": flow.name, "description": flow.description, "stages": stages, "dead_ends": flow.dead_ends}, ctx.obj["human"], ctx.obj["compact"])

    @flow_group.command("next-status")
    @click.argument("type_name")
    @click.argument("current")
    @click.option("--failed", is_flag=True, help="Query fail path instead of happy path")
    @click.pass_context
    def next_status(ctx: click.Context, type_name: str, current: str, failed: bool) -> None:
        """Query routing: what status comes next?"""
        from minion.tasks.loader import load_flow
        try:
            flow = load_flow(type_name)
        except FileNotFoundError as e:
            _output({"error": str(e)})
            sys.exit(1)
        result = flow.next_status(current, passed=not failed)
        _output({"type": type_name, "current": current, "next": result}, ctx.obj["human"], ctx.obj["compact"])

    @flow_group.command("transition")
    @click.argument("task_id", type=int)
    @click.argument("to_status")
    @_agent_option(required=True, help="Agent triggering transition")
    @click.pass_context
    def transition(ctx: click.Context, task_id: int, to_status: str, agent: str) -> None:
        """Manually transition a task to a new status."""
        from minion.tasks import update_task
        result = update_task(agent, task_id, status=to_status)
        _output(result, ctx.obj["human"], ctx.obj["compact"])
