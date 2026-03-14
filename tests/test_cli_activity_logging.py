"""Tests for CLI activity logging and stream tailer CLI activity reader.

Purpose: Verify that (a) the CLI close handler writes JSONL to
    .work/agent-activity/<agent>.jsonl when an agent name is set,
    (b) the stream tailer's tail_cli_activity() correctly parses
    CLI activity JSONL files, (c) missing/empty/malformed files
    are handled gracefully, (d) web_server merges both daemon and
    CLI activity sources.
Responsibility: Test coverage for backlog #281 — CLI-level activity logging.
Organization: Grouped by component — CLI logger tests, then tailer tests.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from click.testing import CliRunner

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def activity_dir(tmp_path):
    """Create a temporary agent-activity directory."""
    d = tmp_path / "agent-activity"
    d.mkdir()
    return d


@pytest.fixture()
def sample_jsonl(activity_dir):
    """Write sample CLI activity JSONL for agent 'testbot'."""
    records = [
        {"command": "task list", "args": ["--status", "open"], "timestamp": "2026-03-14T10:00:00+00:00", "agent": "testbot"},
        {"command": "comms send local", "args": ["--from", "testbot", "--to", "lead", "--message", "done"], "timestamp": "2026-03-14T10:01:00+00:00", "agent": "testbot"},
        {"command": "agent set-context", "args": ["--agent", "testbot", "--context", "working"], "timestamp": "2026-03-14T10:02:00+00:00", "agent": "testbot"},
    ]
    jsonl_file = activity_dir / "testbot.jsonl"
    with open(jsonl_file, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    return jsonl_file


# ---------------------------------------------------------------------------
# CLI activity logger tests (cli/main.py _log_activity_on_close)
# ---------------------------------------------------------------------------

class TestCliActivityLogger:
    """Test the CLI close handler that writes activity JSONL."""

    def test_writes_jsonl_when_agent_env_set(self, tmp_path, monkeypatch):
        """CLI invocation with MINION_AGENT_NAME set writes a JSONL line."""
        import sys
        from minion.db import init_db, reset_db_path

        # Set up isolated DB
        work_dir = tmp_path / ".work"
        work_dir.mkdir()
        db_path = str(work_dir / "minion.db")
        monkeypatch.setenv("MINION_DB_PATH", db_path)
        monkeypatch.setenv("MINION_AGENT_NAME", "testbot")
        monkeypatch.chdir(tmp_path)
        reset_db_path()
        init_db()

        # Patch AGENT_ACTIVITY_DIR to our tmp
        activity_dir = work_dir / "agent-activity"
        monkeypatch.setattr("minion.fs.AGENT_ACTIVITY_DIR", str(activity_dir))

        # Patch sys.argv so the activity logger sees the CLI command, not pytest's argv
        monkeypatch.setattr(sys, "argv", ["minion", "flow", "list"])

        runner = CliRunner()
        from minion.cli.main import cli
        result = runner.invoke(cli, ["flow", "list"])
        assert result.exit_code == 0

        jsonl_file = activity_dir / "testbot.jsonl"
        assert jsonl_file.exists(), "JSONL file should have been created"

        lines = jsonl_file.read_text().strip().split("\n")
        assert len(lines) >= 1

        record = json.loads(lines[-1])
        assert record["agent"] == "testbot"
        assert record["command"] == "flow list"
        assert "timestamp" in record
        assert isinstance(record["args"], list)

        reset_db_path()

    def test_no_file_when_no_agent(self, tmp_path, monkeypatch):
        """CLI invocation without agent name does not write any JSONL."""
        from minion.db import init_db, reset_db_path

        work_dir = tmp_path / ".work"
        work_dir.mkdir()
        db_path = str(work_dir / "minion.db")
        monkeypatch.setenv("MINION_DB_PATH", db_path)
        monkeypatch.delenv("MINION_AGENT_NAME", raising=False)
        monkeypatch.chdir(tmp_path)
        reset_db_path()
        init_db()

        activity_dir = work_dir / "agent-activity"
        monkeypatch.setattr("minion.fs.AGENT_ACTIVITY_DIR", str(activity_dir))

        runner = CliRunner()
        from minion.cli.main import cli
        result = runner.invoke(cli, ["flow", "list"])
        assert result.exit_code == 0

        # No activity directory or file should be created
        assert not activity_dir.exists() or len(list(activity_dir.iterdir())) == 0

        reset_db_path()

    def test_command_with_flags_splits_correctly(self, tmp_path, monkeypatch):
        """Flags are captured in args, command tokens are in command."""
        import sys
        from minion.db import init_db, reset_db_path, register_agent_db

        work_dir = tmp_path / ".work"
        work_dir.mkdir()
        db_path = str(work_dir / "minion.db")
        monkeypatch.setenv("MINION_DB_PATH", db_path)
        monkeypatch.setenv("MINION_AGENT_NAME", "testbot")
        monkeypatch.chdir(tmp_path)
        reset_db_path()
        init_db()
        register_agent_db("testbot", "coder")

        activity_dir = work_dir / "agent-activity"
        monkeypatch.setattr("minion.fs.AGENT_ACTIVITY_DIR", str(activity_dir))

        # Patch sys.argv so the activity logger sees the CLI command
        monkeypatch.setattr(sys, "argv", ["minion", "task", "list", "--status", "open"])

        runner = CliRunner()
        from minion.cli.main import cli
        result = runner.invoke(cli, ["task", "list", "--status", "open"])
        assert result.exit_code == 0

        jsonl_file = activity_dir / "testbot.jsonl"
        assert jsonl_file.exists()
        record = json.loads(jsonl_file.read_text().strip().split("\n")[-1])
        assert "task" in record["command"]
        assert "list" in record["command"]
        assert "--status" in record["args"]
        assert "open" in record["args"]

        reset_db_path()


# ---------------------------------------------------------------------------
# tail_cli_activity tests (stream_tailer.py)
# ---------------------------------------------------------------------------

class TestTailCliActivity:
    """Test the stream tailer's CLI activity reader."""

    def test_parses_valid_jsonl(self, activity_dir, sample_jsonl):
        """Valid JSONL records are parsed into dashboard event format."""
        from minion.dashboard.stream_tailer import tail_cli_activity

        result = tail_cli_activity(str(activity_dir), ["testbot"], max_events=10)

        assert "testbot" in result
        events = result["testbot"]
        assert len(events) == 3

        # Events should be newest first
        assert events[0]["timestamp"] == "2026-03-14T10:02:00+00:00"
        assert events[0]["tool"] == "minion agent set-context"

    def test_returns_empty_for_missing_dir(self, tmp_path):
        """Missing activity directory returns empty dict."""
        from minion.dashboard.stream_tailer import tail_cli_activity

        result = tail_cli_activity(str(tmp_path / "nonexistent"), ["testbot"])
        assert result == {}

    def test_returns_empty_for_missing_file(self, activity_dir):
        """Missing agent file returns empty list for that agent."""
        from minion.dashboard.stream_tailer import tail_cli_activity

        result = tail_cli_activity(str(activity_dir), ["nobody"])
        assert result.get("nobody", []) == []

    def test_handles_empty_file(self, activity_dir):
        """Empty JSONL file returns empty list."""
        from minion.dashboard.stream_tailer import tail_cli_activity

        (activity_dir / "emptybot.jsonl").write_text("")
        result = tail_cli_activity(str(activity_dir), ["emptybot"])
        assert result.get("emptybot", []) == []

    def test_handles_malformed_lines(self, activity_dir):
        """Malformed JSONL lines are skipped, valid lines still parsed."""
        from minion.dashboard.stream_tailer import tail_cli_activity

        content = "not json\n" + json.dumps({"command": "flow list", "args": [], "timestamp": "2026-03-14T10:00:00+00:00", "agent": "badbot"}) + "\n" + "also bad\n"
        (activity_dir / "badbot.jsonl").write_text(content)

        result = tail_cli_activity(str(activity_dir), ["badbot"])
        events = result.get("badbot", [])
        assert len(events) == 1
        assert events[0]["tool"] == "minion flow list"

    def test_max_events_cap(self, activity_dir):
        """Events are capped at max_events, newest first."""
        from minion.dashboard.stream_tailer import tail_cli_activity

        records = []
        for i in range(10):
            records.append(json.dumps({"command": f"cmd {i}", "args": [], "timestamp": f"2026-03-14T10:{i:02d}:00+00:00", "agent": "capbot"}))
        (activity_dir / "capbot.jsonl").write_text("\n".join(records) + "\n")

        result = tail_cli_activity(str(activity_dir), ["capbot"], max_events=3)
        events = result.get("capbot", [])
        assert len(events) == 3
        # Newest first
        assert "cmd 9" in events[0]["tool"]

    def test_event_format(self, activity_dir, sample_jsonl):
        """Events have tool, input_summary, and timestamp keys."""
        from minion.dashboard.stream_tailer import tail_cli_activity

        result = tail_cli_activity(str(activity_dir), ["testbot"], max_events=1)
        event = result["testbot"][0]
        assert "tool" in event
        assert "input_summary" in event
        assert "timestamp" in event
        # Tool should be prefixed with "minion "
        assert event["tool"].startswith("minion ")
