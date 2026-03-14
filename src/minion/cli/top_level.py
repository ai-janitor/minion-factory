"""Top-level commands — poll, sitrep, docs, register shortcuts, and other ungrouped commands.
These live directly on the root CLI group, not under a subgroup.

Purpose: Top-level commands — poll, sitrep, docs, register shortcuts, and other ungrouped commands.
Rationale: Extracted into own module for single-responsibility CLI command grouping.
Responsibility: Top-level commands — poll, sitrep, docs, register shortcuts, and other ungrouped commands. NOT responsible for unrelated concerns.
Organization: Click command group with subcommands."""

from __future__ import annotations

import os
import sys

import click

from minion.cli.main import _agent_option, _output


def register_commands(cli: click.Group) -> None:
    """Attach ungrouped top-level commands to the root CLI."""

    @cli.command()
    @_agent_option(required=True, help="Agent name to poll as")
    @click.option("--interval", "-i", default=5, type=int, help="Seconds between checks (default: 5)")
    @click.option("--timeout", "-T", default=0, type=int, help="Max wait in seconds. 0 = block forever until content arrives (default: 0)")
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

    @cli.command("refresh")
    @click.pass_context
    def refresh(ctx: click.Context) -> None:
        """Re-seed .work/ with latest bundled protocols, flows, and configs from the installed package.

        Overwrites local copies with the package defaults. Use after upgrading
        the CLI to pick up new protocol versions. Project-specific customizations
        will be lost — commit or back up first.
        """
        import shutil
        from minion.defaults import resolve_db_path
        from minion.tasks.loader import _bundled_protocols_dir, _find_flows_dir

        db_path = resolve_db_path()
        work_dir = os.path.dirname(db_path)

        refreshed = []

        # Protocols
        bundled_protocols = _bundled_protocols_dir()
        local_protocols = os.path.join(work_dir, "protocols")
        if bundled_protocols.exists():
            if os.path.exists(local_protocols):
                shutil.rmtree(local_protocols)
            shutil.copytree(str(bundled_protocols), local_protocols)
            refreshed.append(f"protocols → {local_protocols}")

        # Flow YAMLs
        bundled_flows = _find_flows_dir()
        local_flows = os.path.join(work_dir, "flows")
        flow_yamls = list(bundled_flows.glob("*.yaml"))
        if flow_yamls:
            os.makedirs(local_flows, exist_ok=True)
            for f in flow_yamls:
                shutil.copy2(str(f), os.path.join(local_flows, f.name))
            refreshed.append(f"flows ({len(flow_yamls)} yamls) → {local_flows}")

        _output({"status": "refreshed", "items": refreshed}, ctx.obj["human"])

    @cli.command("dashboard")
    @click.option("--web", is_flag=True, default=False,
                  help="Launch web dashboard (browser) instead of terminal TUI")
    @click.option("--port", default=8765, type=int,
                  help="Port for web dashboard (default: 8765)")
    @click.option("--host", default="0.0.0.0",
                  help="Host to bind web dashboard (default: 0.0.0.0)")
    @click.option("--db", "db_path", default="",
                  help="Path to minion.db (auto-detected if omitted)")
    @click.pass_context
    def dashboard_cmd(ctx: click.Context, web: bool, port: int, host: str, db_path: str) -> None:
        """Live task board — terminal TUI or browser web dashboard.

        Default: terminal TUI (ANSI). Use --web for browser-based dashboard
        served via WebSocket on the specified port.

        \b
        Examples:
          minion dashboard              # Terminal TUI
          minion dashboard --web        # Web dashboard on http://0.0.0.0:8765
          minion dashboard --web --port 9000
          minion dashboard --web --db /path/to/minion.db
        """
        if web:
            from minion.dashboard.web_server import serve
            serve(host=host, port=port, db_path=db_path)
        else:
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
    @click.option("--class", "-c", "agent_class", default="", help="Class to list tools for (default: MINION_CLASS env)")
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
    @click.option("--debrief-file", "-f", required=True)
    @click.pass_context
    def debrief(ctx: click.Context, agent: str, debrief_file: str) -> None:
        """File a session debrief. Lead only."""
        from minion.auth import require_class
        require_class("lead")(lambda: None)()
        from minion.lifecycle import debrief as _debrief
        _output(_debrief(agent, debrief_file), ctx.obj["human"])

    @cli.command("install-hooks")
    @click.pass_context
    def install_hooks(ctx: click.Context) -> None:
        """Install hooks for minion agent enforcement.

        Installs:
        1. Claude Code Stop hook (poll-on-stop.sh) — checks inbox after every response
        2. Git pre-commit hook (scaffolding-gate.sh) — blocks code commits before scaffolding

        Safe to run multiple times — merges without clobbering existing hooks.
        Only activates when MINION_AGENT_NAME env var is set (spawn time)."""
        import json as _json
        from pathlib import Path

        settings_path = Path.home() / ".claude" / "settings.json"
        scripts_dir = Path(__file__).resolve().parents[3] / "scripts"

        # Fallback: look in installed package
        if not scripts_dir.exists():
            import minion
            scripts_dir = Path(minion.__file__).resolve().parents[1] / "scripts"

        installed: list[str] = []
        skipped: list[str] = []
        errors: list[str] = []

        # --- Claude Code Stop hook ---
        # Copy script to ~/.minion/hooks/ so it doesn't depend on repo location
        stable_hooks_dir = Path.home() / ".minion" / "hooks"
        stable_hooks_dir.mkdir(parents=True, exist_ok=True)

        stop_script_src = scripts_dir / "poll-on-stop.sh"
        stop_script_dst = stable_hooks_dir / "poll-on-stop.sh"

        if not stop_script_src.exists():
            errors.append(f"poll-on-stop.sh not found at {stop_script_src}")
        else:
            import shutil
            shutil.copy2(stop_script_src, stop_script_dst)
            stop_script_dst.chmod(0o755)

            settings: dict = {}
            if settings_path.exists():
                settings = _json.loads(settings_path.read_text())

            hooks = settings.setdefault("hooks", {})
            stop_hooks = hooks.setdefault("Stop", [])
            hook_cmd = str(stop_script_dst)

            # Remove any old entries pointing to repo or stale paths
            stop_hooks[:] = [
                entry for entry in stop_hooks
                if not (isinstance(entry, dict) and any(
                    "poll-on-stop.sh" in h.get("command", "")
                    for h in entry.get("hooks", [])
                ))
            ]

            stop_hooks.append({
                "hooks": [{"type": "command", "command": hook_cmd}]
            })
            installed.append("Stop:poll-on-stop.sh")

            settings_path.parent.mkdir(parents=True, exist_ok=True)
            settings_path.write_text(_json.dumps(settings, indent=2) + "\n")

        # --- Git pre-commit hook (scaffolding gate) ---
        gate_script = scripts_dir / "scaffolding-gate.sh"
        if not gate_script.exists():
            errors.append(f"scaffolding-gate.sh not found at {gate_script}")
        else:
            gate_script.chmod(0o755)
            # Find .git/hooks directory — walk up from cwd to find .git
            import subprocess
            try:
                git_root = subprocess.check_output(
                    ["git", "rev-parse", "--show-toplevel"],
                    stderr=subprocess.DEVNULL,
                ).decode().strip()
                hooks_dir = Path(git_root) / ".git" / "hooks"
                hooks_dir.mkdir(parents=True, exist_ok=True)
                pre_commit = hooks_dir / "pre-commit"

                if pre_commit.exists():
                    # Check if it's already our script
                    target = pre_commit.resolve()
                    if target == gate_script.resolve():
                        skipped.append("git:pre-commit (scaffolding-gate.sh)")
                    else:
                        # Existing pre-commit hook — don't clobber, warn
                        errors.append(
                            f"git pre-commit hook already exists at {pre_commit}. "
                            f"Manually symlink: ln -sf {gate_script} {pre_commit}"
                        )
                else:
                    pre_commit.symlink_to(gate_script)
                    installed.append("git:pre-commit (scaffolding-gate.sh)")
            except (subprocess.CalledProcessError, OSError):
                errors.append("Not in a git repo — skipped git pre-commit hook")

        result: dict[str, object] = {
            "status": "ok",
            "installed": installed,
            "already_present": skipped,
            "note": "Hooks activate when MINION_AGENT_NAME env var is set at spawn time",
        }
        if errors:
            result["errors"] = errors
        _output(result, ctx.obj["human"])

    @cli.command("completions")
    @click.option("--shell", "-s", type=click.Choice(["bash", "zsh", "fish"]), default=None,
                  help="Shell type (auto-detected if omitted)")
    def completions_cmd(shell: str | None) -> None:
        """Print shell completion setup instructions.

        Click provides built-in shell completion for all commands, options,
        and arguments. Run the printed eval line in your shell profile to
        enable tab-completion for the minion CLI.

        \b
        Examples:
          minion completions          # auto-detect shell
          minion completions --shell zsh
          minion completions --shell bash
          minion completions --shell fish
        """
        # Auto-detect shell from $SHELL env var
        if shell is None:
            shell_env = os.environ.get("SHELL", "")
            if "zsh" in shell_env:
                shell = "zsh"
            elif "fish" in shell_env:
                shell = "fish"
            else:
                shell = "bash"

        # Click uses _<PROGNAME>_COMPLETE env var convention
        instructions = {
            "zsh": (
                '# Add to ~/.zshrc:\n'
                'eval "$(_MINION_COMPLETE=zsh_source minion)"'
            ),
            "bash": (
                '# Add to ~/.bashrc:\n'
                'eval "$(_MINION_COMPLETE=bash_source minion)"'
            ),
            "fish": (
                '# Add to ~/.config/fish/completions/minion.fish:\n'
                '_MINION_COMPLETE=fish_source minion | source'
            ),
        }
        click.echo(f"Shell completion for {shell}:\n")
        click.echo(instructions[shell])
        click.echo(f"\nAfter adding, restart your shell or run: source ~/.{shell}rc")

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
