"""Reference integrity tests for CLI command registration.

Verify that every CLI command module registers its commands onto the root CLI group,
that all expected command groups and subcommands are accessible, and that the registration
wiring in main.py is complete — no module is silently dropped or misspelled.

Purpose: Reference integrity tests for CLI command registration.
Rationale: The CLI has 20+ command modules each with a register_commands() function.
    If any registration is dropped from main.py, or a module's register_commands()
    silently fails, commands vanish with no error. These tests catch that.
Responsibility: Verify CLI command wiring only. NOT responsible for testing command behavior.
Organization: One TestClass per concern, or standalone test functions."""

from __future__ import annotations

import importlib
import pkgutil

import click
import pytest

from minion.cli import cli
from minion.cli import main as cli_main

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _collect_all_commands(group: click.Group, prefix: str = "") -> dict[str, click.BaseCommand]:
    """Recursively collect every command/group reachable from *group*.

    Returns {full_dotted_name: command_object}.
    E.g. "agent.register", "comms.send.local", "poll".
    """
    ctx = click.Context(group, info_name="minion")
    result: dict[str, click.BaseCommand] = {}
    for name in group.list_commands(ctx):
        cmd = group.get_command(ctx, name)
        if cmd is None:
            continue
        full = f"{prefix}{name}" if not prefix else f"{prefix}.{name}"
        result[full] = cmd
        if isinstance(cmd, click.Group):
            result.update(_collect_all_commands(cmd, full))
    return result


# ---------------------------------------------------------------------------
# 1. Every *_cmds.py module in minion.cli has a register_commands callable
# ---------------------------------------------------------------------------

class TestEveryCommandModuleHasRegisterCallable:
    """Each *_cmds.py module must expose a register_commands (or known alternative)."""

    def _cmd_modules(self) -> list[str]:
        """Return the names of all *_cmds.py submodules in minion.cli."""
        import minion.cli as pkg
        modules = []
        for info in pkgutil.iter_modules(pkg.__path__, prefix="minion.cli."):
            if info.name.endswith("_cmds"):
                modules.append(info.name)
        return modules

    def test_all_cmd_modules_discovered(self):
        """Sanity: we find a reasonable number of command modules."""
        mods = self._cmd_modules()
        # As of this writing there are 20+ *_cmds.py modules
        assert len(mods) >= 15, f"Expected >=15 command modules, found {len(mods)}: {mods}"

    @pytest.mark.parametrize("mod_name", [
        "minion.cli.agent_cmds",
        "minion.cli.api_cmds",
        "minion.cli.backlog_cmds",
        "minion.cli.checklist_cmds",
        "minion.cli.comms_cmds",
        # completion_cmds uses a different pattern: exports `completions` group directly
        # instead of register_commands(). Tested separately below.
        "minion.cli.crew_cmds",
        "minion.cli.daemon_cmds",
        "minion.cli.db_cmds",
        "minion.cli.file_cmds",
        "minion.cli.flow_cmds",
        "minion.cli.global_cmds",
        "minion.cli.intel_cmds",
        "minion.cli.mission_cmds",
        "minion.cli.network_cmds",
        "minion.cli.req_cmds",
        "minion.cli.task_cmds",
        "minion.cli.top_level",
        "minion.cli.trigger_cmds",
        "minion.cli.war_cmds",
        "minion.cli.war_plan_cmds",
    ])
    def test_module_has_register_callable(self, mod_name: str):
        """Each command module must have a register_commands callable."""
        mod = importlib.import_module(mod_name)
        assert hasattr(mod, "register_commands"), (
            f"{mod_name} is missing register_commands()"
        )
        assert callable(mod.register_commands), (
            f"{mod_name}.register_commands is not callable"
        )


# ---------------------------------------------------------------------------
# 2. Every command module is actually wired in main.py
# ---------------------------------------------------------------------------

class TestMainRegistersAllModules:
    """main.py must import and call register_commands for every *_cmds module."""

    # These are the expected top-level groups that register_commands creates.
    # If a new group is added to a *_cmds.py, add it here.
    EXPECTED_GROUPS = {
        "agent",
        "api",
        "backlog",
        "checklist",
        "comms",
        "completions",
        "crew",
        "daemon",
        "db",
        "file",
        "flow",
        "global",
        "intel",
        "mission",
        "network",
        "req",
        "task",
        "trigger",
        "war",
        "war-plan",
    }

    def test_all_groups_present(self):
        """Every expected command group is registered on the root CLI."""
        ctx = click.Context(cli, info_name="minion")
        registered = set(cli.list_commands(ctx))
        for grp in self.EXPECTED_GROUPS:
            assert grp in registered, (
                f"Command group '{grp}' not found on root CLI. "
                f"Registered: {sorted(registered)}"
            )

    def test_no_unexpected_groups_without_commands(self):
        """Groups that exist should have at least one subcommand."""
        ctx = click.Context(cli, info_name="minion")
        for name in cli.list_commands(ctx):
            cmd = cli.get_command(ctx, name)
            if isinstance(cmd, click.Group):
                sub_ctx = click.Context(cmd, info_name=name, parent=ctx)
                subs = cmd.list_commands(sub_ctx)
                assert len(subs) > 0, (
                    f"Group '{name}' is registered but has zero subcommands"
                )


# ---------------------------------------------------------------------------
# 3. Specific subcommands exist under each group
# ---------------------------------------------------------------------------

class TestExpectedSubcommands:
    """Verify key subcommands exist under their groups.

    This catches the case where a register_commands() imports fine but
    silently fails to attach one of its commands (e.g. decorator typo).
    """

    # {group_name: {expected subcommands}}
    EXPECTED = {
        "agent": {
            "register", "deregister", "rename", "set-context", "set-status",
            "who", "cold-start", "fenix-down", "check-activity", "check-freshness",
            "update-hp", "refresh", "interrupt", "resume", "retire",
        },
        "comms": {"send", "check-inbox", "list-history", "purge-inbox", "sitrep-global"},
        "task": {
            "create", "define", "assign", "update", "list", "get", "show",
            "lineage", "close", "reopen", "pull", "complete-phase", "done",
            "block", "submit-result", "check-work", "result", "review",
            "test", "spec", "comment", "comments",
        },
        "flow": {"list", "show", "next-status", "transition"},
        "war": {"set-plan", "get-plan", "update-status", "log", "list-log"},
        "file": {"claim", "release", "list"},
        "crew": {"list", "spawn", "stand-down", "halt", "recruit", "hand-off-zone", "status"},
        "trigger": {"list", "clear-moon-crash"},
        "daemon": {"run", "start", "stop", "logs"},
        "backlog": {
            "add", "list", "show", "update", "promote", "defer", "kill",
            "lineage", "reindex",
        },
        "intel": {
            "add", "find", "list", "get", "read", "show", "link",
            "for-task", "suggest", "register-docs", "reindex",
        },
        "mission": {"list", "spawn", "suggest"},
        "req": {
            "create", "list", "update", "link", "decompose", "findings",
            "tree", "orphans", "unlinked", "status", "report", "register",
            "reindex", "itemize",
        },
        "network": {
            "serve", "status", "who", "projects", "project-agents",
            "overview", "alerts", "outbox", "gen-cert",
        },
        "db": {"prune", "schema-version"},
        "checklist": {"generate", "show", "template"},
        "war-plan": {"set", "show", "append"},
        "global": {"who", "send", "deregister", "prune"},
        "api": {
            "start", "stop", "status", "restart", "set-remote",
            "remove-remote", "list-remotes", "remote-agents",
            "remote-status", "remote-overview", "remote-projects",
            "remote-inbox", "remote-send", "remote-alerts",
        },
        "completions": {"show", "install"},
    }

    @pytest.mark.parametrize("group_name", sorted(EXPECTED.keys()))
    def test_subcommands_present(self, group_name: str):
        """All expected subcommands exist under the group."""
        ctx = click.Context(cli, info_name="minion")
        group_cmd = cli.get_command(ctx, group_name)
        assert group_cmd is not None, f"Group '{group_name}' not found on root CLI"
        assert isinstance(group_cmd, click.Group), (
            f"'{group_name}' is not a Group, it's a {type(group_cmd).__name__}"
        )
        sub_ctx = click.Context(group_cmd, info_name=group_name, parent=ctx)
        registered_subs = set(group_cmd.list_commands(sub_ctx))
        expected_subs = self.EXPECTED[group_name]
        missing = expected_subs - registered_subs
        assert not missing, (
            f"Group '{group_name}' is missing subcommands: {sorted(missing)}. "
            f"Registered: {sorted(registered_subs)}"
        )


# ---------------------------------------------------------------------------
# 4. Top-level (ungrouped) commands exist
# ---------------------------------------------------------------------------

class TestTopLevelCommands:
    """Commands registered directly on the root CLI (not under a group)."""

    EXPECTED_TOP_LEVEL = {
        "poll", "sitrep", "docs", "tools", "dashboard",
        "install-docs", "install-hooks", "debrief", "end-session",
    }

    def test_top_level_commands_present(self):
        ctx = click.Context(cli, info_name="minion")
        registered = set(cli.list_commands(ctx))
        for cmd_name in self.EXPECTED_TOP_LEVEL:
            assert cmd_name in registered, (
                f"Top-level command '{cmd_name}' not found. "
                f"Registered: {sorted(registered)}"
            )


# ---------------------------------------------------------------------------
# 5. Aliases are registered (hidden but functional)
# ---------------------------------------------------------------------------

class TestAliasesRegistered:
    """Backwards-compat aliases should be registered as hidden commands."""

    # Sample of key aliases from aliases.py
    EXPECTED_ALIASES = {
        "register",           # agent register
        "set-context",        # agent set-context
        "who",                # agent who
        "send-local",         # comms send local
        "send-global",        # comms send global
        "check-inbox",        # comms check-inbox
        "create-task",        # task create
        "list-tasks",         # task list
        "list-flows",         # flow list
        "claim-file",         # file claim
        "spawn-party",        # crew spawn
        "list-triggers",      # trigger list
        "log-raid",           # war log
        "list-raid-log",      # war list-log
    }

    def test_aliases_accessible(self):
        """Each expected alias resolves to a command on the root CLI."""
        ctx = click.Context(cli, info_name="minion")
        registered = set(cli.list_commands(ctx))
        for alias in self.EXPECTED_ALIASES:
            assert alias in registered, (
                f"Alias '{alias}' not found on root CLI. "
                f"Is aliases.py wired in main.py?"
            )

    def test_aliases_are_hidden(self):
        """Aliases should be hidden from --help."""
        ctx = click.Context(cli, info_name="minion")
        for alias in self.EXPECTED_ALIASES:
            cmd = cli.get_command(ctx, alias)
            if cmd is not None:
                # Some aliases shadow real top-level commands (e.g. 'who'),
                # which may not be hidden. Only check aliases that are
                # purely backwards-compat wrappers.
                if alias in {"send-local", "send-global", "create-task",
                             "list-tasks", "list-flows", "claim-file",
                             "spawn-party", "list-triggers", "log-raid",
                             "list-raid-log"}:
                    assert cmd.hidden, (
                        f"Alias '{alias}' should be hidden but is not"
                    )


# ---------------------------------------------------------------------------
# 6. Every command has a callback (not just a stub group)
# ---------------------------------------------------------------------------

class TestCommandsHaveCallbacks:
    """Leaf commands (non-groups) should have a non-None callback."""

    def test_leaf_commands_have_callbacks(self):
        all_cmds = _collect_all_commands(cli)
        missing_callback = []
        for name, cmd in all_cmds.items():
            if isinstance(cmd, click.Group):
                continue  # groups can have None callback (pass-through)
            if cmd.callback is None:
                missing_callback.append(name)
        assert not missing_callback, (
            f"Leaf commands with no callback (dead wiring): {missing_callback}"
        )


# ---------------------------------------------------------------------------
# 7. CLI module count matches registration count in main.py
# ---------------------------------------------------------------------------

class TestRegistrationCompleteness:
    """The number of register_commands calls in main.py should match
    the number of *_cmds.py modules (excluding aliases.py and completion_cmds.py
    which use different registration patterns).
    """

    def test_registration_count_matches_module_count(self):
        """Count register_commands imports in main.py vs *_cmds.py modules."""
        import minion.cli as pkg
        import inspect

        # Count *_cmds modules (excluding completion_cmds which uses a different pattern)
        cmd_modules = []
        for info in pkgutil.iter_modules(pkg.__path__, prefix="minion.cli."):
            if info.name.endswith("_cmds") and "completion" not in info.name:
                cmd_modules.append(info.name)

        # Count register_commands imports in main.py source
        source = inspect.getsource(cli_main)
        import_count = source.count("register_commands as")

        assert import_count >= len(cmd_modules), (
            f"main.py has {import_count} register_commands imports but there are "
            f"{len(cmd_modules)} *_cmds modules: {sorted(cmd_modules)}"
        )


# ---------------------------------------------------------------------------
# 8. FuzzyGroup is the root CLI group class
# ---------------------------------------------------------------------------

class TestFuzzyGroupWiring:
    """The root CLI should use FuzzyGroup for typo suggestions."""

    def test_cli_uses_fuzzy_group(self):
        from minion.cli.main import FuzzyGroup
        assert isinstance(cli, FuzzyGroup), (
            f"Root CLI group should be FuzzyGroup, got {type(cli).__name__}"
        )


# ---------------------------------------------------------------------------
# 9. Comms send subgroup has local and global
# ---------------------------------------------------------------------------

class TestNestedGroups:
    """Verify multi-level nesting works (comms > send > local/global)."""

    def test_comms_send_has_local_and_global(self):
        ctx = click.Context(cli, info_name="minion")
        comms = cli.get_command(ctx, "comms")
        assert isinstance(comms, click.Group)
        comms_ctx = click.Context(comms, info_name="comms", parent=ctx)
        send = comms.get_command(comms_ctx, "send")
        assert isinstance(send, click.Group), "comms send should be a group"
        send_ctx = click.Context(send, info_name="send", parent=comms_ctx)
        subs = set(send.list_commands(send_ctx))
        assert "local" in subs, "comms send local missing"
        assert "global" in subs, "comms send global missing"
