"""Root Click group, global options (-C, --human, --compact), and shared helpers.

This module defines the `cli` group and the `_agent_option` / `_store_heartbeat_agent`
helpers used across all command modules. Submodules register their commands/groups
onto `cli` at import time via `register_*` functions called from this file's tail.
"""

from __future__ import annotations

import os

import click

from minion.db import init_db, reset_db_path
from minion.fs import ensure_dirs
from minion.output import output as _output  # noqa: F401 — re-exported for submodules


# ---------------------------------------------------------------------------
# Universal heartbeat — every --agent option auto-touches coordinator DB
# ---------------------------------------------------------------------------

def _store_heartbeat_agent(ctx: click.Context, param: click.Parameter, value: str) -> str:
    """Click callback: stash --agent value so the CLI close handler can heartbeat."""
    if value:
        ctx.ensure_object(dict)
        ctx.obj["_heartbeat_agent"] = value
    return value


def _agent_option(**kwargs):  # noqa: ANN003
    """Drop-in replacement for @click.option('--agent', ...) with auto heartbeat."""
    kwargs.setdefault("callback", _store_heartbeat_agent)
    return click.option("--agent", **kwargs)


@click.group(epilog="Run 'minion <group> --help' to see subcommands. Run 'minion docs' for the full reference.")
@click.version_option(package_name="minion-factory")
@click.option("--human", is_flag=True, help="Human-readable output instead of JSON")
@click.option("--compact", is_flag=True, help="Concise text output for agent context injection")
@click.option("--project-dir", "-C", default=None, help="Project directory (default: cwd)")
@click.pass_context
def cli(ctx: click.Context, human: bool, compact: bool, project_dir: str | None) -> None:
    """minion — multi-agent coordination CLI.

    \b
    Quick start:
      1. Register:  minion agent register --name <you> --class <role>
      2. Poll:      minion poll --agent <you>  (REQUIRED — no poll = no messages)
      3. Send:      minion comms send local  --from <you> --to <target> --message '...'
                    minion comms send global --from <you> --to <target> --message '...'

    \b
    Communication:
      LOCAL  (comms send local)  — same-repo agents. Messages in .work/minion.db.
      GLOBAL (comms send global) — cross-repo agents. Routes via ~/.minion/coordinator.db.
      Poll checks BOTH automatically."""
    ctx.ensure_object(dict)
    ctx.obj["human"] = human
    ctx.obj["compact"] = compact
    ctx.obj["project_dir"] = os.path.abspath(project_dir) if project_dir else None
    # Set DB path before init so all commands target the right project
    if project_dir:
        db_path = os.path.join(os.path.abspath(project_dir), ".work", "minion.db")
        os.environ["MINION_DB_PATH"] = db_path
        reset_db_path()
    init_db()
    ensure_dirs()

    # Universal heartbeat: any command with --agent marks agent active in coordinator
    def _heartbeat_on_close() -> None:
        agent = ctx.obj.get("_heartbeat_agent")
        if agent:
            try:
                from minion.db import touch_coordinator_activity
                touch_coordinator_activity(agent)
            except Exception:
                pass

    ctx.call_on_close(_heartbeat_on_close)


# ---------------------------------------------------------------------------
# Register all command groups/commands onto cli
# ---------------------------------------------------------------------------

from minion.cli.agent_cmds import register_commands as _reg_agent  # noqa: E402
from minion.cli.comms_cmds import register_commands as _reg_comms  # noqa: E402
from minion.cli.task_cmds import register_commands as _reg_task  # noqa: E402
from minion.cli.flow_cmds import register_commands as _reg_flow  # noqa: E402
from minion.cli.war_cmds import register_commands as _reg_war  # noqa: E402
from minion.cli.file_cmds import register_commands as _reg_file  # noqa: E402
from minion.cli.crew_cmds import register_commands as _reg_crew  # noqa: E402
from minion.cli.trigger_cmds import register_commands as _reg_trigger  # noqa: E402
from minion.cli.daemon_cmds import register_commands as _reg_daemon  # noqa: E402
from minion.cli.mission_cmds import register_commands as _reg_mission  # noqa: E402
from minion.cli.backlog_cmds import register_commands as _reg_backlog  # noqa: E402
from minion.cli.war_plan_cmds import register_commands as _reg_war_plan  # noqa: E402
from minion.cli.intel_cmds import register_commands as _reg_intel  # noqa: E402
from minion.cli.req_cmds import register_commands as _reg_req  # noqa: E402
from minion.cli.global_cmds import register_commands as _reg_global  # noqa: E402
from minion.cli.api_cmds import register_commands as _reg_api  # noqa: E402
from minion.cli.network_cmds import register_commands as _reg_network  # noqa: E402
from minion.cli.top_level import register_commands as _reg_top  # noqa: E402
from minion.cli.aliases import register_aliases  # noqa: E402

_reg_agent(cli)
_reg_comms(cli)
_reg_task(cli)
_reg_flow(cli)
_reg_war(cli)
_reg_file(cli)
_reg_crew(cli)
_reg_trigger(cli)
_reg_daemon(cli)
_reg_mission(cli)
_reg_backlog(cli)
_reg_war_plan(cli)
_reg_intel(cli)
_reg_req(cli)
_reg_global(cli)
_reg_api(cli)
_reg_network(cli)
_reg_top(cli)
register_aliases(cli)
