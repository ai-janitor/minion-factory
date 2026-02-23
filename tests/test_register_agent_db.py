"""Tests for register_agent_db() DB isolation (T83)."""

from __future__ import annotations

import os

import pytest

from minion.db import init_db, reset_db_path, register_agent_db, get_db


# ---------------------------------------------------------------------------
# DB isolation fixture
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Each test gets its own .work/ dir and isolated SQLite DB."""
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
# T83 — register_agent_db() inserts row visible via get_db()
# ---------------------------------------------------------------------------


def test_register_agent_db_row_visible(tmp_path):
    """register_agent_db inserts an agent row that is readable via get_db()."""
    register_agent_db("agent-alpha", "coder", model="claude-sonnet-4-6")

    conn = get_db()
    row = conn.execute(
        "SELECT name, agent_class, model FROM agents WHERE name = ?",
        ("agent-alpha",),
    ).fetchone()
    conn.close()

    assert row is not None
    assert row["name"] == "agent-alpha"
    assert row["agent_class"] == "coder"
    assert row["model"] == "claude-sonnet-4-6"


def test_register_agent_db_lead_class(tmp_path):
    """register_agent_db correctly stores the lead agent_class."""
    register_agent_db("lead-one", "lead")

    conn = get_db()
    row = conn.execute(
        "SELECT agent_class FROM agents WHERE name = ?", ("lead-one",)
    ).fetchone()
    conn.close()

    assert row is not None
    assert row["agent_class"] == "lead"


def test_register_agent_db_replace_semantics(tmp_path):
    """Calling register_agent_db twice for the same name updates, not duplicates."""
    register_agent_db("agent-beta", "coder")
    register_agent_db("agent-beta", "lead")  # Upsert to lead

    conn = get_db()
    rows = conn.execute(
        "SELECT COUNT(*) as cnt, agent_class FROM agents WHERE name = ?",
        ("agent-beta",),
    ).fetchone()
    conn.close()

    assert rows["cnt"] == 1
    assert rows["agent_class"] == "lead"


# ---------------------------------------------------------------------------
# T83 — no filesystem writes (no inbox dirs, no onboarding files)
# ---------------------------------------------------------------------------


def test_register_agent_db_no_filesystem_writes(tmp_path):
    """register_agent_db does not create inbox directories or onboarding files."""
    work_dir = tmp_path / ".work"

    # Snapshot filesystem before
    before = _snapshot(work_dir)

    register_agent_db("agent-gamma", "oracle")

    after = _snapshot(work_dir)
    new_entries = after - before

    assert new_entries == set(), (
        f"register_agent_db wrote unexpected files/dirs: {new_entries}"
    )


def test_register_agent_db_no_inbox_dir(tmp_path):
    """register_agent_db does not create an inbox directory for the agent."""
    work_dir = tmp_path / ".work"

    register_agent_db("agent-delta", "coder")

    # Check common inbox locations — none should exist
    inbox_candidates = [
        work_dir / "inbox" / "agent-delta",
        work_dir / "agent-delta" / "inbox",
        work_dir / "comms" / "agent-delta",
    ]
    for path in inbox_candidates:
        assert not path.exists(), f"Unexpected directory created: {path}"


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------


def _snapshot(directory) -> set:
    """Recursively list all paths under directory as a set of strings."""
    result = set()
    for dirpath, dirnames, filenames in os.walk(str(directory)):
        for fname in filenames:
            result.add(os.path.join(dirpath, fname))
        for dname in dirnames:
            result.add(os.path.join(dirpath, dname))
    return result
