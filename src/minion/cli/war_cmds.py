"""War group — set-plan, get-plan, update-status, log, list-log.
Session strategy: objectives and progress tracking.

Purpose: War group — set-plan, get-plan, update-status, log, list-log.
Rationale: Extracted into own module for single-responsibility CLI command grouping.
Responsibility: War group — set-plan, get-plan, update-status, log, list-log. NOT responsible for unrelated concerns.
Organization: Click command group with subcommands."""

from __future__ import annotations

import click

from minion.cli.main import _agent_option, _output


def register_commands(cli: click.Group) -> None:
    """Attach the war group and its subcommands to the root CLI."""

    @cli.group("war")
    @click.pass_context
    def war_group(ctx: click.Context) -> None:
        """Session strategy — set objectives and log progress entries."""
        pass

    @war_group.command("set-plan")
    @_agent_option(required=True)
    @click.option("--plan", required=True)
    @click.pass_context
    def set_battle_plan(ctx: click.Context, agent: str, plan: str) -> None:
        """Set the session's current objective. Lead only."""
        from minion.auth import require_class
        require_class("lead")(lambda: None)()
        from minion.warroom import set_battle_plan as _set_battle_plan
        _output(_set_battle_plan(agent, plan), ctx.obj["human"])

    @war_group.command("get-plan")
    @click.option("--status", default="active", type=click.Choice(["active", "superseded", "completed", "abandoned", "obsolete"]))
    @click.pass_context
    def get_battle_plan(ctx: click.Context, status: str) -> None:
        """Get the session objective by status."""
        from minion.warroom import get_battle_plan as _get_battle_plan
        _output(_get_battle_plan(status), ctx.obj["human"])

    @war_group.command("update-status")
    @_agent_option(required=True)
    @click.option("--plan-id", required=True, type=int)
    @click.option("--status", required=True, type=click.Choice(["active", "superseded", "completed", "abandoned", "obsolete"]))
    @click.pass_context
    def update_battle_plan_status(ctx: click.Context, agent: str, plan_id: int, status: str) -> None:
        """Update an objective's status. Lead only."""
        from minion.auth import require_class
        require_class("lead")(lambda: None)()
        from minion.warroom import update_battle_plan_status as _update
        _output(_update(agent, plan_id, status), ctx.obj["human"])

    @war_group.command("log")
    @_agent_option(required=True)
    @click.option("--entry", required=True)
    @click.option("--priority", default="normal", type=click.Choice(["low", "normal", "high", "critical"]))
    @click.pass_context
    def log_raid(ctx: click.Context, agent: str, entry: str, priority: str) -> None:
        """Log a progress entry — what was done, decisions made, blockers hit."""
        from minion.warroom import log_raid as _log_raid
        _output(_log_raid(agent, entry, priority), ctx.obj["human"])

    @war_group.command("list-log")
    @click.option("--priority", default=None, type=click.Choice(["low", "normal", "high", "critical"]))
    @click.option("--count", default=20, type=int)
    @_agent_option(default="")
    @click.pass_context
    def list_raid_log(ctx: click.Context, priority: str, count: int, agent: str) -> None:
        """Read the progress log."""
        from minion.warroom import get_raid_log as _get_raid_log
        _output(_get_raid_log(priority, count, agent), ctx.obj["human"])
