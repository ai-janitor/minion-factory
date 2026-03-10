"""Crew group — list, spawn, stand-down, halt, recruit, hand-off-zone, status.
Spawn agent crews from YAML, manage party health, and coordinate handoffs.

Purpose: Crew group — list, spawn, stand-down, halt, recruit, hand-off-zone, status.
Rationale: Extracted into own module for single-responsibility CLI command grouping.
Responsibility: Crew group — list, spawn, stand-down, halt, recruit, hand-off-zone, status. NOT responsible for unrelated concerns.
Organization: Click command group with subcommands."""

from __future__ import annotations

import click

from minion.cli.main import _agent_option, _output


def register_commands(cli: click.Group) -> None:
    """Attach the crew group and its subcommands to the root CLI."""

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
    @_agent_option(required=True)
    @click.option("--crew", default="")
    @click.pass_context
    def stand_down(ctx: click.Context, agent: str, crew: str) -> None:
        """Shut down all agents in a crew. Lead only."""
        from minion.auth import require_class
        require_class("lead")(lambda: None)()
        from minion.crew import stand_down as _stand_down
        _output(_stand_down(agent, crew), ctx.obj["human"])

    @crew_group.command("halt")
    @_agent_option(required=True, help="Lead agent issuing the halt")
    @click.pass_context
    def halt_cmd(ctx: click.Context, agent: str) -> None:
        """Pause all agents — they finish current work, save state, then stop."""
        from minion.auth import require_class
        require_class("lead")(lambda: None)()
        from minion.lifecycle import halt as _halt
        _output(_halt(agent), ctx.obj["human"])

    @crew_group.command("recruit")
    @click.option("--name", "-n", required=True, help="Agent name")
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
            raise SystemExit(2)
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
