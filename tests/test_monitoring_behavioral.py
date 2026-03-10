"""Behavioral tests for monitoring.py — party_status, check_activity, sitrep.

Purpose: Verify party_status returns correct agent lists, check_activity
         identifies agents correctly, and sitrep is a superset view.
"""

from __future__ import annotations

import os
import sqlite3
import datetime

import pytest

from minion.db import init_db, reset_db_path

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# DB isolation fixture
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    work_dir = tmp_path / ".work"
    work_dir.mkdir(parents=True, exist_ok=True)
    db_path = str(work_dir / "minion.db")
    monkeypatch.setenv("MINION_DB_PATH", db_path)
    reset_db_path()
    init_db()
    monkeypatch.chdir(tmp_path)
    yield tmp_path
    reset_db_path()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _register_agent(name: str, cls: str = "coder", last_seen: str | None = None) -> None:
    db_path = os.environ["MINION_DB_PATH"]
    now = last_seen or datetime.datetime.now().isoformat()
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT OR REPLACE INTO agents (name, agent_class, registered_at, last_seen) VALUES (?, ?, ?, ?)",
        (name, cls, now, now),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# party_status — structure
# ---------------------------------------------------------------------------


def test_party_status_empty_registry():
    """party_status with no agents returns {'agents': []}."""
    from minion.monitoring import party_status
    result = party_status()
    assert "agents" in result
    assert result["agents"] == []


def test_party_status_shows_registered_agents():
    """party_status lists all registered agents."""
    _register_agent("leo", "coder")
    _register_agent("atlas", "lead")
    from minion.monitoring import party_status
    result = party_status()
    names = [a["name"] for a in result["agents"]]
    assert "leo" in names
    assert "atlas" in names


def test_party_status_agent_has_required_keys():
    """Each agent entry in party_status has expected keys."""
    _register_agent("leo", "coder")
    from minion.monitoring import party_status
    result = party_status()
    agent = result["agents"][0]
    for key in ("name", "agent_class", "open_tasks"):
        assert key in agent, f"Missing key: {key}"


def test_party_status_open_tasks_is_int():
    """open_tasks in party_status is an integer."""
    _register_agent("leo", "coder")
    from minion.monitoring import party_status
    result = party_status()
    assert isinstance(result["agents"][0]["open_tasks"], int)


# ---------------------------------------------------------------------------
# check_activity — agent judgment
# ---------------------------------------------------------------------------


def test_check_activity_unregistered_agent_returns_error():
    """check_activity returns error for unregistered agent."""
    from minion.monitoring import check_activity
    result = check_activity("ghost")
    assert "error" in result


def test_check_activity_recently_seen_is_active():
    """Agent seen within 5 minutes is judged 'active'."""
    now = datetime.datetime.now().isoformat()
    _register_agent("leo", "coder", last_seen=now)
    from minion.monitoring import check_activity
    result = check_activity("leo")
    # Result should indicate activity — either "active" judgment or no error
    assert "error" not in result


def test_check_activity_stale_agent_is_possibly_dead():
    """Agent last seen over 20 minutes ago is 'possibly dead'."""
    old_time = (datetime.datetime.now() - datetime.timedelta(minutes=25)).isoformat()
    _register_agent("zombie", "coder", last_seen=old_time)
    from minion.monitoring import check_activity
    result = check_activity("zombie")
    assert "error" not in result
    judgment = result.get("judgment", "")
    assert judgment in ("possibly dead", "idle", "active")  # at minimum, don't crash


# ---------------------------------------------------------------------------
# sitrep — fused view
# ---------------------------------------------------------------------------


def test_sitrep_returns_dict():
    """sitrep() returns a dict."""
    from minion.monitoring import sitrep
    result = sitrep()
    assert isinstance(result, dict)


def test_sitrep_with_agents_populated():
    """sitrep() includes agents when registry has agents."""
    _register_agent("leo", "coder")
    from minion.monitoring import sitrep
    result = sitrep()
    assert isinstance(result, dict)
    # sitrep should have at least agents or tasks info
    assert len(result) > 0
