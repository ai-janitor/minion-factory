"""Root Click group, global options (-C, --json, --compact), and shared helpers.
This module defines the `cli` group and the `_agent_option` / `_store_heartbeat_agent`
helpers used across all command modules. Submodules register their commands/groups
onto `cli` at import time via `register_*` functions called from this file's tail.

Includes FuzzyGroup — a Click group subclass that suggests close matches when a user
misspells a command, using difflib.get_close_matches().

Purpose: Root Click group, global options (-C, --json, --compact), and shared helpers.
Rationale: Extracted into own module for single-responsibility CLI command grouping.
Responsibility: Root Click group, global options (-C, --json, --compact), and shared helpers. NOT responsible for unrelated concerns.
Organization: Click command group with subcommands.

Output default logic:
  - Default output is human-readable text (what --human used to do).
  - --json flag opts in to JSON output (for scripts and programmatic consumers).
  - MINION_CLASS env var set => auto-JSON (daemon agents parse JSON programmatically).
  - --human is kept as a hidden no-op for backward compatibility."""

from __future__ import annotations

import os
from difflib import get_close_matches

import click


# ---------------------------------------------------------------------------
# FuzzyGroup — suggest close command matches on typos
# ---------------------------------------------------------------------------

class FuzzyGroup(click.Group):
    """Click group that suggests similar commands when a command is not found.

    Uses difflib.get_close_matches() with a cutoff of 0.6 to find commands
    that are similar to the misspelled input and appends suggestions to the
    error message.
    """

    def resolve_command(self, ctx: click.Context, args: list[str]) -> tuple:
        """Override resolve_command to add fuzzy suggestions on UsageError."""
        try:
            return super().resolve_command(ctx, args)
        except click.UsageError as exc:
            # Only add suggestions if there's a command name to match against
            if args:
                cmd_name = args[0]
                available = self.list_commands(ctx)
                matches = get_close_matches(cmd_name, available, n=3, cutoff=0.6)
                if matches:
                    suggestion = ", ".join(f"'{m}'" for m in matches)
                    exc.message += f"\n\nDid you mean: {suggestion}?"
            raise

from minion.db import init_db, reset_db_path
from minion.fs import ensure_dirs
from minion.logging_setup import configure_logging
from minion.output import output as _output  # noqa: F401 — re-exported for submodules

# Configure logging at CLI startup — library modules just call getLogger(__name__)
configure_logging()


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
    return click.option("--agent", "-a", **kwargs)


@click.group(cls=FuzzyGroup, epilog="Run 'minion <group> --help' to see subcommands. Run 'minion docs' for the full reference.")
@click.version_option(package_name="minion-factory")
@click.option("--json", "use_json", is_flag=True, help="JSON output (default is human-readable text)")
@click.option("--human", is_flag=True, hidden=True, help="(deprecated, now the default) Human-readable output")
@click.option("--compact", is_flag=True, help="Concise text output for agent context injection")
@click.option("--project-dir", "-C", default=None, help="Project directory (default: cwd)")
@click.pass_context
def cli(ctx: click.Context, use_json: bool, human: bool, compact: bool, project_dir: str | None) -> None:
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
      Poll checks BOTH automatically.

    \b
    Output (default: human-readable text):
      --json     JSON output for scripts / programmatic consumption
      --compact  Concise text for agent context injection
      MINION_CLASS env var set => auto-JSON (daemon agents)"""
    ctx.ensure_object(dict)
    # Output default logic:
    # - Human-readable is the default for interactive CLI use.
    # - --json flag explicitly requests JSON output.
    # - MINION_CLASS env var set => daemon agent => auto-JSON for backward compat.
    # - --human is a hidden no-op (kept for backward compat, human is now default).
    is_daemon = bool(os.environ.get("MINION_CLASS"))
    # human=True means "not JSON". It's True unless --json was passed or daemon auto-JSON applies.
    # Explicit --json always wins. Explicit --human (legacy) forces human even for daemons.
    if use_json:
        resolved_human = False
    elif human:
        # Explicit --human flag (legacy backward compat) — force human even for daemons
        resolved_human = True
    elif is_daemon:
        # Daemon agents auto-get JSON for backward compat
        resolved_human = False
    else:
        # Default: human-readable
        resolved_human = True
    ctx.obj["human"] = resolved_human
    ctx.obj["compact"] = compact
    ctx.obj["project_dir"] = os.path.abspath(project_dir) if project_dir else None
    # SU-16: Normalize -C to absolute path and add debug log for traceability.
    # Set DB path before init so all commands target the right project
    if project_dir:
        import logging as _logging
        abs_project_dir = os.path.abspath(project_dir)
        _logging.getLogger("minion.cli").debug(
            "-C resolved: %r -> %s", project_dir, abs_project_dir
        )
        db_path = os.path.join(abs_project_dir, ".work", "minion.db")
        os.environ["MINION_DB_PATH"] = db_path
        reset_db_path()
    init_db()
    ensure_dirs()

    # Universal heartbeat: any CLI command by a registered agent updates last_seen
    # in BOTH the coordinator DB and the local .work/minion.db.
    # Agent identity comes from --agent option OR MINION_AGENT_NAME env var.
    def _heartbeat_on_close() -> None:
        agent = ctx.obj.get("_heartbeat_agent") or os.environ.get("MINION_AGENT_NAME")
        if not agent:
            return
        try:
            from minion.db import get_db, now_iso, touch_coordinator_activity
            # Touch coordinator DB (cross-project presence)
            touch_coordinator_activity(agent)
            # Touch local .work/minion.db last_seen (same-project dashboard)
            now = now_iso()
            conn = get_db()
            try:
                conn.execute(
                    "UPDATE agents SET last_seen = ? WHERE name = ?",
                    (now, agent),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception:
            pass  # broad catch: best-effort heartbeat — must never break CLI commands — never let heartbeat failures break commands

    ctx.call_on_close(_heartbeat_on_close)

    # ---------------------------------------------------------------------------
    # Piggyback inbox delivery: after every CLI command, if MINION_AGENT_NAME is
    # set, check for unread messages and append them to stderr. This replaces
    # send-side inbox discipline — agents see messages in the output they are
    # already reading. Excluded for commands that already handle inbox (poll,
    # check-inbox) to avoid duplication.
    # ---------------------------------------------------------------------------
    # Commands that already deliver inbox content — skip piggyback for these.
    # Matched against sys.argv tokens so both "minion poll" and
    # "minion comms check-inbox" are caught regardless of nesting depth.
    _PIGGYBACK_EXCLUDED_TOKENS = {"poll", "check-inbox"}

    def _piggyback_inbox_on_close() -> None:
        agent = ctx.obj.get("_heartbeat_agent") or os.environ.get("MINION_AGENT_NAME")
        if not agent:
            return
        # Skip commands that already handle inbox delivery to avoid duplication.
        import sys as _sys
        argv_tokens = set(_sys.argv[1:])  # drop the program name
        if argv_tokens & _PIGGYBACK_EXCLUDED_TOKENS:
            return
        try:
            from minion.comms.inbox import check_inbox_silent
            messages = check_inbox_silent(agent)
            if messages:
                click.echo(f"\n--- [INBOX] ---\n{messages}\n--- [/INBOX] ---", err=True)
        except Exception:
            pass  # best-effort — must never break the primary command

    ctx.call_on_close(_piggyback_inbox_on_close)

    # ---------------------------------------------------------------------------
    # CLI activity logger: append a JSONL line to .work/agent-activity/<agent>.jsonl
    # on every CLI invocation. Makes terminal agent activity visible to the
    # dashboard stream tailer — same visibility that daemon agents get via
    # .minion-swarm/logs/.stream.jsonl. Best-effort: failures silently ignored.
    # ---------------------------------------------------------------------------
    def _log_activity_on_close() -> None:
        agent = ctx.obj.get("_heartbeat_agent") or os.environ.get("MINION_AGENT_NAME")
        if not agent:
            return
        try:
            import json as _json
            import sys as _sys
            from datetime import datetime as _dt, timezone as _tz
            from minion.fs import AGENT_ACTIVITY_DIR

            # Build the command and args from sys.argv.
            # argv[0] is the program name ("minion"); argv[1:] are command + flags.
            argv = _sys.argv[1:]  # drop program name
            # Reconstruct the command name (first non-flag tokens) and remaining args.
            command_parts: list[str] = []
            args_parts: list[str] = []
            past_command = False
            for token in argv:
                if not past_command and not token.startswith("-"):
                    command_parts.append(token)
                else:
                    past_command = True
                    args_parts.append(token)

            record = {
                "command": " ".join(command_parts),
                "args": args_parts,
                "timestamp": _dt.now(_tz.utc).isoformat(),
                "agent": agent,
            }

            os.makedirs(AGENT_ACTIVITY_DIR, exist_ok=True)
            activity_file = os.path.join(AGENT_ACTIVITY_DIR, f"{agent}.jsonl")
            with open(activity_file, "a", encoding="utf-8") as f:
                f.write(_json.dumps(record, ensure_ascii=False) + "\n")
        except Exception:
            pass  # best-effort — must never break the primary CLI command

    ctx.call_on_close(_log_activity_on_close)


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
from minion.cli.db_cmds import register_commands as _reg_db  # noqa: E402
from minion.cli.team_cmds import register_commands as _reg_team  # noqa: E402
from minion.cli.coordinator_cmds import register_commands as _reg_coordinator  # noqa: E402
from minion.cli.top_level import register_commands as _reg_top  # noqa: E402
from minion.cli.aliases import register_aliases  # noqa: E402
from minion.cli.checklist_cmds import register_commands as _reg_checklist  # noqa: E402
from minion.cli.completion_cmds import completions as _completions  # noqa: E402

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
_reg_db(cli)
_reg_team(cli)
_reg_coordinator(cli)
_reg_checklist(cli)
_reg_top(cli)
cli.add_command(_completions)
register_aliases(cli)
