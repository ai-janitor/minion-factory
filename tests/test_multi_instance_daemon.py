"""Tests for multi-instance daemon spawn isolation.

Validates that multiple instances of the same agent template get isolated
PID files, state files, log files, and poll processes.

Requirement: 246 (multi-instance-daemon-spawns-with-unique-instance)
Task: 244
"""
from __future__ import annotations

import json
import os
import tempfile

import pytest


# ---------------------------------------------------------------------------
# instance.py — resolve_file_key
# ---------------------------------------------------------------------------

class TestResolveFileKey:
    """resolve_file_key() returns the correct file-system key."""

    def test_bare_name_no_instance(self):
        from minion.instance import resolve_file_key
        assert resolve_file_key("redmage-jr") == "redmage-jr"

    def test_bare_name_none_instance(self):
        from minion.instance import resolve_file_key
        assert resolve_file_key("redmage-jr", None) == "redmage-jr"

    def test_bare_name_empty_instance(self):
        from minion.instance import resolve_file_key
        assert resolve_file_key("redmage-jr", "") == "redmage-jr"

    def test_instance_id_suffix(self):
        from minion.instance import resolve_file_key
        assert resolve_file_key("redmage-jr", "2") == "redmage-jr-2"

    def test_instance_id_larger_number(self):
        from minion.instance import resolve_file_key
        assert resolve_file_key("redmage-jr", "15") == "redmage-jr-15"


# ---------------------------------------------------------------------------
# instance.py — next_instance_id
# ---------------------------------------------------------------------------

class TestNextInstanceId:
    """next_instance_id() scans existing files and returns the next suffix."""

    def test_no_existing_files_returns_2(self, tmp_path):
        """When no runtime files exist, the next instance is 2 (bare name = 1)."""
        from minion.instance import next_instance_id
        assert next_instance_id("agent-a", str(tmp_path)) == "2"

    def test_bare_pidfile_exists_returns_2(self, tmp_path):
        """When only the bare-name PID file exists, next is 2."""
        from minion.instance import next_instance_id
        poll_dir = tmp_path / ".work" / ".minion-poll"
        poll_dir.mkdir(parents=True)
        (poll_dir / "agent-a.pid").write_text("12345")
        assert next_instance_id("agent-a", str(tmp_path)) == "2"

    def test_instance_2_exists_returns_3(self, tmp_path):
        """When instance-2 PID file exists, next is 3."""
        from minion.instance import next_instance_id
        poll_dir = tmp_path / ".work" / ".minion-poll"
        poll_dir.mkdir(parents=True)
        (poll_dir / "agent-a.pid").write_text("12345")
        (poll_dir / "agent-a-2.pid").write_text("12346")
        assert next_instance_id("agent-a", str(tmp_path)) == "3"

    def test_gap_in_sequence_fills_gap(self, tmp_path):
        """When instances 1, 2, 4 exist, next is 3 (fills the gap)."""
        from minion.instance import next_instance_id
        poll_dir = tmp_path / ".work" / ".minion-poll"
        poll_dir.mkdir(parents=True)
        (poll_dir / "agent-a.pid").write_text("12345")
        (poll_dir / "agent-a-2.pid").write_text("12346")
        (poll_dir / "agent-a-4.pid").write_text("12348")
        assert next_instance_id("agent-a", str(tmp_path)) == "3"

    def test_state_files_also_scanned(self, tmp_path):
        """Instance IDs from state files are also detected."""
        from minion.instance import next_instance_id
        state_dir = tmp_path / ".minion-swarm" / "state"
        state_dir.mkdir(parents=True)
        (state_dir / "agent-a.json").write_text("{}")
        (state_dir / "agent-a-2.json").write_text("{}")
        assert next_instance_id("agent-a", str(tmp_path)) == "3"

    def test_mixed_pid_and_state_files(self, tmp_path):
        """Instance IDs from both PID and state files are merged."""
        from minion.instance import next_instance_id
        poll_dir = tmp_path / ".work" / ".minion-poll"
        poll_dir.mkdir(parents=True)
        (poll_dir / "agent-a.pid").write_text("12345")
        (poll_dir / "agent-a-2.pid").write_text("12346")

        state_dir = tmp_path / ".minion-swarm" / "state"
        state_dir.mkdir(parents=True)
        (state_dir / "agent-a-3.json").write_text("{}")

        assert next_instance_id("agent-a", str(tmp_path)) == "4"

    def test_unrelated_agent_files_ignored(self, tmp_path):
        """Files for other agents are not counted."""
        from minion.instance import next_instance_id
        poll_dir = tmp_path / ".work" / ".minion-poll"
        poll_dir.mkdir(parents=True)
        (poll_dir / "other-agent.pid").write_text("99999")
        (poll_dir / "other-agent-2.pid").write_text("99998")
        # Only bare name of target agent
        (poll_dir / "agent-a.pid").write_text("12345")
        assert next_instance_id("agent-a", str(tmp_path)) == "2"


# ---------------------------------------------------------------------------
# instance.py — is_instance_alive
# ---------------------------------------------------------------------------

class TestIsInstanceAlive:
    """is_instance_alive() checks poll PID and state files for running processes."""

    def test_no_files_returns_false(self, tmp_path):
        from minion.instance import is_instance_alive
        assert is_instance_alive("agent-a", None, str(tmp_path)) is False

    def test_stale_pid_returns_false(self, tmp_path):
        """PID file with a dead PID returns False."""
        from minion.instance import is_instance_alive
        poll_dir = tmp_path / ".work" / ".minion-poll"
        poll_dir.mkdir(parents=True)
        # PID 999999999 is very unlikely to be alive
        (poll_dir / "agent-a.pid").write_text("999999999")
        assert is_instance_alive("agent-a", None, str(tmp_path)) is False

    def test_alive_pid_returns_true(self, tmp_path):
        """PID file with our own PID returns True (we are alive)."""
        from minion.instance import is_instance_alive
        poll_dir = tmp_path / ".work" / ".minion-poll"
        poll_dir.mkdir(parents=True)
        (poll_dir / "agent-a.pid").write_text(str(os.getpid()))
        assert is_instance_alive("agent-a", None, str(tmp_path)) is True

    def test_instance_id_uses_qualified_path(self, tmp_path):
        """With instance_id, checks the instance-qualified PID file."""
        from minion.instance import is_instance_alive
        poll_dir = tmp_path / ".work" / ".minion-poll"
        poll_dir.mkdir(parents=True)
        # Bare name NOT alive
        (poll_dir / "agent-a.pid").write_text("999999999")
        # Instance-2 IS alive
        (poll_dir / "agent-a-2.pid").write_text(str(os.getpid()))
        assert is_instance_alive("agent-a", "2", str(tmp_path)) is True
        assert is_instance_alive("agent-a", "3", str(tmp_path)) is False

    def test_state_file_alive_pid(self, tmp_path):
        """State file with an alive PID returns True."""
        from minion.instance import is_instance_alive
        state_dir = tmp_path / ".minion-swarm" / "state"
        state_dir.mkdir(parents=True)
        (state_dir / "agent-a.json").write_text(json.dumps({"pid": os.getpid()}))
        assert is_instance_alive("agent-a", None, str(tmp_path)) is True


# ---------------------------------------------------------------------------
# polling.py — _poll_pidfile with instance_id
# ---------------------------------------------------------------------------

class TestPollPidfileInstanceId:
    """_poll_pidfile() returns different paths based on instance_id."""

    def _patch_runtime_dir(self, monkeypatch, fake_dir="/fake/project/.work"):
        """Patch get_runtime_dir at all import sites."""
        import minion.db as _db_pkg
        import minion.db.connection as _conn
        monkeypatch.setattr(_conn, "get_runtime_dir", lambda: fake_dir)
        monkeypatch.setattr(_db_pkg, "get_runtime_dir", lambda: fake_dir)

    def test_no_instance_uses_bare_name(self, monkeypatch):
        from minion.polling import _poll_pidfile
        self._patch_runtime_dir(monkeypatch)
        path = _poll_pidfile("myagent")
        assert path == "/fake/project/.work/.minion-poll/myagent.pid"

    def test_none_instance_same_as_no_instance(self, monkeypatch):
        from minion.polling import _poll_pidfile
        self._patch_runtime_dir(monkeypatch)
        assert _poll_pidfile("myagent", None) == _poll_pidfile("myagent")

    def test_instance_id_uses_qualified_name(self, monkeypatch):
        from minion.polling import _poll_pidfile
        self._patch_runtime_dir(monkeypatch)
        path = _poll_pidfile("myagent", "3")
        assert path == "/fake/project/.work/.minion-poll/myagent-3.pid"

    def test_different_instances_different_paths(self, monkeypatch):
        from minion.polling import _poll_pidfile
        self._patch_runtime_dir(monkeypatch)
        assert _poll_pidfile("agent", "2") != _poll_pidfile("agent", "3")
        assert _poll_pidfile("agent", "2") != _poll_pidfile("agent")


# ---------------------------------------------------------------------------
# Backward compatibility — instance_id=None matches old behavior
# ---------------------------------------------------------------------------

class TestBackwardCompatibility:
    """When instance_id is None/empty, all paths match pre-instance behavior."""

    def test_resolve_file_key_backward_compat(self):
        from minion.instance import resolve_file_key
        # These should all return the bare agent name
        assert resolve_file_key("agent") == "agent"
        assert resolve_file_key("agent", None) == "agent"
        assert resolve_file_key("agent", "") == "agent"

    def test_poll_pidfile_backward_compat(self, monkeypatch):
        from minion.polling import _poll_pidfile
        import minion.db as _db_pkg
        import minion.db.connection as _conn
        monkeypatch.setattr(_conn, "get_runtime_dir", lambda: "/fake/.work")
        monkeypatch.setattr(_db_pkg, "get_runtime_dir", lambda: "/fake/.work")
        # Old behavior: _poll_pidfile("agent") -> /fake/.work/.minion-poll/agent.pid
        old_style = "/fake/.work/.minion-poll/agent.pid"
        assert _poll_pidfile("agent") == old_style
        assert _poll_pidfile("agent", None) == old_style
        assert _poll_pidfile("agent", "") == old_style

    def test_is_poll_alive_backward_compat(self, tmp_path):
        from minion.polling import is_poll_alive
        poll_dir = tmp_path / ".work" / ".minion-poll"
        poll_dir.mkdir(parents=True)
        (poll_dir / "agent.pid").write_text(str(os.getpid()))
        # Old signature: is_poll_alive(agent, project_path)
        assert is_poll_alive("agent", str(tmp_path)) is True
        # New signature with None: same result
        assert is_poll_alive("agent", str(tmp_path), None) is True


# ---------------------------------------------------------------------------
# _extract_instance_number — edge cases
# ---------------------------------------------------------------------------

class TestExtractInstanceNumber:
    """_extract_instance_number correctly parses instance numbers from filenames."""

    def test_bare_name(self):
        from minion.instance import _extract_instance_number
        s: set[int] = set()
        _extract_instance_number("agent.pid", "agent", ".pid", s)
        assert s == {1}

    def test_numeric_suffix(self):
        from minion.instance import _extract_instance_number
        s: set[int] = set()
        _extract_instance_number("agent-5.pid", "agent", ".pid", s)
        assert s == {5}

    def test_non_numeric_suffix_ignored(self):
        from minion.instance import _extract_instance_number
        s: set[int] = set()
        _extract_instance_number("agent-foo.pid", "agent", ".pid", s)
        assert s == set()

    def test_different_agent_ignored(self):
        from minion.instance import _extract_instance_number
        s: set[int] = set()
        _extract_instance_number("other-agent.pid", "agent", ".pid", s)
        assert s == set()

    def test_agent_name_with_hyphens(self):
        """Agent names containing hyphens don't cause false positives."""
        from minion.instance import _extract_instance_number
        s: set[int] = set()
        _extract_instance_number("red-mage-jr-2.pid", "red-mage-jr", ".pid", s)
        assert s == {2}

    def test_json_suffix(self):
        from minion.instance import _extract_instance_number
        s: set[int] = set()
        _extract_instance_number("agent-3.json", "agent", ".json", s)
        assert s == {3}
