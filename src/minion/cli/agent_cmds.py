"""Agent group — register, deregister, rename, set-context, set-status, who, cold-start.
Identity and lifecycle management for individual agents.

Purpose: Agent group — register, deregister, rename, set-context, set-status, who, cold-start.
Rationale: Extracted into own module for single-responsibility CLI command grouping.
Responsibility: Agent group — register, deregister, rename, set-context, set-status, who, cold-start. NOT responsible for unrelated concerns.
Organization: Click command group with subcommands."""

from __future__ import annotations

import click

from minion.cli.main import _agent_option, _output


def register_commands(cli: click.Group) -> None:
    """Attach the agent group and its subcommands to the root CLI."""

    @cli.group("agent")
    @click.pass_context
    def agent_group(ctx: click.Context) -> None:
        """Join the session, report your state, and manage your identity."""
        pass

    @agent_group.command("register")
    @click.option("--name", "-n", required=True)
    @click.option("--class", "-c", "agent_class", required=True, type=click.Choice(["lead", "coder", "builder", "oracle", "recon", "planner", "auditor", "coordinator"]))
    @click.option("--model", "-M", default="")
    @click.option("--description", "-d", default="")
    @click.option("--transport", "-T", default="terminal", type=click.Choice(["terminal", "daemon", "daemon-ts"]))
    @click.option("--crew", "-w", default="", help="Crew YAML name — injects zone, capabilities, system prompt excerpt")
    @click.option("--scope", "-S", default="project", type=click.Choice(["project", "sys", "cross-repo"]), help="Permission scope — narrows what commands are allowed")
    @click.pass_context
    def register(ctx: click.Context, name: str, agent_class: str, model: str, description: str, transport: str, crew: str, scope: str) -> None:
        """Register an agent into the local session AND the global coordinator DB.

        After registering, you MUST start polling to receive messages:
        minion poll --agent <name>

        An agent that registers but doesn't poll is deaf — it cannot receive
        messages or task assignments. Names must be unique across all projects."""
        from minion.comms import register as _register
        _output(_register(name, agent_class, model, description, transport, crew, scope), ctx.obj["human"], ctx.obj["compact"])

    @agent_group.command("set-status")
    @_agent_option(required=True)
    @click.option("--status", "-s", required=True)
    @click.pass_context
    def set_status(ctx: click.Context, agent: str, status: str) -> None:
        """Set agent status."""
        from minion.comms import set_status as _set_status
        _output(_set_status(agent, status), ctx.obj["human"])

    @agent_group.command("set-context")
    @_agent_option(required=True)
    @click.option("--context", "-x", required=True)
    @click.option("--tokens-used", "-u", default=0, type=int)
    @click.option("--tokens-limit", "-l", default=0, type=int)
    @click.option("--hp", "-H", default=None, type=int, help="Self-reported HP 0-100 (skips daemon token counting)")
    @click.option("--files-modified", "-F", default="", help="Comma-separated files modified this turn; warns if unclaimed")
    @click.pass_context
    def set_context(ctx: click.Context, agent: str, context: str, tokens_used: int, tokens_limit: int, hp: int | None, files_modified: str) -> None:
        """Update context summary and health (tokens used, token limit)."""
        from minion.comms import set_context as _set_context
        _output(_set_context(agent, context, tokens_used, tokens_limit, hp, files_modified), ctx.obj["human"])

    @agent_group.command("who")
    @click.option("--global", "-g", "use_global", is_flag=True, default=False,
                  help="Query the global coordinator DB (~/.minion/coordinator.db) to show agents across ALL projects, not just the current repo")
    @click.pass_context
    def who(ctx: click.Context, use_global: bool) -> None:
        """List registered agents in THIS repo. Use --global for all repos."""
        if use_global:
            from minion.comms import who_global as _who_global
            _output(_who_global(), ctx.obj["human"])
        else:
            from minion.comms import who as _who
            _output(_who(), ctx.obj["human"])

    @agent_group.command("update-hp")
    @_agent_option(required=True)
    @click.option("--input-tokens", "-i", required=True, type=int)
    @click.option("--output-tokens", "-o", required=True, type=int)
    @click.option("--limit", "-l", required=True, type=int)
    @click.option("--turn-input", default=None, type=int, help="Per-turn input tokens (current context pressure)")
    @click.option("--turn-output", default=None, type=int, help="Per-turn output tokens (current context pressure)")
    @click.pass_context
    def update_hp(ctx: click.Context, agent: str, input_tokens: int, output_tokens: int, limit: int, turn_input: int | None, turn_output: int | None) -> None:
        """Daemon-only: record token usage and compute health score."""
        from minion.monitoring import update_hp as _update_hp
        _output(_update_hp(agent, input_tokens, output_tokens, limit, turn_input, turn_output), ctx.obj["human"])

    @agent_group.command("cold-start")
    @_agent_option(required=True)
    @click.pass_context
    def cold_start(ctx: click.Context, agent: str) -> None:
        """Bootstrap an agent into (or back into) a session."""
        from minion.lifecycle import cold_start as _cold_start
        _output(_cold_start(agent), ctx.obj["human"], ctx.obj["compact"])

    @agent_group.command("refresh")
    @_agent_option(required=True)
    @click.pass_context
    def refresh_cmd(ctx: click.Context, agent: str) -> None:
        """Lightweight mid-session state refresh — no side effects.

        Returns current tasks (with DAG position), inbox summary, file claims,
        HP metrics, and interrupt/retire flags. Unlike cold-start, does not
        consume fenix_down records or return onboarding data."""
        from minion.lifecycle import refresh as _refresh
        _output(_refresh(agent), ctx.obj["human"], ctx.obj["compact"])

    @agent_group.command("fenix-down")
    @_agent_option(required=True)
    @click.option("--files", "-f", required=True)
    @click.option("--manifest", "-m", default="")
    @click.pass_context
    def fenix_down(ctx: click.Context, agent: str, files: str, manifest: str) -> None:
        """Save session state to disk before context window runs out."""
        from minion.lifecycle import fenix_down as _fenix_down
        _output(_fenix_down(agent, files, manifest), ctx.obj["human"])

    @agent_group.command("retire")
    @_agent_option(required=True, help="Agent to retire")
    @click.option("--requesting-agent", "-r", required=True, help="Lead requesting retirement")
    @click.pass_context
    def retire_agent_cmd(ctx: click.Context, agent: str, requesting_agent: str) -> None:
        """Signal a single daemon agent to exit gracefully. Lead only."""
        from minion.auth import require_class
        require_class("lead")(lambda: None)()
        from minion.crew import retire_agent as _retire_agent
        _output(_retire_agent(agent, requesting_agent), ctx.obj["human"])

    @agent_group.command("check-activity")
    @_agent_option(required=True)
    @click.pass_context
    def check_activity(ctx: click.Context, agent: str) -> None:
        """Check an agent's activity level."""
        from minion.monitoring import check_activity as _check_activity
        _output(_check_activity(agent), ctx.obj["human"])

    @agent_group.command("check-freshness")
    @_agent_option(required=True)
    @click.option("--files", "-f", required=True)
    @click.pass_context
    def check_freshness(ctx: click.Context, agent: str, files: str) -> None:
        """Check file freshness relative to agent's last set-context. Lead only."""
        from minion.auth import require_class
        require_class("lead")(lambda: None)()
        from minion.monitoring import check_freshness as _check_freshness
        _output(_check_freshness(agent, files), ctx.obj["human"])

    @agent_group.command("deregister")
    @click.option("--name", "-n", required=True)
    @click.pass_context
    def deregister(ctx: click.Context, name: str) -> None:
        """Remove an agent from the registry."""
        from minion.comms import deregister as _deregister
        _output(_deregister(name), ctx.obj["human"])

    @agent_group.command("rename")
    @click.option("--old", "-o", required=True)
    @click.option("--new", "-N", required=True)
    @click.pass_context
    def rename(ctx: click.Context, old: str, new: str) -> None:
        """Rename an agent. Lead only."""
        from minion.auth import require_class
        require_class("lead")(lambda: None)()
        from minion.comms import rename as _rename
        _output(_rename(old, new), ctx.obj["human"])

    @agent_group.command("interrupt")
    @_agent_option(required=True, help="Agent to interrupt")
    @click.option("--requesting-agent", "-r", required=True, help="Lead requesting interrupt")
    @click.pass_context
    def interrupt(ctx: click.Context, agent: str, requesting_agent: str) -> None:
        """Interrupt an agent's current invocation. Lead only."""
        from minion.auth import require_class
        require_class("lead")(lambda: None)()
        from minion.crew import interrupt_agent as _interrupt
        _output(_interrupt(agent, requesting_agent), ctx.obj["human"])

    @agent_group.command("resume")
    @_agent_option(required=True, help="Agent to resume")
    @click.option("--message", "-m", required=True, help="Message to send on resume")
    @click.option("--from", "-F", "from_agent", required=True, help="Sending agent (lead)")
    @click.pass_context
    def resume(ctx: click.Context, agent: str, message: str, from_agent: str) -> None:
        """Send a resume message to an interrupted agent. Lead only."""
        from minion.auth import require_class
        require_class("lead")(lambda: None)()
        from minion.comms import send as _send
        _output(_send(from_agent, agent, message), ctx.obj["human"])
