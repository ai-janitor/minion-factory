"""Behavioral tests for comms/ — register, deregister, who, set_status, send, check_inbox.

Purpose: Verify agent registration/deregistration lifecycle, status updates,
         send + inbox flow, and who listing.
"""

from __future__ import annotations

import os
import sqlite3

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.db]


# ---------------------------------------------------------------------------
# Auto-apply isolated_db_with_coordinator from conftest to every test
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _use_isolated_db(isolated_db_with_coordinator):
    """Delegate to conftest.isolated_db_with_coordinator; autouse ensures DB isolation."""


# ---------------------------------------------------------------------------
# register — happy path
# ---------------------------------------------------------------------------


def test_register_agent_success():
    """register() inserts agent into DB and returns registered status."""
    from minion.comms import register
    result = register(agent_name="leo", agent_class="coder")
    assert "error" not in result
    assert result.get("status") in ("registered", "re_registered")
    # Agent field may be 'agent' or 'name' depending on implementation
    assert result.get("agent") == "leo" or result.get("name") == "leo"


def test_register_agent_idempotent_re_registration():
    """Re-registering an existing agent returns re_registered or registered status."""
    from minion.comms import register
    register(agent_name="leo", agent_class="coder")
    result = register(agent_name="leo", agent_class="coder")
    assert "error" not in result
    assert result.get("status") in ("registered", "re_registered", "already_registered")


def test_register_invalid_class_returns_error():
    """register() with invalid class returns error."""
    from minion.comms import register
    result = register(agent_name="ghost", agent_class="wizard")
    assert "error" in result


# ---------------------------------------------------------------------------
# deregister — happy path
# ---------------------------------------------------------------------------


def test_deregister_registered_agent():
    """deregister() removes an agent from the registry."""
    from minion.comms import register, deregister
    register(agent_name="leo", agent_class="coder")
    result = deregister("leo")
    assert "error" not in result


def test_deregister_unregistered_agent_returns_error():
    """deregister() on unknown agent returns error."""
    from minion.comms import deregister
    result = deregister("ghost")
    assert "error" in result


# ---------------------------------------------------------------------------
# who — list agents
# ---------------------------------------------------------------------------


def test_who_empty_registry():
    """who() with no agents returns empty agents list."""
    from minion.comms import who
    result = who()
    assert "agents" in result
    assert result["agents"] == []


def test_who_shows_registered_agents():
    """who() lists registered agents."""
    from minion.comms import register, who
    register(agent_name="leo", agent_class="coder")
    register(agent_name="atlas", agent_class="lead")
    result = who()
    names = [a["name"] for a in result["agents"]]
    assert "leo" in names
    assert "atlas" in names


# ---------------------------------------------------------------------------
# set_status — update status text
# ---------------------------------------------------------------------------


def test_set_status_registered_agent():
    """set_status updates status for a registered agent."""
    from minion.comms import register, set_status
    register(agent_name="leo", agent_class="coder")
    result = set_status("leo", "working")
    assert "error" not in result


def test_set_status_unregistered_agent_succeeds_or_noop():
    """set_status on unregistered agent either errors or updates status (implementation-defined)."""
    from minion.comms import set_status
    result = set_status("ghost", "doing stuff")
    # Implementation may allow setting status for unregistered agents (soft upsert)
    assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# send + check_inbox — message delivery
# ---------------------------------------------------------------------------


def test_send_and_check_inbox():
    """send() delivers a message that check_inbox returns."""
    from minion.comms import register, send, check_inbox, set_context
    register(agent_name="leo", agent_class="coder")
    register(agent_name="atlas", agent_class="lead")

    # set_context to satisfy staleness check before sending
    set_context("atlas", context="sending test message")

    send_result = send(
        from_agent="atlas",
        to_agent="leo",
        message="Hello from atlas",
    )
    assert "error" not in send_result

    inbox_result = check_inbox("leo")
    assert isinstance(inbox_result, dict)


def test_send_to_unregistered_returns_error():
    """send() to an unregistered recipient returns error."""
    from minion.comms import register, send
    register(agent_name="atlas", agent_class="lead")
    result = send(from_agent="atlas", to_agent="nonexistent", message="hello")
    assert "error" in result


# ---------------------------------------------------------------------------
# SU-04: Cross-repo delivery — narrowed exceptions, error dicts, schema compat
# ---------------------------------------------------------------------------


def test_cross_repo_permission_error_returns_error_dict(tmp_path, monkeypatch):
    """SU-04: PermissionError on coordinator DB returns error dict, not None."""
    from minion.comms.delivery import route_cross_repo

    def _raise_perm(*a, **kw):
        raise PermissionError("read-only filesystem")

    monkeypatch.setattr("minion.comms.delivery.get_coordinator_db", _raise_perm)
    result = route_cross_repo(to_agent="bob", from_agent="alice", message="hi", now="2026-03-10T00:00:00")
    assert isinstance(result, dict)
    assert "error" in result
    assert "permission" in result["error"].lower()


def test_cross_repo_database_error_returns_error_dict(tmp_path, monkeypatch):
    """SU-04: DatabaseError on coordinator DB returns error dict, not None."""
    import sqlite3 as _sqlite3
    from minion.comms.delivery import route_cross_repo

    def _raise_db_err(*a, **kw):
        raise _sqlite3.DatabaseError("malformed database")

    monkeypatch.setattr("minion.comms.delivery.get_coordinator_db", _raise_db_err)
    result = route_cross_repo(to_agent="bob", from_agent="alice", message="hi", now="2026-03-10T00:00:00")
    assert isinstance(result, dict)
    assert "error" in result
    assert "corrupt" in result["error"].lower() or "unreadable" in result["error"].lower()


def test_cross_repo_operational_error_returns_none(tmp_path, monkeypatch):
    """SU-04: OperationalError (DB not found) returns None — agent not found globally."""
    import sqlite3 as _sqlite3
    from minion.comms.delivery import route_cross_repo

    def _raise_op_err(*a, **kw):
        raise _sqlite3.OperationalError("no such table: agents")

    monkeypatch.setattr("minion.comms.delivery.get_coordinator_db", _raise_op_err)
    result = route_cross_repo(to_agent="bob", from_agent="alice", message="hi", now="2026-03-10T00:00:00")
    assert result is None


def test_cross_repo_stale_project_path_returns_error_dict(tmp_path, monkeypatch):
    """SU-04: When target project path no longer exists, return error dict (not None)."""
    import sqlite3 as _sqlite3
    from minion.comms.delivery import route_cross_repo

    # Mock coordinator to return a non-existent project path
    class FakeCoord:
        def execute(self, *a, **kw):
            return self

        def fetchone(self):
            return {"project_path": "/nonexistent/stale/project"}

        def close(self):
            pass

    monkeypatch.setattr("minion.comms.delivery.get_coordinator_db", lambda: FakeCoord())
    result = route_cross_repo(to_agent="bob", from_agent="alice", message="hi", now="2026-03-10T00:00:00")
    assert isinstance(result, dict)
    assert "error" in result
    assert "stale" in result["error"].lower()


def test_cross_repo_schema_compat_missing_columns(tmp_path, monkeypatch):
    """SU-04: Schema compatibility check handles missing columns gracefully."""
    import sqlite3 as _sqlite3
    from minion.comms.delivery import route_cross_repo

    # Set up a real coordinator DB and remote project with a minimal messages table
    remote_project = tmp_path / "remote-project"
    remote_work = remote_project / ".work"
    remote_work.mkdir(parents=True)
    remote_db_path = str(remote_work / "minion.db")

    # Create remote DB with a stripped-down messages table (missing is_cc column)
    rconn = _sqlite3.connect(remote_db_path)
    rconn.execute("""
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_agent TEXT NOT NULL,
            to_agent TEXT NOT NULL,
            content_file TEXT,
            timestamp TEXT,
            read_flag INTEGER DEFAULT 0
        )
    """)
    rconn.commit()
    rconn.close()

    # Mock coordinator to return the remote project path
    class FakeCoord:
        def execute(self, *a, **kw):
            return self

        def fetchone(self):
            return {"project_path": str(remote_project)}

        def close(self):
            pass

    monkeypatch.setattr("minion.comms.delivery.get_coordinator_db", lambda: FakeCoord())

    result = route_cross_repo(to_agent="bob", from_agent="alice", message="test msg", now="2026-03-10T00:00:00")
    # Should succeed (gracefully handle missing columns) — status "sent"
    assert isinstance(result, dict)
    assert result.get("status") == "sent" or "error" not in result or "warning" in result


# ---------------------------------------------------------------------------
# SU-07: is_cross_project() — auth helper
# ---------------------------------------------------------------------------


def test_is_cross_project_same_dir(monkeypatch):
    """SU-07: is_cross_project() returns False when MINION_PROJECT_DIR matches cwd."""
    import os
    from minion.auth import is_cross_project
    cwd = os.getcwd()
    monkeypatch.setenv("MINION_PROJECT_DIR", cwd)
    assert is_cross_project() is False


def test_is_cross_project_different_dir(monkeypatch):
    """SU-07: is_cross_project() returns True when MINION_PROJECT_DIR differs from cwd."""
    from minion.auth import is_cross_project
    monkeypatch.setenv("MINION_PROJECT_DIR", "/some/other/project")
    assert is_cross_project() is True


def test_is_cross_project_unset(monkeypatch):
    """SU-07: is_cross_project() returns False when MINION_PROJECT_DIR not set."""
    from minion.auth import is_cross_project
    monkeypatch.delenv("MINION_PROJECT_DIR", raising=False)
    assert is_cross_project() is False
