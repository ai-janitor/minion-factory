"""Click CLI entrypoint — `minion <subcommand>`.

Every call is stateless. JSON output by default, --human for tables.
MINION_CLASS env var gates commands via auth.require_class.
"""

from __future__ import annotations

import os
import sys

import click

from minion.db import init_db, reset_db_path
from minion.fs import ensure_dirs
from minion.output import output as _output


@click.group(epilog="Run 'minion <group> --help' to see subcommands. Run 'minion docs' for the full reference.")
@click.version_option(package_name="minion-factory")
@click.option("--human", is_flag=True, help="Human-readable output instead of JSON")
@click.option("--compact", is_flag=True, help="Concise text output for agent context injection")
@click.option("--project-dir", "-C", default=None, help="Project directory (default: cwd)")
@click.pass_context
def cli(ctx: click.Context, human: bool, compact: bool, project_dir: str | None) -> None:
    """minion — multi-agent coordination CLI."""
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


# =========================================================================
# Agent group
# =========================================================================

@cli.group("agent")
@click.pass_context
def agent_group(ctx: click.Context) -> None:
    """Join the session, report your state, and manage your identity."""
    pass


@agent_group.command("register")
@click.option("--name", required=True)
@click.option("--class", "agent_class", required=True, type=click.Choice(["lead", "coder", "builder", "oracle", "recon", "planner", "auditor"]))
@click.option("--model", default="")
@click.option("--description", default="")
@click.option("--transport", default="terminal", type=click.Choice(["terminal", "daemon", "daemon-ts"]))
@click.option("--crew", default="", help="Crew YAML name — injects zone, capabilities, system prompt excerpt")
@click.pass_context
def register(ctx: click.Context, name: str, agent_class: str, model: str, description: str, transport: str, crew: str) -> None:
    """Register an agent."""
    from minion.comms import register as _register
    _output(_register(name, agent_class, model, description, transport, crew), ctx.obj["human"], ctx.obj["compact"])


@agent_group.command("set-status")
@click.option("--agent", required=True)
@click.option("--status", required=True)
@click.pass_context
def set_status(ctx: click.Context, agent: str, status: str) -> None:
    """Set agent status."""
    from minion.comms import set_status as _set_status
    _output(_set_status(agent, status), ctx.obj["human"])


@agent_group.command("set-context")
@click.option("--agent", required=True)
@click.option("--context", required=True)
@click.option("--tokens-used", default=0, type=int)
@click.option("--tokens-limit", default=0, type=int)
@click.option("--hp", default=None, type=int, help="Self-reported HP 0-100 (skips daemon token counting)")
@click.option("--files-modified", default="", help="Comma-separated files modified this turn; warns if unclaimed")
@click.pass_context
def set_context(ctx: click.Context, agent: str, context: str, tokens_used: int, tokens_limit: int, hp: int | None, files_modified: str) -> None:
    """Update context summary and health (tokens used, token limit)."""
    from minion.comms import set_context as _set_context
    _output(_set_context(agent, context, tokens_used, tokens_limit, hp, files_modified), ctx.obj["human"])


@agent_group.command("who")
@click.pass_context
def who(ctx: click.Context) -> None:
    """List all registered agents."""
    from minion.comms import who as _who
    _output(_who(), ctx.obj["human"])


@agent_group.command("update-hp")
@click.option("--agent", required=True)
@click.option("--input-tokens", required=True, type=int)
@click.option("--output-tokens", required=True, type=int)
@click.option("--limit", required=True, type=int)
@click.option("--turn-input", default=None, type=int, help="Per-turn input tokens (current context pressure)")
@click.option("--turn-output", default=None, type=int, help="Per-turn output tokens (current context pressure)")
@click.pass_context
def update_hp(ctx: click.Context, agent: str, input_tokens: int, output_tokens: int, limit: int, turn_input: int | None, turn_output: int | None) -> None:
    """Daemon-only: record token usage and compute health score."""
    from minion.monitoring import update_hp as _update_hp
    _output(_update_hp(agent, input_tokens, output_tokens, limit, turn_input, turn_output), ctx.obj["human"])


@agent_group.command("cold-start")
@click.option("--agent", required=True)
@click.pass_context
def cold_start(ctx: click.Context, agent: str) -> None:
    """Bootstrap an agent into (or back into) a session."""
    from minion.lifecycle import cold_start as _cold_start
    _output(_cold_start(agent), ctx.obj["human"], ctx.obj["compact"])


@agent_group.command("fenix-down")
@click.option("--agent", required=True)
@click.option("--files", required=True)
@click.option("--manifest", default="")
@click.pass_context
def fenix_down(ctx: click.Context, agent: str, files: str, manifest: str) -> None:
    """Save session state to disk before context window runs out."""
    from minion.lifecycle import fenix_down as _fenix_down
    _output(_fenix_down(agent, files, manifest), ctx.obj["human"])


@agent_group.command("retire")
@click.option("--agent", required=True, help="Agent to retire")
@click.option("--requesting-agent", required=True, help="Lead requesting retirement")
@click.pass_context
def retire_agent_cmd(ctx: click.Context, agent: str, requesting_agent: str) -> None:
    """Signal a single daemon agent to exit gracefully. Lead only."""
    from minion.auth import require_class
    require_class("lead")(lambda: None)()
    from minion.crew import retire_agent as _retire_agent
    _output(_retire_agent(agent, requesting_agent), ctx.obj["human"])


@agent_group.command("check-activity")
@click.option("--agent", required=True)
@click.pass_context
def check_activity(ctx: click.Context, agent: str) -> None:
    """Check an agent's activity level."""
    from minion.monitoring import check_activity as _check_activity
    _output(_check_activity(agent), ctx.obj["human"])


@agent_group.command("check-freshness")
@click.option("--agent", required=True)
@click.option("--files", required=True)
@click.pass_context
def check_freshness(ctx: click.Context, agent: str, files: str) -> None:
    """Check file freshness relative to agent's last set-context. Lead only."""
    from minion.auth import require_class
    require_class("lead")(lambda: None)()
    from minion.monitoring import check_freshness as _check_freshness
    _output(_check_freshness(agent, files), ctx.obj["human"])


# =========================================================================
# Comms group
# =========================================================================

@cli.group("comms")
@click.pass_context
def comms_group(ctx: click.Context) -> None:
    """Send and receive messages between agents."""
    pass


@comms_group.command("send")
@click.option("--from", "from_agent", required=True)
@click.option("--to", "to_agent", required=True)
@click.option("--message", required=True)
@click.option("--cc", default="")
@click.pass_context
def send(ctx: click.Context, from_agent: str, to_agent: str, message: str, cc: str) -> None:
    """Send a message to an agent (or 'all' for broadcast)."""
    from minion.comms import send as _send
    _output(_send(from_agent, to_agent, message, cc), ctx.obj["human"])


@comms_group.command("check-inbox")
@click.option("--agent", required=True)
@click.pass_context
def check_inbox(ctx: click.Context, agent: str) -> None:
    """Check and clear unread messages."""
    from minion.comms import check_inbox as _check_inbox
    _output(_check_inbox(agent), ctx.obj["human"])


@comms_group.command("purge-inbox")
@click.option("--agent", required=True)
@click.option("--older-than-hours", default=2, type=int)
@click.pass_context
def purge_inbox(ctx: click.Context, agent: str, older_than_hours: int) -> None:
    """Delete old messages from inbox."""
    from minion.comms import purge_inbox as _purge_inbox
    _output(_purge_inbox(agent, older_than_hours), ctx.obj["human"])


@comms_group.command("list-history")
@click.option("--count", default=20, type=int)
@click.pass_context
def list_history(ctx: click.Context, count: int) -> None:
    """Return the last N messages across all agents."""
    from minion.comms import get_history as _get_history
    _output(_get_history(count), ctx.obj["human"])


# =========================================================================
# Task group
# =========================================================================

@cli.group("task")
@click.pass_context
def task_group(ctx: click.Context) -> None:
    """Create, assign, and update work items. Track progress through the DAG."""
    pass


@task_group.command("create")
@click.option("--agent", required=True)
@click.option("--title", required=True)
@click.option("--task-file", required=True)
@click.option("--project", default="")
@click.option("--zone", default="")
@click.option("--blocked-by", default="")
@click.option("--class-required", default="", help="Agent class required (e.g. coder, builder, recon)")
@click.option("--type", "task_type", default="bugfix", type=click.Choice(["bugfix", "build", "chore", "feature", "hotfix", "investigation", "requirement", "research"]))
@click.pass_context
def create_task(ctx: click.Context, agent: str, title: str, task_file: str, project: str, zone: str, blocked_by: str, class_required: str, task_type: str) -> None:
    """Create a new task. Lead only."""
    from minion.auth import require_class
    require_class("lead")(lambda: None)()
    from minion.tasks import create_task as _create_task
    _output(_create_task(agent, title, task_file, project, zone, blocked_by, class_required, task_type), ctx.obj["human"])


@task_group.command("assign")
@click.option("--agent", required=True)
@click.option("--task-id", required=True, type=int)
@click.option("--assigned-to", required=True)
@click.pass_context
def assign_task(ctx: click.Context, agent: str, task_id: int, assigned_to: str) -> None:
    """Assign a task to an agent. Lead only."""
    from minion.auth import require_class
    require_class("lead")(lambda: None)()
    from minion.tasks import assign_task as _assign_task
    _output(_assign_task(agent, task_id, assigned_to), ctx.obj["human"])


@task_group.command("update")
@click.option("--agent", required=True)
@click.option("--task-id", required=True, type=int)
@click.option("--status", default="")
@click.option("--progress", default="")
@click.option("--files", default="")
@click.pass_context
def update_task(ctx: click.Context, agent: str, task_id: int, status: str, progress: str, files: str) -> None:
    """Update a task's status, progress, or files."""
    from minion.tasks import update_task as _update_task
    _output(_update_task(agent, task_id, status, progress, files), ctx.obj["human"])


@task_group.command("list")
@click.option("--status", default="")
@click.option("--project", default="")
@click.option("--zone", default="")
@click.option("--assigned-to", default="")
@click.option("--class-required", default="", help="Filter by required agent class")
@click.option("--count", default=50, type=int)
@click.pass_context
def list_tasks(ctx: click.Context, status: str, project: str, zone: str, assigned_to: str, class_required: str, count: int) -> None:
    """List tasks."""
    from minion.tasks import get_tasks as _get_tasks
    _output(_get_tasks(status, project, zone, assigned_to, class_required, count), ctx.obj["human"])


@task_group.command("get")
@click.option("--task-id", required=True, type=int)
@click.pass_context
def get_task(ctx: click.Context, task_id: int) -> None:
    """Get full detail for a single task."""
    from minion.tasks import get_task as _get_task
    _output(_get_task(task_id), ctx.obj["human"])


@task_group.command("spec")
@click.option("--task-id", required=True, type=int)
@click.pass_context
def task_spec_cmd(ctx: click.Context, task_id: int) -> None:
    """Read the spec file contents for a task by ID."""
    from minion.tasks import get_spec as _get_spec
    result = _get_spec(task_id)
    if ctx.obj["human"] and "spec" in result:
        click.echo(result["spec"])
    else:
        _output(result, ctx.obj["human"])


@task_group.command("lineage")
@click.option("--task-id", required=True, type=int)
@click.pass_context
def task_lineage(ctx: click.Context, task_id: int) -> None:
    """Show task lineage — DAG history and who worked each stage."""
    from minion.tasks import get_task_lineage as _get_lineage
    _output(_get_lineage(task_id), ctx.obj["human"])


@task_group.command("submit-result")
@click.option("--agent", required=True)
@click.option("--task-id", required=True, type=int)
@click.option("--result-file", required=True)
@click.pass_context
def submit_result(ctx: click.Context, agent: str, task_id: int, result_file: str) -> None:
    """Submit a result file for a task."""
    from minion.tasks import submit_result as _submit_result
    _output(_submit_result(agent, task_id, result_file), ctx.obj["human"])


@task_group.command("close")
@click.option("--agent", required=True)
@click.option("--task-id", required=True, type=int)
@click.pass_context
def close_task(ctx: click.Context, agent: str, task_id: int) -> None:
    """Close a task. Lead only."""
    from minion.auth import require_class
    require_class("lead")(lambda: None)()
    from minion.tasks import close_task as _close_task
    _output(_close_task(agent, task_id), ctx.obj["human"])


@task_group.command("done")
@click.option("--agent", required=True)
@click.option("--task-id", required=True, type=int)
@click.option("--summary", default="", help="Optional summary of externally completed work")
@click.pass_context
def done_task_cmd(ctx: click.Context, agent: str, task_id: int, summary: str) -> None:
    """Fast-close a task completed outside the DAG. Lead only."""
    from minion.auth import require_class
    require_class("lead")(lambda: None)()
    from minion.tasks import done_task as _done_task
    _output(_done_task(agent, task_id, summary), ctx.obj["human"])


@task_group.command("reopen")
@click.option("--agent", required=True)
@click.option("--task-id", required=True, type=int)
@click.option("--to-status", default="assigned", help="Target status (default: assigned)")
@click.pass_context
def reopen_task_cmd(ctx: click.Context, agent: str, task_id: int, to_status: str) -> None:
    """Reopen a terminal task back to an earlier phase. Lead only."""
    from minion.tasks import reopen_task as _reopen_task
    _output(_reopen_task(agent, task_id, to_status), ctx.obj["human"])


@task_group.command("pull")
@click.option("--agent", required=True)
@click.option("--task-id", required=True, type=int)
@click.pass_context
def pull_task_cmd(ctx: click.Context, agent: str, task_id: int) -> None:
    """Claim a specific task by ID."""
    from minion.tasks import pull_task as _pull_task
    _output(_pull_task(agent, task_id), ctx.obj["human"])


@task_group.command("complete-phase")
@click.option("--agent", required=True)
@click.option("--task-id", required=True, type=int)
@click.option("--failed", is_flag=True, help="Mark as failed (routes to fail branch in DAG)")
@click.option("--reason", default=None, help="Required when blocking — why you're stuck")
@click.pass_context
def complete_phase_cmd(ctx: click.Context, agent: str, task_id: int, failed: bool, reason: str | None) -> None:
    """Complete your phase — DAG routes to next stage."""
    from minion.tasks import complete_phase as _complete_phase
    _output(_complete_phase(agent, task_id, passed=not failed, reason=reason), ctx.obj["human"])


@task_group.command("check-work")
@click.option("--agent", required=True)
@click.pass_context
def check_work_cmd(ctx: click.Context, agent: str) -> None:
    """Check if agent has available tasks. Exit 0 = work, 1 = no work."""
    from minion.polling import _find_available_tasks
    tasks = _find_available_tasks(agent)
    _output({"has_work": len(tasks) > 0, "task_count": len(tasks), "tasks": tasks}, ctx.obj["human"])
    sys.exit(0 if tasks else 1)


@task_group.command("comment")
@click.option("--agent", required=True)
@click.option("--task-id", required=True, type=int)
@click.option("--message", required=True)
@click.option("--files", default="", help="Comma-separated file paths read for context")
@click.pass_context
def task_comment_cmd(ctx: click.Context, agent: str, task_id: int, message: str, files: str) -> None:
    """Add a comment to a task with optional file context."""
    from minion.tasks.comments import add_comment
    files_list = [f.strip() for f in files.split(",") if f.strip()] if files else None
    _output(add_comment(agent, task_id, message, files_read=files_list), ctx.obj["human"])


@task_group.command("comments")
@click.option("--task-id", required=True, type=int)
@click.pass_context
def task_comments_cmd(ctx: click.Context, task_id: int) -> None:
    """List all comments for a task."""
    from minion.tasks.comments import list_comments
    _output(list_comments(task_id), ctx.obj["human"])


@task_group.command("define")
@click.option("--agent", required=True)
@click.option("--title", required=True)
@click.option("--description", required=True)
@click.option("--task-type", default="feature", type=click.Choice(["feature", "bugfix", "chore"]))
@click.option("--project", default="")
@click.option("--zone", default="")
@click.option("--blocked-by", default="", help="Comma-separated task IDs")
@click.option("--class-required", default="")
@click.pass_context
def task_define_cmd(ctx: click.Context, agent: str, title: str, description: str,
                    task_type: str, project: str, zone: str, blocked_by: str, class_required: str) -> None:
    """Create a task spec file and task record in one command."""
    from minion.tasks.define import define_task
    _output(define_task(agent, title, description, task_type, project, zone, blocked_by, class_required), ctx.obj["human"])


@task_group.command("result")
@click.option("--agent", required=True)
@click.option("--task-id", required=True, type=int)
@click.option("--summary", required=True)
@click.option("--files-changed", default="", help="Comma-separated list of changed files")
@click.option("--notes", default="")
@click.pass_context
def task_result_cmd(ctx: click.Context, agent: str, task_id: int, summary: str,
                    files_changed: str, notes: str) -> None:
    """Write a result file and submit it for a task."""
    from minion.tasks.result import create_result
    _output(create_result(agent, task_id, summary, files_changed, notes), ctx.obj["human"])


@task_group.command("review")
@click.option("--agent", required=True)
@click.option("--task-id", required=True, type=int)
@click.option("--verdict", required=True, type=click.Choice(["pass", "fail"]))
@click.option("--notes", default="")
@click.pass_context
def task_review_cmd(ctx: click.Context, agent: str, task_id: int, verdict: str, notes: str) -> None:
    """Write a review verdict and advance the task phase."""
    from minion.tasks.review import create_review
    _output(create_review(agent, task_id, verdict, notes), ctx.obj["human"])


@task_group.command("test")
@click.option("--agent", required=True)
@click.option("--task-id", required=True, type=int)
@click.option("--passed/--failed", required=True, help="Test outcome")
@click.option("--output", "test_output", default="", help="Test output text")
@click.option("--notes", default="")
@click.pass_context
def task_test_cmd(ctx: click.Context, agent: str, task_id: int, passed: bool,
                  test_output: str, notes: str) -> None:
    """Write a test report and advance the task phase."""
    from minion.tasks.test_report import create_test_report
    _output(create_test_report(agent, task_id, passed, test_output, notes), ctx.obj["human"])


@task_group.command("block")
@click.option("--agent", required=True)
@click.option("--task-id", required=True, type=int)
@click.option("--reason", required=True)
@click.pass_context
def task_block_cmd(ctx: click.Context, agent: str, task_id: int, reason: str) -> None:
    """Block a task with a reason and transition to blocked status."""
    from minion.tasks.block import block_task
    _output(block_task(agent, task_id, reason), ctx.obj["human"])


@task_group.command("spawn")
@click.option("--task-id", required=True, type=int)
@click.option("--profile", required=True, help="Agent profile name (crew YAML key)")
@click.option("--name", "agent_name", default=None, help="Runtime agent name (defaults to profile)")
@click.option("--crew", required=True)
@click.option("--format", "fmt", default="json", type=click.Choice(["json", "text", "prompt"]))
@click.pass_context
def task_spawn_cmd(ctx: click.Context, task_id: int, profile: str, agent_name: str | None, crew: str, fmt: str) -> None:
    """Output a spawn-ready prompt for an agent + task."""
    from minion.tasks.spawn_prompt import get_spawn_prompt, format_as_prompt
    resolved_name = agent_name if agent_name is not None else profile
    result = get_spawn_prompt(task_id, profile_name=profile, agent_name=resolved_name, crew_name=crew)
    if fmt == "prompt":
        if "error" in result:
            click.echo(f"ERROR: {result['error']}", err=True)
            ctx.exit(1)
            return
        click.echo(format_as_prompt(result))
    elif fmt == "text":
        if "error" in result:
            click.echo(f"ERROR: {result['error']}", err=True)
            ctx.exit(1)
            return
        click.echo("=" * 60)
        click.echo("SYSTEM PROMPT")
        click.echo("=" * 60)
        click.echo(result.get("system_prompt", ""))
        click.echo()
        click.echo("=" * 60)
        click.echo("TASK BRIEFING")
        click.echo("=" * 60)
        click.echo(result.get("task_briefing", ""))
        click.echo()
        click.echo(f"Model:       {result.get('model', 'default')}")
        click.echo(f"Permissions: {result.get('permission_mode', 'default')}")
        tools = result.get("tools") or []
        click.echo(f"Tools:       {len(tools)} commands")
        for t in tools:
            click.echo(f"  - {t.get('command', t)}")
    else:
        _output(result, ctx.obj["human"], ctx.obj["compact"])


# =========================================================================
# Flow group
# =========================================================================

@cli.group("flow")
@click.pass_context
def flow_group(ctx: click.Context) -> None:
    """Inspect task flow DAGs — see stages, transitions, and routing rules."""
    pass


@flow_group.command("list")
@click.pass_context
def list_flows_cmd(ctx: click.Context) -> None:
    """List available task flow types."""
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
        return
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
        return
    result = flow.next_status(current, passed=not failed)
    _output({"type": type_name, "current": current, "next": result}, ctx.obj["human"], ctx.obj["compact"])


@flow_group.command("transition")
@click.argument("task_id", type=int)
@click.argument("to_status")
@click.option("--agent", required=True, help="Agent triggering transition")
@click.pass_context
def transition(ctx: click.Context, task_id: int, to_status: str, agent: str) -> None:
    """Manually transition a task to a new status."""
    from minion.tasks import update_task
    result = update_task(agent, task_id, status=to_status)
    _output(result, ctx.obj["human"], ctx.obj["compact"])


# =========================================================================
# War group
# =========================================================================

@cli.group("war")
@click.pass_context
def war_group(ctx: click.Context) -> None:
    """Session strategy — set objectives and log progress entries."""
    pass


@war_group.command("set-plan")
@click.option("--agent", required=True)
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
@click.option("--agent", required=True)
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
@click.option("--agent", required=True)
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
@click.option("--agent", default="")
@click.pass_context
def list_raid_log(ctx: click.Context, priority: str, count: int, agent: str) -> None:
    """Read the progress log."""
    from minion.warroom import get_raid_log as _get_raid_log
    _output(_get_raid_log(priority, count, agent), ctx.obj["human"])


# =========================================================================
# File group
# =========================================================================

@cli.group("file")
@click.pass_context
def file_group(ctx: click.Context) -> None:
    """Claim files before editing to prevent conflicts between agents."""
    pass


@file_group.command("claim")
@click.option("--agent", required=True)
@click.option("--file", "file_path", required=True)
@click.pass_context
def claim_file(ctx: click.Context, agent: str, file_path: str) -> None:
    """Claim a file for exclusive editing."""
    from minion.auth import require_class
    require_class("lead", "coder", "builder")(lambda: None)()
    from minion.filesafety import claim_file as _claim_file
    _output(_claim_file(agent, file_path), ctx.obj["human"])


@file_group.command("release")
@click.option("--agent", required=True)
@click.option("--file", "file_path", required=True)
@click.option("--force", is_flag=True)
@click.pass_context
def release_file(ctx: click.Context, agent: str, file_path: str, force: bool) -> None:
    """Release a file claim."""
    from minion.auth import require_class
    require_class("lead", "coder", "builder")(lambda: None)()
    from minion.filesafety import release_file as _release_file
    _output(_release_file(agent, file_path, force), ctx.obj["human"])


@file_group.command("list")
@click.option("--agent", default="")
@click.pass_context
def list_claims(ctx: click.Context, agent: str) -> None:
    """List active file claims."""
    from minion.filesafety import get_claims as _get_claims
    _output(_get_claims(agent), ctx.obj["human"])


# =========================================================================
# Crew group
# =========================================================================

@cli.group("crew")
@click.pass_context
def crew_group(ctx: click.Context) -> None:
    """Spawn agent crews from YAML, add/remove agents, check party health."""
    pass


@crew_group.command("list")
@click.pass_context
def list_crews(ctx: click.Context) -> None:
    """List available crews. Lead only."""
    from minion.auth import require_class
    require_class("lead")(lambda: None)()
    from minion.crew import list_crews as _list_crews
    _output(_list_crews(), ctx.obj["human"])


@crew_group.command("spawn")
@click.option("--crew", required=True)
@click.option("--project-dir", default=".")
@click.option("--agents", default="")
@click.option("--runtime", type=click.Choice(["python", "ts"]), default="python",
              help="Daemon runtime: python (minion-swarm) or ts (SDK daemon).")
@click.pass_context
def spawn_party(ctx: click.Context, crew: str, project_dir: str, agents: str, runtime: str) -> None:
    """Launch agents from a crew YAML into tmux panes."""
    from minion.crew import spawn_party as _spawn_party
    # Global -C flag overrides default project-dir
    if project_dir == "." and ctx.obj.get("project_dir"):
        project_dir = ctx.obj["project_dir"]
    _output(_spawn_party(crew, project_dir, agents, runtime=runtime), ctx.obj["human"])


@crew_group.command("stand-down")
@click.option("--agent", required=True)
@click.option("--crew", default="")
@click.pass_context
def stand_down(ctx: click.Context, agent: str, crew: str) -> None:
    """Shut down all agents in a crew. Lead only."""
    from minion.auth import require_class
    require_class("lead")(lambda: None)()
    from minion.crew import stand_down as _stand_down
    _output(_stand_down(agent, crew), ctx.obj["human"])


@crew_group.command("halt")
@click.option("--agent", required=True, help="Lead agent issuing the halt")
@click.pass_context
def halt_cmd(ctx: click.Context, agent: str) -> None:
    """Pause all agents — they finish current work, save state, then stop."""
    from minion.auth import require_class
    require_class("lead")(lambda: None)()
    from minion.lifecycle import halt as _halt
    _output(_halt(agent), ctx.obj["human"])


@crew_group.command("recruit")
@click.option("--name", required=True, help="Agent name")
@click.option("--class", "agent_class", default=None, type=click.Choice(["lead", "coder", "builder", "oracle", "recon", "planner", "auditor"]))
@click.option("--crew", required=True, help="Running crew to join (tmux session crew-<name>)")
@click.option("--from-crew", default="", help="Source crew YAML to pull character config from")
@click.option("--capabilities", default="", help="Comma-separated capabilities (code,review,...)")
@click.option("--system", default="", help="System prompt override")
@click.option("--provider", default=None, type=click.Choice(["claude", "codex", "opencode", "gemini"]))
@click.option("--model", default="", help="Model override")
@click.option("--transport", default=None, type=click.Choice(["terminal", "daemon", "daemon-ts"]))
@click.option("--permission-mode", default="", help="Permission mode for the agent")
@click.option("--zone", default="", help="Zone assignment")
@click.option("--runtime", type=click.Choice(["python", "ts"]), default="python",
              help="Daemon runtime: python or ts.")
@click.pass_context
def recruit(ctx: click.Context, name: str, agent_class: str, crew: str,
            from_crew: str, capabilities: str, system: str, provider: str,
            model: str, transport: str, permission_mode: str, zone: str,
            runtime: str) -> None:
    """Add an ad-hoc agent into a running crew. Lead only."""
    from minion.auth import require_class
    require_class("lead")(lambda: None)()
    # --from-crew or --class is required
    if not from_crew and not agent_class:
        click.echo("BLOCKED: Provide --from-crew or --class.", err=True)
        raise SystemExit(1)
    from minion.crew import recruit_agent as _recruit
    project_dir = ctx.obj.get("project_dir") or "."
    _output(_recruit(
        name=name,
        agent_class=agent_class or "coder",
        crew=crew,
        from_crew=from_crew,
        capabilities=capabilities,
        system=system,
        provider=provider or "claude",
        model=model,
        transport=transport or "daemon",
        permission_mode=permission_mode,
        zone=zone,
        runtime=runtime,
        project_dir=project_dir,
    ), ctx.obj["human"], ctx.obj["compact"])


@crew_group.command("hand-off-zone")
@click.option("--from", "from_agent", required=True)
@click.option("--to", "to_agents", required=True, help="Comma-separated agent names")
@click.option("--zone", required=True)
@click.pass_context
def hand_off_zone(ctx: click.Context, from_agent: str, to_agents: str, zone: str) -> None:
    """Transfer file zone ownership from one agent to another."""
    from minion.crew import hand_off_zone as _hand_off
    _output(_hand_off(from_agent, to_agents, zone), ctx.obj["human"])


@crew_group.command("status")
@click.pass_context
def party_status_cmd(ctx: click.Context) -> None:
    """Show crew health — agent status, token usage, active tasks. Lead only."""
    from minion.auth import require_class
    require_class("lead")(lambda: None)()
    from minion.monitoring import party_status
    _output(party_status(), ctx.obj["human"])


# =========================================================================
# Trigger group
# =========================================================================

@cli.group("trigger")
@click.pass_context
def trigger_group(ctx: click.Context) -> None:
    """Manage trigger words that flag messages for special handling."""
    pass


@trigger_group.command("list")
@click.pass_context
def list_triggers(ctx: click.Context) -> None:
    """Return the trigger word codebook."""
    from minion.triggers import get_triggers as _get_triggers
    _output(_get_triggers(), ctx.obj["human"])


@trigger_group.command("clear-moon-crash")
@click.option("--agent", required=True)
@click.pass_context
def clear_moon_crash(ctx: click.Context, agent: str) -> None:
    """Clear the emergency stop flag. Lead only."""
    from minion.auth import require_class
    require_class("lead")(lambda: None)()
    from minion.triggers import clear_moon_crash as _clear
    _output(_clear(agent), ctx.obj["human"])


# =========================================================================
# Daemon group
# =========================================================================

@cli.group("daemon")
@click.pass_context
def daemon_group(ctx: click.Context) -> None:
    """Start, stop, and tail logs for individual daemon agents."""
    pass


@daemon_group.command("run", hidden=True)
@click.option("--config", required=True, help="Path to crew YAML config")
@click.option("--agent", required=True, help="Agent name to run")
def daemon_run(config: str, agent: str) -> None:
    """Run a single agent daemon (internal — called by spawn-party)."""
    from minion.daemon.config import load_config
    from minion.daemon.runner import AgentDaemon
    cfg = load_config(config)
    daemon = AgentDaemon(cfg, agent)
    daemon.run()


@daemon_group.command("start")
@click.argument("agent")
@click.option("--crew", required=True, help="Crew YAML name (e.g. ff1)")
@click.option("--project-dir", default=".", help="Project directory")
@click.pass_context
def start_agent(ctx: click.Context, agent: str, crew: str, project_dir: str) -> None:
    """Start a single daemon agent from a crew."""
    from minion.crew.spawn import spawn_party
    result = spawn_party(crew, project_dir, agents=agent, runtime="python")
    _output(result, ctx.obj["human"], ctx.obj["compact"])


@daemon_group.command("stop")
@click.argument("agent")
@click.pass_context
def stop_agent(ctx: click.Context, agent: str) -> None:
    """Stop a single daemon agent (SIGTERM → SIGKILL)."""
    from minion.crew.lifecycle import stop_agent_process
    _output(stop_agent_process(agent), ctx.obj["human"], ctx.obj["compact"])


@daemon_group.command("logs")
@click.argument("agent")
@click.option("--lines", default=80, type=int)
@click.option("--follow/--no-follow", default=False)
def logs_agent(agent: str, lines: int, follow: bool) -> None:
    """Show (and optionally follow) one agent's log."""
    from minion.crew.logs import tail_agent_log
    tail_agent_log(agent, lines, follow)


# =========================================================================
# Missions (already grouped — unchanged)
# =========================================================================

@cli.group("mission")
@click.pass_context
def mission_group(ctx: click.Context) -> None:
    """Compose a crew from a mission description. AI suggests roles and skills."""
    pass


@mission_group.command("list")
@click.pass_context
def mission_list(ctx: click.Context) -> None:
    """List available mission templates."""
    from minion.missions import list_missions, load_mission
    names = list_missions()
    missions = []
    for name in names:
        try:
            m = load_mission(name)
            missions.append({"name": m.name, "description": m.description, "requires": m.requires})
        except Exception as exc:
            missions.append({"name": name, "error": f"parse failed: {exc}"})
    _output({"missions": missions}, ctx.obj["human"], ctx.obj["compact"])


@mission_group.command("suggest")
@click.argument("mission_type")
@click.option("--crew", default="", help="Comma-separated crew names to filter characters")
@click.option("--project-dir", default=".", help="Project directory for crew scanning")
@click.pass_context
def mission_suggest(ctx: click.Context, mission_type: str, crew: str, project_dir: str) -> None:
    """Show required capabilities, resolved slots, and eligible characters."""
    from minion.missions import load_mission, resolve_slots, suggest_party
    try:
        mission = load_mission(mission_type)
    except FileNotFoundError as e:
        _output({"error": str(e)})
        return
    slots = resolve_slots(set(mission.requires))
    crews = [c.strip() for c in crew.split(",") if c.strip()] or None
    party = suggest_party(slots, crews=crews, project_dir=project_dir)
    _output({
        "mission": mission.name,
        "description": mission.description,
        "requires": mission.requires,
        "slots": slots,
        "eligible": {slot: chars for slot, chars in party.items()},
    }, ctx.obj["human"], ctx.obj["compact"])


@mission_group.command("spawn")
@click.argument("mission_type")
@click.option("--party", "party_str", default="", help="Comma-separated character names to spawn")
@click.option("--crew", default="", help="Comma-separated crew names to filter characters")
@click.option("--project-dir", default=".", help="Project directory")
@click.option("--runtime", type=click.Choice(["python", "ts"]), default="python",
              help="Daemon runtime: python or ts.")
@click.pass_context
def mission_spawn(ctx: click.Context, mission_type: str, party_str: str, crew: str, project_dir: str, runtime: str) -> None:
    """Resolve mission slots, suggest party, and spawn."""
    from minion.missions import resolve_and_spawn
    try:
        result = resolve_and_spawn(mission_type, party_str, crew, project_dir, runtime)
    except FileNotFoundError as e:
        _output({"error": str(e)})
        return
    _output(result, ctx.obj["human"], ctx.obj["compact"])


# =========================================================================
# Backlog group
# =========================================================================

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
@click.pass_context
def backlog_add(ctx: click.Context, item_type: str, title: str, source: str, description: str, priority: str) -> None:
    """Add a new item to the backlog."""
    import json
    from minion.backlog import add as _add
    try:
        result = _add(item_type, title, source, description, priority)
    except ValueError as e:
        click.echo(json.dumps({"error": str(e)}, indent=2))
        sys.exit(1)
    click.echo(json.dumps(result, indent=2))


@backlog_group.command("list")
@click.option("--type", "item_type", default=None, type=click.Choice(["idea", "bug", "request", "smell", "debt"]))
@click.option("--priority", default=None, type=click.Choice(["unset", "low", "medium", "high", "critical"]))
@click.option("--status", default="open", type=click.Choice(["open", "promoted", "killed", "deferred"]))
@click.pass_context
def backlog_list(ctx: click.Context, item_type: str | None, priority: str | None, status: str | None) -> None:
    """List backlog items with optional filters."""
    import json
    from minion.backlog import list_items as _list_items
    try:
        result = _list_items(item_type, priority, status)
    except ValueError as e:
        click.echo(json.dumps({"error": str(e)}, indent=2))
        sys.exit(1)
    click.echo(json.dumps(result, indent=2))


@backlog_group.command("show")
@click.argument("path", required=False, default=None)
@click.option("--id", "item_id", type=int, default=None, help="Look up by backlog ID")
@click.pass_context
def backlog_show(ctx: click.Context, path: str | None, item_id: int | None) -> None:
    """Show a single backlog item by file path or --id."""
    import json
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
        click.echo(json.dumps({"error": f"Backlog item not found."}, indent=2))
        sys.exit(1)
    click.echo(json.dumps(result, indent=2))


@backlog_group.command("update")
@click.argument("path")
@click.option("--priority", default=None, type=click.Choice(["unset", "low", "medium", "high", "critical"]))
@click.option("--status", default=None, type=click.Choice(["open", "promoted", "killed", "deferred"]))
@click.pass_context
def backlog_update(ctx: click.Context, path: str, priority: str | None, status: str | None) -> None:
    """Update priority and/or status of a backlog item."""
    import json
    from minion.backlog import update_item as _update_item
    try:
        result = _update_item(path, priority, status)
    except ValueError as e:
        click.echo(json.dumps({"error": str(e)}, indent=2))
        sys.exit(1)
    click.echo(json.dumps(result, indent=2))


@backlog_group.command("promote")
@click.argument("path")
@click.option("--origin", default=None, type=click.Choice(["bug", "feature"]), help="Requirement origin override")
@click.option("--slug", default=None, help="Override the auto-derived requirement slug")
@click.option("--flow", default="requirement", type=click.Choice(["requirement", "requirement-lite"]),
              help="Lifecycle flow: 'requirement' (full 9-stage, default) or 'requirement-lite' (4-stage shortcut)")
@click.pass_context
def backlog_promote(ctx: click.Context, path: str, origin: str | None, slug: str | None, flow: str) -> None:
    """Promote a backlog item into the requirement pipeline."""
    import json
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
    import json
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
    import json
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
    import json
    from minion.backlog import reindex as _reindex
    try:
        result = _reindex()
    except ValueError as e:
        click.echo(json.dumps({"error": str(e)}, indent=2))
        sys.exit(1)
    click.echo(json.dumps(result, indent=2))


# =========================================================================
# Requirements (already grouped — unchanged)
# =========================================================================

@cli.group("req")
@click.pass_context
def req_group(ctx: click.Context) -> None:
    """Track requirements through the decomposition pipeline — seed to completed."""
    pass


@req_group.command("register")
@click.option("--path", required=True, help="Path relative to .work/requirements/")
@click.option("--by", "created_by", default="human", help="Who is registering (agent name or 'human')")
@click.pass_context
def req_register(ctx: click.Context, path: str, created_by: str) -> None:
    """Register a requirement folder in the index."""
    from minion.requirements import register as _register
    _output(_register(path, created_by), ctx.obj["human"], ctx.obj["compact"])


@req_group.command("reindex")
@click.option("--work-dir", default="", help="Path to .work/ directory (default: cwd/.work or -C project-dir/.work)")
@click.pass_context
def req_reindex(ctx: click.Context, work_dir: str) -> None:
    """Rebuild the requirements index by scanning the filesystem."""
    from minion.defaults import resolve_work_dir
    from minion.requirements import reindex as _reindex
    if work_dir:
        wd = work_dir
    else:
        # Prefer the project dir set by -C flag over raw cwd
        project_dir = ctx.obj.get("project_dir")
        wd = str(resolve_work_dir(project_dir))
    _output(_reindex(wd), ctx.obj["human"], ctx.obj["compact"])


@req_group.command("list")
@click.option("--stage", default=None, type=click.Choice(["seed", "itemizing", "itemized", "investigating", "findings_ready", "decomposing", "tasked", "in_progress", "completed"]))
@click.option("--origin", default="", help="Filter by origin (feature, bug, ...)")
@click.pass_context
def req_list(ctx: click.Context, stage: str, origin: str) -> None:
    """List all requirements with optional filters."""
    from minion.requirements import list_requirements as _list
    _output(_list(stage, origin), ctx.obj["human"], ctx.obj["compact"])


@req_group.command("tree")
@click.argument("path")
@click.pass_context
def req_tree(ctx: click.Context, path: str) -> None:
    """Show the decomposition tree rooted at PATH."""
    from minion.requirements import get_tree as _tree
    _output(_tree(path), ctx.obj["human"], ctx.obj["compact"])


@req_group.command("status")
@click.argument("path")
@click.pass_context
def req_status(ctx: click.Context, path: str) -> None:
    """Show a requirement, its linked tasks, and completion percentage."""
    from minion.requirements import get_status as _status
    _output(_status(path), ctx.obj["human"], ctx.obj["compact"])


@req_group.command("update")
@click.option("--path", required=True, help="Requirement path relative to .work/requirements/")
@click.option("--stage", required=True, type=click.Choice(["seed", "itemizing", "itemized", "investigating", "findings_ready", "decomposing", "tasked", "in_progress", "completed"]))
@click.option("--skip", "skip_stages", is_flag=True, default=False, help="Walk through all intermediate stages to reach target (lead only).")
@click.option("--agent", default="", help="Caller agent name; must be 'lead' to use --skip.")
@click.pass_context
def req_update(ctx: click.Context, path: str, stage: str, skip_stages: bool, agent: str) -> None:
    """Advance a requirement's stage. Use --skip --agent lead to jump multiple stages at once."""
    from minion.requirements import update_stage as _update
    _output(_update(path, stage, skip=skip_stages, agent=agent), ctx.obj["human"], ctx.obj["compact"])


@req_group.command("link")
@click.option("--task", "task_id", required=True, type=int, help="Task ID to link")
@click.option("--path", required=True, help="Requirement path relative to .work/requirements/")
@click.pass_context
def req_link(ctx: click.Context, task_id: int, path: str) -> None:
    """Link a task to its source requirement."""
    from minion.requirements import link_task as _link
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
@click.option("--path", required=True, help="Path relative to .work/requirements/")
@click.option("--title", required=True, help="Requirement title")
@click.option("--description", default="", help="Requirement description")
@click.option("--by", "created_by", default="human")
@click.pass_context
def req_create(ctx: click.Context, path: str, title: str, description: str, created_by: str) -> None:
    """Create a requirement folder with README and register it."""
    from minion.requirements import create as _create
    _output(_create(path, title, description, created_by), ctx.obj["human"], ctx.obj["compact"])


@req_group.command("decompose")
@click.option("--path", required=True, help="Parent requirement path")
@click.option("--spec", default=None, help="YAML spec file for children. Use '-' to read from stdin.")
@click.option("--inline", default=None, help="Inline YAML string (alternative to --spec file).")
@click.option("--by", "agent_name", default="lead")
@click.pass_context
def req_decompose(ctx: click.Context, path: str, spec: str | None, inline: str | None, agent_name: str) -> None:
    """Decompose a requirement into children from a spec file or inline YAML.

    Accepts a spec in three ways:
      --spec <file>       YAML file on disk
      --spec -            Read YAML from stdin
      --inline '<yaml>'   Pass YAML directly as a string argument
    """
    import sys
    import yaml as _yaml
    from minion.requirements.decompose import decompose as _decompose, _load_spec

    if inline is not None:
        # Parse the inline YAML string directly — no filesystem read
        try:
            spec_data = _yaml.safe_load(inline)
        except _yaml.YAMLError as exc:
            _output({"error": f"Invalid inline YAML: {exc}"}, ctx.obj["human"], ctx.obj["compact"])
            ctx.exit(1)
            return
        if not isinstance(spec_data, dict) or "children" not in spec_data:
            _output({"error": "Inline YAML must contain a 'children' key."}, ctx.obj["human"], ctx.obj["compact"])
            ctx.exit(1)
            return
    elif spec == "-":
        # Read spec YAML from stdin
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

    _output(_decompose(path, spec_data, agent_name), ctx.obj["human"], ctx.obj["compact"])


@req_group.command("itemize")
@click.option("--path", required=True, help="Requirement path")
@click.option("--spec", required=True, type=click.Path(exists=True), help="YAML spec file with items")
@click.option("--by", "created_by", default="lead")
@click.pass_context
def req_itemize(ctx: click.Context, path: str, spec: str, created_by: str) -> None:
    """Write itemized-requirements.md from a spec file."""
    import yaml
    with open(spec) as f:
        spec_data = yaml.safe_load(f)
    from minion.requirements import itemize as _itemize
    _output(_itemize(path, spec_data, created_by), ctx.obj["human"], ctx.obj["compact"])


@req_group.command("findings")
@click.option("--path", required=True, help="Requirement path")
@click.option("--spec", required=True, type=click.Path(exists=True), help="YAML spec file with findings")
@click.option("--by", "created_by", default="lead")
@click.pass_context
def req_findings(ctx: click.Context, path: str, spec: str, created_by: str) -> None:
    """Write findings.md from a spec file."""
    import yaml
    with open(spec) as f:
        spec_data = yaml.safe_load(f)
    from minion.requirements import findings as _findings
    _output(_findings(path, spec_data, created_by), ctx.obj["human"], ctx.obj["compact"])


# =========================================================================
# Top-level commands (stay ungrouped)
# =========================================================================

@cli.command()
@click.option("--agent", required=True)
@click.option("--interval", default=5, type=int, help="Poll interval in seconds")
@click.option("--timeout", default=0, type=int, help="Timeout in seconds (0 = forever)")
@click.pass_context
def poll(ctx: click.Context, agent: str, interval: int, timeout: int) -> None:
    """Poll for messages and tasks. Returns content when available."""
    from minion.polling import poll_loop
    result = poll_loop(agent, interval, timeout)
    exit_code = result.pop("exit_code", 1)
    if result:
        _output(result, ctx.obj["human"])
    sys.exit(exit_code)


@cli.command()
@click.pass_context
def sitrep(ctx: click.Context) -> None:
    """Fused COP: agents + tasks + zones + claims + flags + recent comms."""
    from minion.monitoring import sitrep as _sitrep
    _output(_sitrep(), ctx.obj["human"])


@cli.command("install-docs")
@click.pass_context
def install_docs(ctx: click.Context) -> None:
    """Copy protocol + contract docs to ~/.minion_work/docs/."""
    from minion.crew.spawn import install_docs as _install_docs
    _output(_install_docs(), ctx.obj["human"])


@cli.command("dashboard")
@click.pass_context
def dashboard_cmd(ctx: click.Context) -> None:
    """Live task board. Run in a tmux pane — no DB registration."""
    from minion.dashboard import run
    run()


@cli.command("end-session")
@click.option("--agent", required=True)
@click.pass_context
def end_session(ctx: click.Context, agent: str) -> None:
    """End the current session. Lead only."""
    from minion.auth import require_class
    require_class("lead")(lambda: None)()
    from minion.lifecycle import end_session as _end_session
    _output(_end_session(agent), ctx.obj["human"])


@cli.command()
@click.option("--class", "agent_class", default="", help="Class to list tools for (default: MINION_CLASS env)")
@click.pass_context
def tools(ctx: click.Context, agent_class: str) -> None:
    """List available tools for your class."""
    from minion.auth import get_agent_class, get_tools_for_class
    from minion.db import DOCS_DIR
    cls = agent_class or get_agent_class()
    docs_dir = DOCS_DIR
    protocol_file = f"protocol-{cls}.md"
    result: dict[str, object] = {
        "class": cls,
        "tools": get_tools_for_class(cls),
        "protocol_doc": os.path.join(docs_dir, protocol_file) if os.path.isfile(os.path.join(docs_dir, protocol_file)) else None,
    }
    _output(result, ctx.obj["human"], ctx.obj["compact"])


@cli.command()
@click.option("--agent", required=True)
@click.option("--debrief-file", required=True)
@click.pass_context
def debrief(ctx: click.Context, agent: str, debrief_file: str) -> None:
    """File a session debrief. Lead only."""
    from minion.auth import require_class
    require_class("lead")(lambda: None)()
    from minion.lifecycle import debrief as _debrief
    _output(_debrief(agent, debrief_file), ctx.obj["human"])


@cli.command()
@click.option("--name", required=True)
@click.pass_context
def deregister(ctx: click.Context, name: str) -> None:
    """Remove an agent from the registry."""
    from minion.comms import deregister as _deregister
    _output(_deregister(name), ctx.obj["human"])


@cli.command()
@click.option("--old", required=True)
@click.option("--new", required=True)
@click.pass_context
def rename(ctx: click.Context, old: str, new: str) -> None:
    """Rename an agent. Lead only."""
    from minion.auth import require_class
    require_class("lead")(lambda: None)()
    from minion.comms import rename as _rename
    _output(_rename(old, new), ctx.obj["human"])


@cli.command()
@click.option("--agent", required=True, help="Agent to interrupt")
@click.option("--requesting-agent", required=True, help="Lead requesting interrupt")
@click.pass_context
def interrupt(ctx: click.Context, agent: str, requesting_agent: str) -> None:
    """Interrupt an agent's current invocation. Lead only."""
    from minion.auth import require_class
    require_class("lead")(lambda: None)()
    from minion.crew import interrupt_agent as _interrupt
    _output(_interrupt(agent, requesting_agent), ctx.obj["human"])


@cli.command()
@click.option("--agent", required=True, help="Agent to resume")
@click.option("--message", required=True, help="Message to send on resume")
@click.option("--from", "from_agent", required=True, help="Sending agent (lead)")
@click.pass_context
def resume(ctx: click.Context, agent: str, message: str, from_agent: str) -> None:
    """Send a resume message to an interrupted agent. Lead only."""
    from minion.auth import require_class
    require_class("lead")(lambda: None)()
    from minion.comms import send as _send
    _output(_send(from_agent, agent, message), ctx.obj["human"])


# =========================================================================
# Docs command — auto-generated CLI reference
# =========================================================================

@cli.command("docs")
@click.option("--format", "fmt", type=click.Choice(["markdown", "json"]), default="markdown",
              help="Output format")
@click.option("--output", "-o", "output_dir", default=None, type=click.Path(),
              help="Write cli-reference.md to this directory")
def docs_cmd(fmt: str, output_dir: str | None) -> None:
    """Generate CLI reference from Click introspection."""
    from minion.cli_schema import generate_cli_schema, schema_to_json, schema_to_markdown

    schema = generate_cli_schema(cli)
    if fmt == "json":
        click.echo(schema_to_json(schema))
    elif output_dir:
        import os
        content = schema_to_markdown(schema)
        path = os.path.join(output_dir, "cli-reference.md")
        os.makedirs(output_dir, exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        click.echo(f"Wrote {path}")
    else:
        click.echo(schema_to_markdown(schema))


# =========================================================================
# Hidden aliases — backwards compat for all old flat command names
# =========================================================================

# Agent group aliases
cli.add_command(register, "register")
cli.add_command(set_status, "set-status")
cli.add_command(set_context, "set-context")
cli.add_command(who, "who")
cli.add_command(update_hp, "update-hp")
cli.add_command(cold_start, "cold-start")
cli.add_command(fenix_down, "fenix-down")
cli.add_command(retire_agent_cmd, "retire-agent")
cli.add_command(check_activity, "check-activity")
cli.add_command(check_freshness, "check-freshness")

# Comms group aliases
cli.add_command(send, "send")
cli.add_command(check_inbox, "check-inbox")
cli.add_command(purge_inbox, "purge-inbox")
cli.add_command(list_history, "list-history")

# Task group aliases
cli.add_command(create_task, "create-task")
cli.add_command(assign_task, "assign-task")
cli.add_command(update_task, "update-task")
cli.add_command(list_tasks, "list-tasks")
cli.add_command(get_task, "get-task")
cli.add_command(task_lineage, "task-lineage")
cli.add_command(submit_result, "submit-result")
cli.add_command(close_task, "close-task")
cli.add_command(reopen_task_cmd, "reopen-task")
cli.add_command(pull_task_cmd, "pull-task")
cli.add_command(complete_phase_cmd, "complete-phase")
cli.add_command(check_work_cmd, "check-work")

# Flow group aliases
cli.add_command(list_flows_cmd, "list-flows")
cli.add_command(show_flow, "show-flow")
cli.add_command(next_status, "next-status")
cli.add_command(transition, "transition")

# War group aliases
cli.add_command(set_battle_plan, "set-battle-plan")
cli.add_command(get_battle_plan, "get-battle-plan")
cli.add_command(update_battle_plan_status, "update-battle-plan-status")
cli.add_command(log_raid, "log-raid")
cli.add_command(list_raid_log, "list-raid-log")

# File group aliases
cli.add_command(claim_file, "claim-file")
cli.add_command(release_file, "release-file")
cli.add_command(list_claims, "list-claims")

# Crew group aliases
cli.add_command(list_crews, "list-crews")
cli.add_command(spawn_party, "spawn-party")
cli.add_command(stand_down, "stand-down")
cli.add_command(halt_cmd, "halt")
cli.add_command(recruit, "recruit")
cli.add_command(hand_off_zone, "hand-off-zone")
cli.add_command(party_status_cmd, "party-status")

# Trigger group aliases
cli.add_command(list_triggers, "list-triggers")
cli.add_command(clear_moon_crash, "clear-moon-crash")

# Daemon group aliases
cli.add_command(daemon_run, "daemon-run")
cli.add_command(start_agent, "start")
cli.add_command(stop_agent, "stop")
cli.add_command(logs_agent, "logs")

# Legacy get-* collection name aliases
cli.add_command(list_tasks, "get-tasks")
cli.add_command(list_history, "get-history")
cli.add_command(list_raid_log, "get-raid-log")
cli.add_command(list_claims, "get-claims")
cli.add_command(list_triggers, "get-triggers")

# Hide flat aliases from --help (progressive discovery).
# The same Command object lives in both the group and cli.commands,
# so we can't mutate .hidden — instead, replace with a hidden wrapper.
_GROUP_NAMES = {n for n, c in cli.commands.items() if isinstance(c, click.Group)}
_TOP_LEVEL_ORIGINALS = {
    "poll", "sitrep", "install-docs", "dashboard", "end-session",
    "tools", "debrief", "deregister", "rename", "interrupt", "resume", "docs",
}
for _alias_name in list(cli.commands):
    if _alias_name not in _GROUP_NAMES and _alias_name not in _TOP_LEVEL_ORIGINALS:
        _orig = cli.commands[_alias_name]
        # Wrap: new Command that delegates to the original callback
        _wrapper = click.Command(
            name=_alias_name,
            callback=_orig.callback,
            params=_orig.params,
            help=_orig.help,
            hidden=True,
        )
        cli.add_command(_wrapper, _alias_name)


if __name__ == "__main__":
    cli()
