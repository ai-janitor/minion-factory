"""Tests for warroom — battle plan creation and test fixtures (T78)."""

from __future__ import annotations

import os

import pytest

from minion.db import init_db, reset_db_path, get_db


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
# Helpers
# ---------------------------------------------------------------------------


def _plan_rows(db_path: str) -> list[dict]:
    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM battle_plan ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# T78 — create_battle_plan() DB-only insertion
# ---------------------------------------------------------------------------


def test_create_battle_plan_inserts_row(tmp_path):
    """create_battle_plan inserts a row into battle_plan without filesystem writes."""
    from minion.warroom import create_battle_plan

    db_path = str(tmp_path / ".work" / "minion.db")
    result = create_battle_plan(set_by="lead", plan_file="/tmp/test-plan.md")

    assert "error" not in result
    assert result["status"] == "active"
    assert isinstance(result["plan_id"], int)
    assert result["set_by"] == "lead"
    assert result["plan_file"] == "/tmp/test-plan.md"

    rows = _plan_rows(db_path)
    assert len(rows) == 1
    assert rows[0]["set_by"] == "lead"
    assert rows[0]["status"] == "active"


def test_create_battle_plan_no_filesystem_writes(tmp_path):
    """create_battle_plan does not create any files on disk."""
    from minion.warroom import create_battle_plan

    # Snapshot filesystem state before
    work_dir = tmp_path / ".work"
    before = set(os.listdir(str(work_dir)))

    create_battle_plan(set_by="lead", plan_file="/tmp/phantom.md")

    after = set(os.listdir(str(work_dir)))
    # Only the DB file should exist; no new files or dirs
    new_entries = after - before
    assert new_entries == set(), f"Unexpected filesystem writes: {new_entries}"


# ---------------------------------------------------------------------------
# T78 — make_test_battle_plan() returns expected defaults
# ---------------------------------------------------------------------------


def test_make_test_battle_plan_defaults(tmp_path):
    """make_test_battle_plan returns the documented default values."""
    from minion.warroom import make_test_battle_plan

    result = make_test_battle_plan()

    assert result["set_by"] == "lead"
    assert result["plan_file"] == "/tmp/test-plan.md"
    assert result["status"] == "active"
    assert isinstance(result["plan_id"], int)


def test_make_test_battle_plan_custom_args(tmp_path):
    """make_test_battle_plan passes through custom arguments."""
    from minion.warroom import make_test_battle_plan

    result = make_test_battle_plan(set_by="agent-x", plan_file="/var/plan.md", status="superseded")

    assert result["set_by"] == "agent-x"
    assert result["plan_file"] == "/var/plan.md"
    assert result["status"] == "superseded"


# ---------------------------------------------------------------------------
# T78 — supersede=True marks previous active plans
# ---------------------------------------------------------------------------


def test_create_battle_plan_supersede_true(tmp_path):
    """When supersede=True a new active plan marks previous active rows as superseded."""
    from minion.warroom import create_battle_plan

    db_path = str(tmp_path / ".work" / "minion.db")

    # Insert first active plan
    first = create_battle_plan(set_by="lead", plan_file="/tmp/plan-1.md", supersede=True)
    assert first["status"] == "active"

    # Insert second active plan — first should become superseded
    second = create_battle_plan(set_by="lead", plan_file="/tmp/plan-2.md", supersede=True)
    assert second["status"] == "active"

    rows = _plan_rows(db_path)
    statuses = {r["id"]: r["status"] for r in rows}

    assert statuses[first["plan_id"]] == "superseded"
    assert statuses[second["plan_id"]] == "active"


def test_create_battle_plan_supersede_false_does_not_supersede(tmp_path):
    """When supersede=False previous active plans are left untouched."""
    from minion.warroom import create_battle_plan

    db_path = str(tmp_path / ".work" / "minion.db")

    first = create_battle_plan(set_by="lead", plan_file="/tmp/plan-a.md", supersede=False)
    second = create_battle_plan(set_by="lead", plan_file="/tmp/plan-b.md", supersede=False)

    rows = _plan_rows(db_path)
    statuses = {r["id"]: r["status"] for r in rows}

    # Both remain active when supersede=False
    assert statuses[first["plan_id"]] == "active"
    assert statuses[second["plan_id"]] == "active"
