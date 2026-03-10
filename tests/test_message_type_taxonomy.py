"""Tests for message type taxonomy — typed messages with filtering.

Purpose: Verify backlog #66 — msg_type column, send with type, inbox filtering.
Responsibility: Test schema migration, send with msg_type, check_inbox filtering.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    """Set up a fresh minion DB in a temp directory."""
    db_path = str(tmp_path / ".work" / "minion.db")
    monkeypatch.setenv("MINION_DB_PATH", db_path)

    from minion.db.connection import reset_db_path, init_db
    reset_db_path()
    init_db()
    return db_path


def _register_agents(fresh_db):
    """Helper to register test agents with fresh context (avoids staleness block)."""
    from minion.db.helpers import register_agent_db, now_iso
    from minion.db.connection import get_db
    register_agent_db("sender", "coder")
    register_agent_db("receiver", "coder")
    # Set context_updated_at to avoid staleness blocks in tests
    conn = get_db()
    now = now_iso()
    conn.execute("UPDATE agents SET context_updated_at = ?, last_inbox_check = ? WHERE name IN ('sender', 'receiver')", (now, now))
    conn.commit()
    conn.close()


# ── Schema ────────────────────────────────────────────────────────────


def test_msg_type_column_exists(fresh_db):
    """Messages table has msg_type column after migration."""
    from minion.db.connection import get_db
    conn = get_db()
    cols = {row[1] for row in conn.execute("PRAGMA table_info(messages)").fetchall()}
    conn.close()
    assert "msg_type" in cols


# ── Send with msg_type ────────────────────────────────────────────────


def test_send_with_msg_type(fresh_db):
    """Send a typed message and verify msg_type is stored."""
    _register_agents(fresh_db)
    from minion.comms.send import send
    result = send("sender", "receiver", "orders here", msg_type="order")
    assert result.get("msg_type") == "order"
    assert result.get("status") == "sent"


def test_send_with_invalid_msg_type(fresh_db):
    """Send with invalid msg_type raises assertion."""
    _register_agents(fresh_db)
    from minion.comms.send import send
    with pytest.raises(AssertionError, match="Invalid msg_type"):
        send("sender", "receiver", "test", msg_type="invalid_type")


def test_send_without_msg_type(fresh_db):
    """Send without msg_type works (backward compat)."""
    _register_agents(fresh_db)
    from minion.comms.send import send
    result = send("sender", "receiver", "plain message")
    assert "msg_type" not in result  # None values not included
    assert result.get("status") == "sent"


# ── Inbox filtering ──────────────────────────────────────────────────


def test_inbox_filter_by_msg_type(fresh_db):
    """check_inbox with msg_type filters messages."""
    _register_agents(fresh_db)
    from minion.comms.send import send
    from minion.comms.inbox import check_inbox

    # Clear inbox first
    check_inbox("receiver")

    # Send typed messages
    send("sender", "receiver", "order msg", msg_type="order")
    send("sender", "receiver", "sitrep msg", msg_type="sitrep")
    send("sender", "receiver", "untyped msg")

    # Filter by order type
    result = check_inbox("receiver", msg_type="order")
    messages = result.get("messages", [])
    assert len(messages) == 1
    assert messages[0].get("msg_type") == "order"


def test_inbox_no_filter_returns_all(fresh_db):
    """check_inbox without msg_type returns all messages."""
    _register_agents(fresh_db)
    from minion.comms.send import send
    from minion.comms.inbox import check_inbox

    # Clear inbox first
    check_inbox("receiver")

    send("sender", "receiver", "order msg", msg_type="order")
    send("sender", "receiver", "plain msg")

    result = check_inbox("receiver")
    messages = result.get("messages", [])
    assert len(messages) == 2


# ── Valid msg_type values ─────────────────────────────────────────────


@pytest.mark.parametrize("msg_type", ["order", "sitrep", "query", "response", "alert", "system"])
def test_all_valid_msg_types(fresh_db, msg_type):
    """All defined message types are accepted."""
    _register_agents(fresh_db)
    from minion.comms.send import send
    # Clear inbox
    from minion.comms.inbox import check_inbox
    check_inbox("receiver")

    result = send("sender", "receiver", f"test {msg_type}", msg_type=msg_type)
    assert result.get("status") == "sent"
    assert result.get("msg_type") == msg_type
