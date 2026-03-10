"""CLI group smoke tests.

Purpose: CLI group smoke tests.
Rationale: Test coverage for the corresponding module.
Responsibility: CLI group smoke tests. NOT responsible for unrelated concerns.
Organization: One TestClass per concern, or standalone test functions."""
import pytest
import click
from click.testing import CliRunner
from minion.cli import cli

pytestmark = pytest.mark.unit


def test_cli_is_group():
    assert isinstance(cli, click.Group)


def test_cli_help_exits_zero():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0


def test_cli_expected_subcommands():
    # Old flat names must stay registered as backwards-compat aliases
    expected_aliases = [
        "register",
        "send-local",
        "send-global",
        "check-inbox",
        "who",
        "set-status",
        "set-context",
        "spawn-party",
        "stand-down",
        "create-task",
        "get-tasks",
        "party-status",
        "sitrep",
        "cold-start",
        "poll",
    ]
    registered = list(cli.commands.keys())
    for cmd in expected_aliases:
        assert cmd in registered, f"Missing backwards-compat alias: {cmd}"


def test_cli_new_groups_registered():
    # New canonical group names must be present
    expected_groups = [
        "agent",
        "comms",
        "task",
        "flow",
        "war",
        "file",
        "crew",
        "trigger",
        "daemon",
        "mission",
        "req",
    ]
    registered = list(cli.commands.keys())
    for grp in expected_groups:
        assert grp in registered, f"Missing group: {grp}"


def test_agent_group_subcommands():
    runner = CliRunner()
    result = runner.invoke(cli, ["agent", "--help"])
    assert result.exit_code == 0
    for sub in ["register", "set-status", "set-context", "who", "update-hp",
                "cold-start", "fenix-down", "retire", "check-activity", "check-freshness"]:
        assert sub in result.output, f"agent group missing: {sub}"


def test_comms_group_subcommands():
    runner = CliRunner()
    result = runner.invoke(cli, ["comms", "--help"])
    assert result.exit_code == 0
    for sub in ["send", "check-inbox", "purge-inbox", "list-history"]:
        assert sub in result.output, f"comms group missing: {sub}"


def test_task_group_subcommands():
    runner = CliRunner()
    result = runner.invoke(cli, ["task", "--help"])
    assert result.exit_code == 0
    for sub in ["create", "assign", "update", "list", "get", "lineage",
                "submit-result", "close", "reopen", "pull", "complete-phase", "check-work"]:
        assert sub in result.output, f"task group missing: {sub}"


def test_flow_group_subcommands():
    runner = CliRunner()
    result = runner.invoke(cli, ["flow", "--help"])
    assert result.exit_code == 0
    for sub in ["list", "show", "next-status", "transition"]:
        assert sub in result.output, f"flow group missing: {sub}"


def test_war_group_subcommands():
    runner = CliRunner()
    result = runner.invoke(cli, ["war", "--help"])
    assert result.exit_code == 0
    for sub in ["set-plan", "get-plan", "update-status", "log", "list-log"]:
        assert sub in result.output, f"war group missing: {sub}"


def test_file_group_subcommands():
    runner = CliRunner()
    result = runner.invoke(cli, ["file", "--help"])
    assert result.exit_code == 0
    for sub in ["claim", "release", "list"]:
        assert sub in result.output, f"file group missing: {sub}"


def test_crew_group_subcommands():
    runner = CliRunner()
    result = runner.invoke(cli, ["crew", "--help"])
    assert result.exit_code == 0
    for sub in ["list", "spawn", "stand-down", "halt", "recruit", "hand-off-zone", "status"]:
        assert sub in result.output, f"crew group missing: {sub}"


def test_trigger_group_subcommands():
    runner = CliRunner()
    result = runner.invoke(cli, ["trigger", "--help"])
    assert result.exit_code == 0
    for sub in ["list", "clear-moon-crash"]:
        assert sub in result.output, f"trigger group missing: {sub}"


def test_daemon_group_subcommands():
    runner = CliRunner()
    result = runner.invoke(cli, ["daemon", "--help"])
    assert result.exit_code == 0
    for sub in ["start", "stop", "logs"]:
        assert sub in result.output, f"daemon group missing: {sub}"


def test_api_group_subcommands():
    runner = CliRunner()
    result = runner.invoke(cli, ["api", "--help"])
    assert result.exit_code == 0
    for sub in ["start", "stop", "status", "restart", "set-remote",
                "list-remotes", "remove-remote", "remote-status",
                "remote-agents", "remote-send", "remote-inbox",
                "remote-projects", "remote-overview", "remote-alerts"]:
        assert sub in result.output, f"api group missing: {sub}"


def test_backlog_group_subcommands():
    runner = CliRunner()
    result = runner.invoke(cli, ["backlog", "--help"])
    assert result.exit_code == 0
    for sub in ["add", "list", "show", "update", "promote", "kill",
                "defer", "lineage", "reindex"]:
        assert sub in result.output, f"backlog group missing: {sub}"


def test_network_group_subcommands():
    runner = CliRunner()
    result = runner.invoke(cli, ["network", "--help"])
    assert result.exit_code == 0
    for sub in ["serve", "status", "who", "projects", "project-agents",
                "overview", "alerts", "gen-cert", "outbox"]:
        assert sub in result.output, f"network group missing: {sub}"


def test_req_group_subcommands():
    runner = CliRunner()
    result = runner.invoke(cli, ["req", "--help"])
    assert result.exit_code == 0
    for sub in ["create", "register", "list", "status", "update", "tree",
                "decompose", "link", "orphans", "unlinked", "reindex",
                "report", "findings", "itemize"]:
        assert sub in result.output, f"req group missing: {sub}"


def test_intel_group_subcommands():
    runner = CliRunner()
    result = runner.invoke(cli, ["intel", "--help"])
    assert result.exit_code == 0
    for sub in ["add", "list", "get", "find", "link", "for-task",
                "read", "suggest", "register-docs", "reindex"]:
        assert sub in result.output, f"intel group missing: {sub}"


def test_mission_group_subcommands():
    runner = CliRunner()
    result = runner.invoke(cli, ["mission", "--help"])
    assert result.exit_code == 0
    for sub in ["list", "suggest", "spawn"]:
        assert sub in result.output, f"mission group missing: {sub}"
