"""Behavioral tests for output.py — JSON, human, compact formatting modes.

Purpose: Verify output() and _format_compact() produce correct output
         across all formatting modes and handle edge cases (error key, empty data).
"""

from __future__ import annotations

import json

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _capture(capsys, fn, *args, **kwargs):
    """Run fn(*args, **kwargs), return (stdout, stderr)."""
    try:
        fn(*args, **kwargs)
    except SystemExit:
        pass
    captured = capsys.readouterr()
    return captured.out, captured.err


# ---------------------------------------------------------------------------
# output() — default JSON mode
# ---------------------------------------------------------------------------


def test_output_human_mode_default(capsys):
    """output() with no flags prints human-readable text to stdout (new default)."""
    from minion.output import output
    data = {"status": "ok", "agent": "leo"}
    out, _ = _capture(capsys, output, data)
    assert "status: ok" in out
    assert "agent: leo" in out


def test_output_json_mode_explicit(capsys):
    """output() with human=False prints valid JSON to stdout."""
    from minion.output import output
    data = {"status": "ok", "agent": "leo"}
    out, _ = _capture(capsys, output, data, human=False)
    parsed = json.loads(out)
    assert parsed["status"] == "ok"
    assert parsed["agent"] == "leo"


def test_output_error_key_exits_nonzero(capsys):
    """output() with 'error' key in data calls sys.exit(1)."""
    from minion.output import output
    with pytest.raises(SystemExit) as exc_info:
        output({"error": "something went wrong"})
    assert exc_info.value.code == 1


def test_output_error_key_prints_json(capsys):
    """output() error path still prints JSON to stderr."""
    from minion.output import output
    try:
        output({"error": "bad thing"})
    except SystemExit:
        pass
    _, err = capsys.readouterr()
    parsed = json.loads(err)
    assert "error" in parsed


# ---------------------------------------------------------------------------
# output() — human mode
# ---------------------------------------------------------------------------


def test_output_human_mode_flat_values(capsys):
    """human=True prints key: value lines for scalar values."""
    from minion.output import output
    data = {"status": "registered", "agent": "tifa"}
    out, _ = _capture(capsys, output, data, human=True)
    assert "status: registered" in out
    assert "agent: tifa" in out


def test_output_human_mode_nested_values_as_json(capsys):
    """human=True prints nested dicts/lists as JSON."""
    from minion.output import output
    data = {"tools": [{"command": "minion who", "description": "list agents"}]}
    out, _ = _capture(capsys, output, data, human=True)
    assert "tools:" in out
    assert "minion who" in out


# ---------------------------------------------------------------------------
# output() — compact mode
# ---------------------------------------------------------------------------


def test_output_compact_mode_status_agent(capsys):
    """compact=True formats status + agent on one line."""
    from minion.output import output
    data = {"status": "registered", "agent": "leo", "class": "coder"}
    out, _ = _capture(capsys, output, data, compact=True)
    assert "registered: leo (coder" in out


def test_output_compact_mode_empty_falls_back_to_json(capsys):
    """compact=True with unrecognized fields falls back to JSON."""
    from minion.output import output
    data = {"foo": "bar", "baz": 42}
    out, _ = _capture(capsys, output, data, compact=True)
    # should produce valid JSON fallback
    parsed = json.loads(out)
    assert parsed["foo"] == "bar"


# ---------------------------------------------------------------------------
# _format_compact — internal formatter
# ---------------------------------------------------------------------------


def test_format_compact_with_tools():
    """_format_compact renders tools table when tools list is present."""
    from minion.output import _format_compact
    data = {
        "status": "registered",
        "agent": "leo",
        "class": "coder",
        "tools": [
            {"command": "minion who", "description": "List agents"},
            {"command": "minion send", "description": "Send message"},
        ],
    }
    result = _format_compact(data)
    assert "Commands:" in result
    assert "minion who" in result
    assert "minion send" in result


def test_format_compact_with_playbook():
    """_format_compact renders playbook steps."""
    from minion.output import _format_compact
    data = {
        "status": "ok",
        "agent": "leo",
        "playbook": {"type": "daemon", "steps": ["Step A", "Step B"]},
    }
    result = _format_compact(data)
    assert "Playbook:" in result
    assert "Step A" in result


def test_format_compact_no_recognized_fields_returns_json():
    """_format_compact with no recognized fields returns JSON string."""
    from minion.output import _format_compact
    data = {"arbitrary": "value"}
    result = _format_compact(data)
    parsed = json.loads(result)
    assert parsed["arbitrary"] == "value"
