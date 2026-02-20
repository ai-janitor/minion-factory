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
    expected = [
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
    for cmd in expected:
        assert cmd in registered, f"Missing subcommand: {cmd}"
