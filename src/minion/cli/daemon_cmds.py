"""Daemon group — run, start, stop, logs.
Start, stop, and tail logs for individual daemon agents.

Purpose: Daemon group — run, start, stop, logs.
Rationale: Extracted into own module for single-responsibility CLI command grouping.
Responsibility: Daemon group — run, start, stop, logs. NOT responsible for unrelated concerns.
Organization: Click command group with subcommands."""

from __future__ import annotations

import click

from minion.cli.main import _agent_option, _output


def register_commands(cli: click.Group) -> None:
    """Attach the daemon group and its subcommands to the root CLI."""

    @cli.group("daemon")
    @click.pass_context
    def daemon_group(ctx: click.Context) -> None:
        """Start, stop, and tail logs for individual daemon agents."""
        pass

    @daemon_group.command("run", hidden=True)
    @click.option("--config", "-c", required=True, help="Path to crew YAML config")
    @_agent_option(required=True, help="Agent name to run")
    @click.option("--instance-id", default=None, help="Instance suffix for multi-instance spawns")
    def daemon_run(config: str, agent: str, instance_id: str | None) -> None:
        """Run a single agent daemon (internal — called by spawn-party)."""
        from minion.daemon.config import load_config
        from minion.daemon.runner import AgentDaemon
        cfg = load_config(config)
        daemon = AgentDaemon(cfg, agent, instance_id=instance_id)
        daemon.run()

    @daemon_group.command("start")
    @click.argument("agent")
    @click.option("--crew", "-c", required=True, help="Crew YAML name (e.g. ff1)")
    @click.option("--project-dir", "-d", default=".", help="Project directory")
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
    @click.option("--lines", "-n", default=80, type=int)
    @click.option("--follow/--no-follow", "-f/", default=False)
    def logs_agent(agent: str, lines: int, follow: bool) -> None:
        """Show (and optionally follow) one agent's log."""
        from minion.crew.logs import tail_agent_log
        tail_agent_log(agent, lines, follow)
