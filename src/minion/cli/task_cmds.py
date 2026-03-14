"""Task group — create, assign, update, list, get, pull, complete-phase, block, done, result, review, test, spec, lineage, define.
Work item lifecycle: creation through DAG-routed completion.

Purpose: Task group — create, assign, update, list, get, pull, complete-phase, block, done, result, review, test, spec, lineage, define.
Rationale: Extracted into own module for single-responsibility CLI command grouping.
Responsibility: Task group — create, assign, update, list, get, pull, complete-phase, block, done, result, review, test, spec, lineage, define. NOT responsible for unrelated concerns.
Organization: Click command group with subcommands."""

from __future__ import annotations

import sys

import click

from minion.cli.main import _agent_option, _output


def register_commands(cli: click.Group) -> None:
    """Attach the task group and its subcommands to the root CLI."""

    @cli.group("task")
    @click.pass_context
    def task_group(ctx: click.Context) -> None:
        """Create, assign, and update work items. Track progress through the DAG."""
        pass

    @task_group.command("create")
    @_agent_option(required=True)
    @click.option("--title", "-t", required=True)
    @click.option("--task-file", "-f", required=True)
    @click.option("--project", "-p", default="")
    @click.option("--zone", "-z", default="")
    @click.option("--blocked-by", "-b", default="")
    @click.option("--class-required", "-c", default="", help="Agent class required (e.g. coder, builder, recon)")
    @click.option("--type", "-T", "task_type", default="bugfix", type=click.Choice(["bugfix", "build", "chore", "feature", "hotfix", "implementation", "investigation", "requirement", "research"]))
    @click.option("--requirement", "-r", "requirement_id", default=None, type=int, help="Link to requirement ID for lineage tracking")
    @click.pass_context
    def create_task(ctx: click.Context, agent: str, title: str, task_file: str, project: str, zone: str, blocked_by: str, class_required: str, task_type: str, requirement_id: int | None) -> None:
        """Create a new task. Lead only."""
        from minion.auth import require_class
        require_class("lead")(lambda: None)()
        from minion.tasks import create_task as _create_task
        _output(_create_task(agent, title, task_file, project, zone, blocked_by, class_required, task_type, requirement_id=requirement_id), ctx.obj["human"])

    @task_group.command("assign")
    @_agent_option(required=True)
    @click.option("--task-id", "-t", required=True, type=int)
    @click.option("--assigned-to", "-A", required=True)
    @click.pass_context
    def assign_task(ctx: click.Context, agent: str, task_id: int, assigned_to: str) -> None:
        """Assign a task to an agent. Lead only."""
        from minion.auth import require_class
        require_class("lead")(lambda: None)()
        from minion.tasks import assign_task as _assign_task
        _output(_assign_task(agent, task_id, assigned_to), ctx.obj["human"])

    @task_group.command("update")
    @_agent_option(required=True)
    @click.option("--task-id", "-t", required=True, type=int)
    @click.option("--status", "-s", default="")
    @click.option("--progress", "-P", default="")
    @click.option("--files", "-f", default="")
    @click.option("--checklist", "-c", default="", help="Path to checklist file (required for in_progress transition)")
    @click.pass_context
    def update_task(ctx: click.Context, agent: str, task_id: int, status: str, progress: str, files: str, checklist: str) -> None:
        """Update a task's status, progress, or files."""
        from minion.tasks import update_task as _update_task
        _output(_update_task(agent, task_id, status, progress, files, checklist), ctx.obj["human"])

    @task_group.command("list")
    @click.option("--status", "-s", default="")
    @click.option("--project", "-p", default="")
    @click.option("--zone", "-z", default="")
    @click.option("--assigned-to", "-A", default="")
    @click.option("--class-required", "-c", default="", help="Filter by required agent class")
    @click.option("--count", "-n", default=50, type=int)
    @click.pass_context
    def list_tasks(ctx: click.Context, status: str, project: str, zone: str, assigned_to: str, class_required: str, count: int) -> None:
        """List tasks."""
        from minion.tasks import get_tasks as _get_tasks
        _output(_get_tasks(status, project, zone, assigned_to, class_required, count), ctx.obj["human"])

    @task_group.command("show")
    @click.option("--task-id", "-t", required=True, type=int)
    @click.pass_context
    def show_task(ctx: click.Context, task_id: int) -> None:
        """Show full detail for a single task."""
        from minion.tasks import get_task as _get_task
        _output(_get_task(task_id), ctx.obj["human"])

    @task_group.command("get", hidden=True)
    @click.option("--task-id", "-t", required=True, type=int)
    @click.pass_context
    def get_task(ctx: click.Context, task_id: int) -> None:
        """Show full detail for a single task (hidden alias for 'task show')."""
        from minion.tasks import get_task as _get_task
        _output(_get_task(task_id), ctx.obj["human"])

    @task_group.command("spec")
    @click.option("--task-id", "-t", required=True, type=int)
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
    @click.option("--task-id", "-t", required=True, type=int)
    @click.pass_context
    def task_lineage(ctx: click.Context, task_id: int) -> None:
        """Show task lineage — DAG history and who worked each stage."""
        from minion.tasks import get_task_lineage as _get_lineage
        _output(_get_lineage(task_id), ctx.obj["human"])

    @task_group.command("submit-result", hidden=True)
    @_agent_option(required=True)
    @click.option("--task-id", "-t", required=True, type=int)
    @click.option("--result-file", "-r", required=True)
    @click.pass_context
    def submit_result(ctx: click.Context, agent: str, task_id: int, result_file: str) -> None:
        """Submit a result file for a task (hidden — use 'task result' instead)."""
        from minion.tasks import submit_result as _submit_result
        _output(_submit_result(agent, task_id, result_file), ctx.obj["human"])

    @task_group.command("close")
    @_agent_option(required=True)
    @click.option("--task-id", "-t", required=True, type=int)
    @click.pass_context
    def close_task(ctx: click.Context, agent: str, task_id: int) -> None:
        """Close a task. Lead only."""
        from minion.auth import require_class
        require_class("lead")(lambda: None)()
        from minion.tasks import close_task as _close_task
        _output(_close_task(agent, task_id), ctx.obj["human"])

    @task_group.command("done")
    @_agent_option(required=True)
    @click.option("--task-id", "-t", required=True, type=int)
    @click.option("--summary", "-s", default="", help="Optional summary of externally completed work")
    @click.pass_context
    def done_task_cmd(ctx: click.Context, agent: str, task_id: int, summary: str) -> None:
        """Fast-close a task completed outside the DAG. Lead only."""
        from minion.auth import require_class
        require_class("lead")(lambda: None)()
        from minion.tasks import done_task as _done_task
        _output(_done_task(agent, task_id, summary), ctx.obj["human"])

    @task_group.command("reopen")
    @_agent_option(required=True)
    @click.option("--task-id", "-t", required=True, type=int)
    @click.option("--to-status", "-s", default="assigned", help="Target status (default: assigned)")
    @click.pass_context
    def reopen_task_cmd(ctx: click.Context, agent: str, task_id: int, to_status: str) -> None:
        """Reopen a terminal task back to an earlier phase. Lead only."""
        from minion.tasks import reopen_task as _reopen_task
        _output(_reopen_task(agent, task_id, to_status), ctx.obj["human"])

    @task_group.command("pull")
    @_agent_option(required=True)
    @click.option("--task-id", "-t", required=True, type=int)
    @click.pass_context
    def pull_task_cmd(ctx: click.Context, agent: str, task_id: int) -> None:
        """Claim a specific task by ID."""
        from minion.tasks import pull_task as _pull_task
        _output(_pull_task(agent, task_id), ctx.obj["human"])

    @task_group.command("complete-phase")
    @_agent_option(required=True)
    @click.option("--task-id", "-t", required=True, type=int)
    @click.option("--failed", "-F", is_flag=True, help="Mark as failed (routes to fail branch in DAG)")
    @click.option("--reason", "-r", default=None, help="Required when blocking — why you're stuck")
    @click.pass_context
    def complete_phase_cmd(ctx: click.Context, agent: str, task_id: int, failed: bool, reason: str | None) -> None:
        """Complete your phase — DAG routes to next stage."""
        from minion.tasks import complete_phase as _complete_phase
        _output(_complete_phase(agent, task_id, passed=not failed, reason=reason), ctx.obj["human"])

    @task_group.command("check-work")
    @_agent_option(required=True)
    @click.pass_context
    def check_work_cmd(ctx: click.Context, agent: str) -> None:
        """Check if agent has available tasks. Exit 0 = work, 1 = no work."""
        from minion.polling import _find_available_tasks
        tasks = _find_available_tasks(agent)
        _output({"has_work": len(tasks) > 0, "task_count": len(tasks), "tasks": tasks}, ctx.obj["human"])
        sys.exit(0 if tasks else 1)

    @task_group.command("comment")
    @_agent_option(required=True)
    @click.option("--task-id", "-t", required=True, type=int)
    @click.option("--message", "-m", required=True)
    @click.option("--files", "-f", default="", help="Comma-separated file paths read for context")
    @click.pass_context
    def task_comment_cmd(ctx: click.Context, agent: str, task_id: int, message: str, files: str) -> None:
        """Add a comment to a task with optional file context."""
        from minion.tasks.comments import add_comment
        files_list = [f.strip() for f in files.split(",") if f.strip()] if files else None
        _output(add_comment(agent, task_id, message, files_read=files_list), ctx.obj["human"])

    @task_group.command("comments")
    @click.option("--task-id", "-t", required=True, type=int)
    @click.pass_context
    def task_comments_cmd(ctx: click.Context, task_id: int) -> None:
        """List all comments for a task."""
        from minion.tasks.comments import list_comments
        _output(list_comments(task_id), ctx.obj["human"])

    @task_group.command("define")
    @_agent_option(required=True)
    @click.option("--title", "-t", required=True)
    @click.option("--description", "-d", required=True)
    @click.option("--task-type", "-T", "task_type", default=None, type=click.Choice(["bugfix", "build", "chore", "feature", "hotfix", "implementation", "investigation", "requirement", "research"]), help="DAG flow type for this task (alias: --flow)")
    @click.option("--flow", "-F", "flow", default=None, type=click.Choice(["bugfix", "build", "chore", "feature", "hotfix", "implementation", "investigation", "requirement", "research"]), help="DAG flow type for this task (alias: --task-type)")
    @click.option("--project", "-p", default="")
    @click.option("--zone", "-z", default="")
    @click.option("--blocked-by", "-b", default="", help="Comma-separated task IDs")
    @click.option("--class-required", "-c", default="")
    @click.option("--intel", "-i", default="", help="Comma-separated intel slugs to link")
    @click.option("--requirement", "-r", "requirement_id", default=None, type=int, help="Link to requirement ID for lineage tracking (alias: --requirement-id)")
    @click.option("--requirement-id", "requirement_id_alias", default=None, type=int, help="Link to requirement ID for lineage tracking (alias: --requirement)")
    @click.pass_context
    def task_define_cmd(ctx: click.Context, agent: str, title: str, description: str,
                        task_type: str | None, flow: str | None, project: str, zone: str, blocked_by: str, class_required: str, intel: str, requirement_id: int | None, requirement_id_alias: int | None) -> None:
        """Create a task spec file and task record in one command.

        Accepts --task-type or --flow (synonyms). Accepts --requirement or --requirement-id (synonyms).
        """
        # Merge alias pairs — --flow is an alias for --task-type; --requirement-id is an alias for --requirement
        resolved_type = task_type or flow or "feature"
        resolved_req_id = requirement_id if requirement_id is not None else requirement_id_alias
        from minion.tasks.define import define_task
        _output(define_task(agent, title, description, resolved_type, project, zone, blocked_by, class_required, intel, requirement_id=resolved_req_id), ctx.obj["human"])

    @task_group.command("result")
    @_agent_option(required=True)
    @click.option("--task-id", "-t", required=True, type=int)
    @click.option("--summary", "-s", required=True)
    @click.option("--files-changed", "-f", default="", help="Comma-separated list of changed files")
    @click.option("--notes", "-n", default="")
    @click.pass_context
    def task_result_cmd(ctx: click.Context, agent: str, task_id: int, summary: str,
                        files_changed: str, notes: str) -> None:
        """Write a result file and submit it for a task."""
        from minion.tasks.result import create_result
        _output(create_result(agent, task_id, summary, files_changed, notes), ctx.obj["human"])

    @task_group.command("review")
    @_agent_option(required=True)
    @click.option("--task-id", "-t", required=True, type=int)
    @click.option("--verdict", "-v", required=True, type=click.Choice(["pass", "fail"]))
    @click.option("--notes", "-n", default="")
    @click.pass_context
    def task_review_cmd(ctx: click.Context, agent: str, task_id: int, verdict: str, notes: str) -> None:
        """Write a review verdict and advance the task phase."""
        from minion.tasks.review import create_review
        _output(create_review(agent, task_id, verdict, notes), ctx.obj["human"])

    @task_group.command("test")
    @_agent_option(required=True)
    @click.option("--task-id", "-t", required=True, type=int)
    @click.option("--passed/--failed", required=True, help="Test outcome")
    @click.option("--output", "-o", "test_output", default="", help="Test output text")
    @click.option("--notes", "-n", default="")
    @click.pass_context
    def task_test_cmd(ctx: click.Context, agent: str, task_id: int, passed: bool,
                      test_output: str, notes: str) -> None:
        """Write a test report and advance the task phase."""
        from minion.tasks.test_report import create_test_report
        _output(create_test_report(agent, task_id, passed, test_output, notes), ctx.obj["human"])

    @task_group.command("block")
    @_agent_option(required=True)
    @click.option("--task-id", "-t", required=True, type=int)
    @click.option("--reason", "-r", required=True)
    @click.pass_context
    def task_block_cmd(ctx: click.Context, agent: str, task_id: int, reason: str) -> None:
        """Block a task with a reason and transition to blocked status."""
        from minion.tasks.block import block_task
        _output(block_task(agent, task_id, reason), ctx.obj["human"])

    @task_group.command("order")
    @_agent_option(required=True)
    @click.option("--task-id", "-t", required=True, type=int)
    @click.option("--worker", "-w", required=True, help="Worker agent name")
    @click.option("--files", "-f", default="", help="Comma-separated files to modify")
    @click.option("--fix", "-d", default="", help="Exact fix description")
    @click.option("--test-cmd", "-T", default="", help="Exact test command (default: uv run pytest)")
    @click.option("--commit-msg", "-m", default="", help="Exact commit message format")
    @click.pass_context
    def task_order_cmd(ctx: click.Context, agent: str, task_id: int, worker: str,
                       files: str, fix: str, test_cmd: str, commit_msg: str) -> None:
        """Generate a deterministic work order file for a worker. Lead only."""
        from minion.auth import require_class
        require_class("lead")(lambda: None)()
        from minion.tasks.work_order import generate_work_order
        _output(generate_work_order(agent, task_id, worker, files, fix, test_cmd, commit_msg), ctx.obj["human"])
