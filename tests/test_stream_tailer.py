"""Tests for stream_tailer — tool_use event extraction from stream.jsonl files.

Purpose: Verify that tail_agent_activity correctly parses stream.jsonl files,
    extracts tool_use events, handles missing files, malformed JSONL, and rotation.
"""

import json
import os
import tempfile
from pathlib import Path

import pytest

from minion.dashboard.stream_tailer import (
    tail_agent_activity,
    _extract_tool_events,
    _summarize_input,
    _truncate,
)


@pytest.fixture
def logs_dir(tmp_path):
    """Create a temporary logs directory."""
    return tmp_path


def _write_stream_lines(logs_dir: Path, agent_name: str, lines: list[dict], suffix: str = "") -> Path:
    """Helper: write JSONL lines to a stream file."""
    stream_file = logs_dir / f"{agent_name}.stream.jsonl{suffix}"
    with open(stream_file, "w") as f:
        for line in lines:
            f.write(json.dumps(line) + "\n")
    return stream_file


# --- Basic extraction tests ---

class TestTailAgentActivity:
    """Tests for the main tail_agent_activity function."""

    def test_extract_tool_use_from_assistant_message(self, logs_dir):
        """Tool_use events inside assistant messages should be extracted."""
        lines = [
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Bash", "input": {"command": "git status"}},
            ]}},
        ]
        _write_stream_lines(logs_dir, "agent-a", lines)

        result = tail_agent_activity(logs_dir, ["agent-a"])
        assert "agent-a" in result
        assert len(result["agent-a"]) == 1
        assert result["agent-a"][0]["tool"] == "Bash"
        assert "git status" in result["agent-a"][0]["input_summary"]

    def test_extract_multiple_tool_use_events(self, logs_dir):
        """Multiple tool_use blocks in one message should all be extracted."""
        lines = [
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}},
                {"type": "tool_use", "name": "Read", "input": {"file_path": "/foo/bar.py"}},
            ]}},
        ]
        _write_stream_lines(logs_dir, "agent-b", lines)

        result = tail_agent_activity(logs_dir, ["agent-b"])
        assert len(result["agent-b"]) == 2
        assert result["agent-b"][0]["tool"] == "Read"  # newest first
        assert result["agent-b"][1]["tool"] == "Bash"

    def test_missing_file_returns_empty(self, logs_dir):
        """Agents with no stream file should return an empty list."""
        result = tail_agent_activity(logs_dir, ["nonexistent-agent"])
        assert result["nonexistent-agent"] == []

    def test_empty_file_returns_empty(self, logs_dir):
        """An empty stream file should return an empty list."""
        stream_file = logs_dir / "empty-agent.stream.jsonl"
        stream_file.touch()

        result = tail_agent_activity(logs_dir, ["empty-agent"])
        assert result["empty-agent"] == []

    def test_malformed_jsonl_lines_skipped(self, logs_dir):
        """Malformed JSONL lines should be silently skipped."""
        stream_file = logs_dir / "bad-agent.stream.jsonl"
        with open(stream_file, "w") as f:
            f.write("this is not json\n")
            f.write(json.dumps({"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Grep", "input": {"pattern": "foo"}},
            ]}}) + "\n")
            f.write("{broken json\n")

        result = tail_agent_activity(logs_dir, ["bad-agent"])
        assert len(result["bad-agent"]) == 1
        assert result["bad-agent"][0]["tool"] == "Grep"

    def test_max_events_limit(self, logs_dir):
        """Only the last max_events should be returned."""
        lines = []
        for i in range(10):
            lines.append({"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": f"Tool{i}", "input": {"command": f"cmd-{i}"}},
            ]}})
        _write_stream_lines(logs_dir, "busy-agent", lines)

        result = tail_agent_activity(logs_dir, ["busy-agent"], max_events=3)
        assert len(result["busy-agent"]) == 3
        # Newest first: Tool9, Tool8, Tool7
        assert result["busy-agent"][0]["tool"] == "Tool9"
        assert result["busy-agent"][1]["tool"] == "Tool8"
        assert result["busy-agent"][2]["tool"] == "Tool7"

    def test_non_tool_events_ignored(self, logs_dir):
        """Non-tool_use events (system, user, rate_limit) should be skipped."""
        lines = [
            {"type": "system", "message": "initialized"},
            {"type": "user", "message": {"content": [{"type": "tool_result", "content": "ok"}]}},
            {"type": "rate_limit_event", "message": "rate limited"},
            {"type": "assistant", "message": {"content": [
                {"type": "text", "text": "thinking..."},
            ]}},
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Bash", "input": {"command": "echo hello"}},
            ]}},
        ]
        _write_stream_lines(logs_dir, "mixed-agent", lines)

        result = tail_agent_activity(logs_dir, ["mixed-agent"])
        assert len(result["mixed-agent"]) == 1
        assert result["mixed-agent"][0]["tool"] == "Bash"

    def test_content_block_start_pattern(self, logs_dir):
        """Tool_use events in content_block_start format should be extracted."""
        lines = [
            {"type": "content_block_start", "content_block": {
                "type": "tool_use", "name": "Edit", "input": {"file_path": "/foo.py"},
            }},
        ]
        _write_stream_lines(logs_dir, "block-agent", lines)

        result = tail_agent_activity(logs_dir, ["block-agent"])
        assert len(result["block-agent"]) == 1
        assert result["block-agent"][0]["tool"] == "Edit"

    def test_rotated_file_included(self, logs_dir):
        """Events from rotated .jsonl.1 file should supplement primary file."""
        # Old events in rotated file
        old_lines = [
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "OldTool", "input": {"command": "old"}},
            ]}},
        ]
        _write_stream_lines(logs_dir, "rotated-agent", old_lines, suffix=".1")

        # New events in primary file — only 1 event, less than max_events=5
        new_lines = [
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "NewTool", "input": {"command": "new"}},
            ]}},
        ]
        _write_stream_lines(logs_dir, "rotated-agent", new_lines)

        result = tail_agent_activity(logs_dir, ["rotated-agent"], max_events=5)
        assert len(result["rotated-agent"]) == 2
        # Newest first
        assert result["rotated-agent"][0]["tool"] == "NewTool"
        assert result["rotated-agent"][1]["tool"] == "OldTool"

    def test_multiple_agents(self, logs_dir):
        """Multiple agents should each get their own results."""
        _write_stream_lines(logs_dir, "alpha", [
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "AlphaTool", "input": {}},
            ]}},
        ])
        _write_stream_lines(logs_dir, "beta", [
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "BetaTool", "input": {}},
            ]}},
        ])

        result = tail_agent_activity(logs_dir, ["alpha", "beta"])
        assert result["alpha"][0]["tool"] == "AlphaTool"
        assert result["beta"][0]["tool"] == "BetaTool"


# --- Input summarization tests ---

class TestSummarizeInput:
    """Tests for the _summarize_input helper."""

    def test_bash_command(self):
        assert _summarize_input({"command": "git status"}) == "git status"

    def test_file_path(self):
        result = _summarize_input({"file_path": "/foo/bar.py"})
        assert "file_path: /foo/bar.py" in result

    def test_grep_pattern(self):
        result = _summarize_input({"pattern": "def main"})
        assert "pattern: def main" in result

    def test_long_input_truncated(self):
        long_cmd = "x" * 200
        result = _summarize_input({"command": long_cmd}, max_len=50)
        assert len(result) == 50
        assert result.endswith("...")

    def test_none_input(self):
        assert _summarize_input(None) == ""

    def test_string_input(self):
        assert _summarize_input("hello world") == "hello world"

    def test_dict_fallback_json(self):
        result = _summarize_input({"foo": "bar", "baz": 42})
        assert "foo" in result
        assert "bar" in result


class TestTruncate:
    """Tests for the _truncate helper."""

    def test_short_string_unchanged(self):
        assert _truncate("hello", 10) == "hello"

    def test_long_string_truncated(self):
        result = _truncate("a" * 100, 20)
        assert len(result) == 20
        assert result.endswith("...")

    def test_newlines_replaced(self):
        result = _truncate("line1\nline2\nline3", 100)
        assert "\n" not in result
        assert "line1 line2 line3" == result
