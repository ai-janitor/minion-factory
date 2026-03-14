"""Tests for inbox piggyback on CLI command output.

Purpose: Verify that unread messages are appended to CLI output when
         MINION_AGENT_NAME is set, and that excluded commands (poll,
         check-inbox) do not trigger piggyback.
Rationale: Piggyback inbox delivery replaces send-side inbox discipline.
Responsibility: Test the _piggyback_inbox_on_close close handler in cli/main.py.
Organization: One test per acceptance criterion."""

from __future__ import annotations

import os

import pytest
from click.testing import CliRunner

pytestmark = [pytest.mark.integration, pytest.mark.db]


@pytest.fixture(autouse=True)
def _use_isolated_db(isolated_db_with_coordinator):
    """Delegate to conftest.isolated_db_with_coordinator; autouse ensures DB isolation."""


@pytest.fixture()
def runner():
    return CliRunner()


def _register_and_send(agent_name: str, message: str) -> None:
    """Register an agent and send them a message so inbox is non-empty."""
    from minion.comms import register, send, set_context
    register(agent_name=agent_name, agent_class="coder")
    register(agent_name="sender", agent_class="lead")
    # Set context to satisfy staleness check before sending
    set_context(agent_name="sender", context="test context", hp=95)
    result = send(
        from_agent="sender",
        to_agent=agent_name,
        message=message,
        msg_type="order",
    )
    assert "error" not in result, f"send failed: {result}"


# ---------------------------------------------------------------------------
# Piggyback appears when messages exist and MINION_AGENT_NAME is set
# ---------------------------------------------------------------------------


def test_piggyback_shows_messages_on_regular_command(runner, monkeypatch):
    """When MINION_AGENT_NAME is set and agent has unread messages,
    the piggyback appends them to stderr after the command output."""
    _register_and_send("pb-agent", "hello from piggyback test")
    monkeypatch.setenv("MINION_AGENT_NAME", "pb-agent")

    from minion.cli import cli
    result = runner.invoke(cli, ["agent", "who"])

    # The primary command should succeed
    assert result.exit_code == 0
    # Piggybacked messages appear on stderr
    assert "[INBOX]" in result.stderr
    assert "hello from piggyback test" in result.stderr


# ---------------------------------------------------------------------------
# No output when no messages
# ---------------------------------------------------------------------------


def test_piggyback_silent_when_no_messages(runner, monkeypatch):
    """When MINION_AGENT_NAME is set but no unread messages exist,
    no piggyback output appears."""
    from minion.comms import register
    register(agent_name="quiet-agent", agent_class="coder")
    monkeypatch.setenv("MINION_AGENT_NAME", "quiet-agent")

    from minion.cli import cli
    result = runner.invoke(cli, ["agent", "who"])

    assert result.exit_code == 0
    assert "[INBOX]" not in result.stderr


# ---------------------------------------------------------------------------
# No output when MINION_AGENT_NAME is not set
# ---------------------------------------------------------------------------


def test_piggyback_silent_when_no_agent_env(runner, monkeypatch):
    """When MINION_AGENT_NAME is not set, no piggyback occurs."""
    monkeypatch.delenv("MINION_AGENT_NAME", raising=False)

    from minion.cli import cli
    result = runner.invoke(cli, ["agent", "who"])

    assert result.exit_code == 0
    assert "[INBOX]" not in result.stderr


# ---------------------------------------------------------------------------
# Excluded commands: poll
# ---------------------------------------------------------------------------


def test_piggyback_excluded_for_poll(runner, monkeypatch):
    """The poll command is excluded from piggyback to avoid duplication."""
    _register_and_send("poll-agent", "should not piggyback")
    monkeypatch.setenv("MINION_AGENT_NAME", "poll-agent")

    from minion.cli import cli
    # poll with --timeout 1 so it exits quickly
    result = runner.invoke(cli, ["poll", "--agent", "poll-agent", "--timeout", "1"])

    # poll may exit with code 0 (content) or 1 (timeout) — either way,
    # the piggyback should NOT appear on stderr
    # Note: poll delivers messages itself, so [INBOX] piggyback must not duplicate
    assert "[INBOX]" not in result.stderr


# ---------------------------------------------------------------------------
# Excluded commands: check-inbox
# ---------------------------------------------------------------------------


def test_piggyback_excluded_for_check_inbox(runner, monkeypatch):
    """The check-inbox command is excluded from piggyback."""
    _register_and_send("inbox-agent", "should not piggyback")
    monkeypatch.setenv("MINION_AGENT_NAME", "inbox-agent")

    from minion.cli import cli
    result = runner.invoke(cli, ["check-inbox", "--agent", "inbox-agent"])

    # check-inbox already delivers messages — piggyback must not duplicate
    assert "[INBOX]" not in result.stderr


# ---------------------------------------------------------------------------
# Errors in piggyback never break the primary command
# ---------------------------------------------------------------------------


def test_piggyback_error_does_not_break_command(runner, monkeypatch):
    """If check_inbox_silent raises, the primary command still succeeds."""
    from minion.comms import register
    register(agent_name="error-agent", agent_class="coder")
    monkeypatch.setenv("MINION_AGENT_NAME", "error-agent")

    # Monkey-patch check_inbox_silent to raise
    import minion.comms.inbox as inbox_mod
    original = inbox_mod.check_inbox_silent

    def _raise(agent_name):
        raise RuntimeError("simulated inbox failure")

    monkeypatch.setattr(inbox_mod, "check_inbox_silent", _raise)

    from minion.cli import cli
    result = runner.invoke(cli, ["agent", "who"])

    # Primary command must still succeed despite inbox error
    assert result.exit_code == 0
    assert "[INBOX]" not in result.stderr

    # Restore
    monkeypatch.setattr(inbox_mod, "check_inbox_silent", original)


# ---------------------------------------------------------------------------
# Messages are marked as delivered after piggyback
# ---------------------------------------------------------------------------


def test_piggyback_marks_messages_as_delivered(runner, monkeypatch):
    """After piggyback delivers messages, a second invocation shows no messages."""
    _register_and_send("deliver-agent", "one-time message")
    monkeypatch.setenv("MINION_AGENT_NAME", "deliver-agent")

    from minion.cli import cli

    # First invocation — messages appear
    result1 = runner.invoke(cli, ["agent", "who"])
    assert "[INBOX]" in result1.stderr
    assert "one-time message" in result1.stderr

    # Second invocation — messages already delivered, no piggyback
    result2 = runner.invoke(cli, ["agent", "who"])
    assert "[INBOX]" not in result2.stderr
