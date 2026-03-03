"""Top-level commands — poll, sitrep, docs, register shortcuts, and other ungrouped commands.

These live directly on the root CLI group, not under a subgroup.
"""

from __future__ import annotations

import os
import sys

import click

from minion.cli.main import _agent_option, _output


def register_commands(cli: click.Group) -> None:
    """Attach ungrouped top-level commands to the root CLI."""

    @cli.command()
    @_agent_option(required=True, help="Agent name to poll as")
    @click.option("--interval", default=5, type=int, help="Seconds between checks (default: 5)")
    @click.option("--timeout", default=0, type=int, help="Max wait in seconds. 0 = block forever until content arrives (default: 0)")
    @click.pass_context
    def poll(ctx: click.Context, agent: str, interval: int, timeout: int) -> None:
        """Block until messages or tasks arrive, then print and exit.

        If you're not polling, you CANNOT receive messages. No poll = no comms.
        Every agent MUST have poll running to participate in the session.

        Start poll in the FOREGROUND. It blocks until a message arrives. Tuck to
        terminal background if needed — do NOT launch as a background task.

        Checks both inbox and task queue every INTERVAL seconds.
        Exits with code 0 (content found), 1 (timeout), or 3 (stand_down/retire signal).
        Designed to run in a loop: call poll, process output, call poll again."""
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
    @_agent_option(required=True)
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
    @_agent_option(required=True)
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
    @_agent_option(required=True, help="Agent to interrupt")
    @click.option("--requesting-agent", required=True, help="Lead requesting interrupt")
    @click.pass_context
    def interrupt(ctx: click.Context, agent: str, requesting_agent: str) -> None:
        """Interrupt an agent's current invocation. Lead only."""
        from minion.auth import require_class
        require_class("lead")(lambda: None)()
        from minion.crew import interrupt_agent as _interrupt
        _output(_interrupt(agent, requesting_agent), ctx.obj["human"])

    @cli.command()
    @_agent_option(required=True, help="Agent to resume")
    @click.option("--message", required=True, help="Message to send on resume")
    @click.option("--from", "from_agent", required=True, help="Sending agent (lead)")
    @click.pass_context
    def resume(ctx: click.Context, agent: str, message: str, from_agent: str) -> None:
        """Send a resume message to an interrupted agent. Lead only."""
        from minion.auth import require_class
        require_class("lead")(lambda: None)()
        from minion.comms import send as _send
        _output(_send(from_agent, agent, message), ctx.obj["human"])

    @cli.command("docs")
    @click.option("--format", "fmt", type=click.Choice(["markdown", "json"]), default="markdown",
                  help="Output format")
    @click.option("--output", "-o", "output_dir", default=None, type=click.Path(),
                  help="Write cli-reference.md to this directory")
    def docs_cmd(fmt: str, output_dir: str | None) -> None:
        """Generate CLI reference from Click introspection."""
        from minion.cli_schema import generate_cli_schema, schema_to_json, schema_to_markdown

        # Import cli from the package (avoid circular — use the already-built object)
        from minion.cli.main import cli as _cli
        schema = generate_cli_schema(_cli)
        if fmt == "json":
            click.echo(schema_to_json(schema))
        elif output_dir:
            content = schema_to_markdown(schema)
            path = os.path.join(output_dir, "cli-reference.md")
            os.makedirs(output_dir, exist_ok=True)
            with open(path, "w") as f:
                f.write(content)
            click.echo(f"Wrote {path}")
        else:
            click.echo(schema_to_markdown(schema))
