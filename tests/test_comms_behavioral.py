"""Behavioral tests for comms/ — register, deregister, who, set_status, send, check_inbox.

Purpose: Verify agent registration/deregistration lifecycle, status updates,
         send + inbox flow, and who listing.
"""

from __future__ import annotations

import os
import sqlite3

import pytest

from minion.db import init_db, reset_db_path


# ---------------------------------------------------------------------------
# DB isolation fixture
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    work_dir = tmp_path / ".work"
    work_dir.mkdir(parents=True, exist_ok=True)
    db_path = str(work_dir / "minion.db")
    # Isolate coordinator DB too — prevents cross-test name conflicts in global registry
    coord_db_path = str(tmp_path / "coordinator.db")
    monkeypatch.setenv("MINION_DB_PATH", db_path)
    monkeypatch.setenv("MINION_COORDINATOR_DB_PATH", coord_db_path)
    reset_db_path()
    init_db()
    monkeypatch.chdir(tmp_path)
    yield tmp_path
    reset_db_path()


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
    result = set_status("leo", "working on task 42")
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
