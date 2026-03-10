"""Behavioral tests for filesafety.py — claim_file, release_file, get_claims.

Purpose: Verify file claiming enforces single-owner semantics, waitlist behavior
         on contention, and release mechanics.
"""

from __future__ import annotations

import os
import sqlite3

import pytest

from minion.db import init_db, reset_db_path

pytestmark = [pytest.mark.integration, pytest.mark.db]


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


def _register_agent(name: str, cls: str = "coder") -> None:
    db_path = os.environ["MINION_DB_PATH"]
    now = "2026-03-09T00:00:00"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT OR REPLACE INTO agents (name, agent_class, registered_at, last_seen) VALUES (?, ?, ?, ?)",
        (name, cls, now, now),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# claim_file — happy path
# ---------------------------------------------------------------------------


def test_claim_file_success(tmp_path):
    """Registered agent can claim an unclaimed file."""
    _register_agent("leo")
    from minion.filesafety import claim_file
    file_path = str(tmp_path / "src" / "auth.py")
    result = claim_file("leo", file_path)
    assert result["status"] == "claimed"
    assert result["by"] == "leo"


def test_claim_file_idempotent_same_agent(tmp_path):
    """Claiming a file twice by the same agent returns already_claimed."""
    _register_agent("leo")
    from minion.filesafety import claim_file
    file_path = str(tmp_path / "foo.py")
    claim_file("leo", file_path)
    result = claim_file("leo", file_path)
    assert result["status"] == "already_claimed"


# ---------------------------------------------------------------------------
# claim_file — unregistered agent
# ---------------------------------------------------------------------------


def test_claim_file_unregistered_agent_blocked(tmp_path):
    """Unregistered agent cannot claim a file."""
    from minion.filesafety import claim_file
    result = claim_file("ghost", str(tmp_path / "x.py"))
    assert "error" in result
    assert "not registered" in result["error"].lower() or "BLOCKED" in result["error"]


# ---------------------------------------------------------------------------
# claim_file — contention: second agent goes to waitlist
# ---------------------------------------------------------------------------


def test_claim_file_contention_adds_to_waitlist(tmp_path):
    """Second agent claiming an already-claimed file is added to waitlist."""
    _register_agent("leo")
    _register_agent("tifa")
    from minion.filesafety import claim_file
    file_path = str(tmp_path / "claimed.py")
    claim_file("leo", file_path)
    result = claim_file("tifa", file_path)
    assert "error" in result
    assert "waitlist" in result["error"].lower() or "waitlist" in result.get("error", "").lower()


# ---------------------------------------------------------------------------
# release_file — happy path
# ---------------------------------------------------------------------------


def test_release_file_by_owner(tmp_path):
    """File owner can release their claim."""
    _register_agent("leo")
    from minion.filesafety import claim_file, release_file
    file_path = str(tmp_path / "owned.py")
    claim_file("leo", file_path)
    result = release_file("leo", file_path)
    assert result.get("status") in ("released", "ok") or "error" not in result


def test_release_file_not_claimed_returns_error_or_noop(tmp_path):
    """Releasing an unclaimed file returns error or noop."""
    _register_agent("leo")
    from minion.filesafety import release_file
    result = release_file("leo", str(tmp_path / "not_claimed.py"))
    # should not crash — either error or noop status
    assert isinstance(result, dict)


def test_release_file_by_non_owner_blocked(tmp_path):
    """Non-owner cannot release another agent's claim."""
    _register_agent("leo")
    _register_agent("tifa")
    from minion.filesafety import claim_file, release_file
    file_path = str(tmp_path / "leos_file.py")
    claim_file("leo", file_path)
    result = release_file("tifa", file_path)
    # should be blocked unless force=True
    assert "error" in result or result.get("status") not in ("released", "ok")


# ---------------------------------------------------------------------------
# get_claims — list active claims
# ---------------------------------------------------------------------------


def test_get_claims_empty_initially():
    """get_claims returns empty list when no files are claimed."""
    from minion.filesafety import get_claims
    result = get_claims()
    assert isinstance(result, (list, dict))
    # Either an empty list or dict with empty claims key
    if isinstance(result, list):
        assert result == []
    else:
        assert result.get("claims", []) == []


def test_get_claims_shows_active_claim(tmp_path):
    """get_claims shows files claimed by registered agents."""
    _register_agent("leo")
    from minion.filesafety import claim_file, get_claims
    file_path = str(tmp_path / "active.py")
    claim_file("leo", file_path)
    result = get_claims()
    # result is list or dict
    if isinstance(result, list):
        paths = [r.get("file_path") or r.get("file") for r in result]
    else:
        claims = result.get("claims", [])
        paths = [c.get("file_path") or c.get("file") for c in claims]
    assert any(file_path in (p or "") for p in paths)
