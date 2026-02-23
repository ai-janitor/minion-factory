"""CLI group smoke tests."""
import click
from click.testing import CliRunner
from minion.cli import cli


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
        "send",
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
