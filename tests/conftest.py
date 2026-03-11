"""Shared test fixtures — DB isolation, CLI runner, project scaffolding.

Purpose: Centralize duplicated test setup (~150 lines across 11 files).
Rationale: Every test that touches the DB needs isolated_db. Every CLI test
           needs a CliRunner. Centralizing prevents drift and makes new tests
           trivial to write.
Responsibility: Provide pytest fixtures for DB isolation, tmp project dirs,
                CLI runner, agent registration helpers, and battle plan setup.
Organization: Grouped by concern — DB fixtures first, then CLI, then helpers.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest
from click.testing import CliRunner

from minion.db import init_db, reset_db_path, register_agent_db, get_db


# ---------------------------------------------------------------------------
# DB isolation — the most duplicated fixture across test files
# ---------------------------------------------------------------------------


@pytest.fixture()
def isolated_db(tmp_path, monkeypatch):
    """Each test gets its own .work/ tree and isolated SQLite DB.

    Sets MINION_DB_PATH env var, resets the cached path, initializes schema,
    and changes cwd to tmp_path so relative path resolution works.
    Tears down by resetting the cached DB path.
    """
    work_dir = tmp_path / ".work"
    work_dir.mkdir(parents=True, exist_ok=True)

    db_path = str(work_dir / "minion.db")
    monkeypatch.setenv("MINION_DB_PATH", db_path)
    reset_db_path()
    init_db()

    monkeypatch.chdir(tmp_path)
    yield tmp_path

    reset_db_path()


@pytest.fixture()
def isolated_db_with_requirements(tmp_path, monkeypatch):
    """Like isolated_db but also creates .work/requirements/ directory.

    Used by tests that register/decompose requirements and need the
    filesystem tree to exist.
    """
    work_dir = tmp_path / ".work"
    work_dir.mkdir(parents=True, exist_ok=True)
    req_dir = work_dir / "requirements"
    req_dir.mkdir(parents=True, exist_ok=True)

    db_path = str(work_dir / "minion.db")
    monkeypatch.setenv("MINION_DB_PATH", db_path)
    reset_db_path()
    init_db()

    monkeypatch.chdir(tmp_path)
    yield tmp_path

    reset_db_path()


@pytest.fixture()
def isolated_db_with_coordinator(tmp_path, monkeypatch):
    """Like isolated_db but also sets MINION_COORDINATOR_DB_PATH.

    Used by tests that exercise cross-project / coordinator features
    (e.g. register --crew).
    """
    work_dir = tmp_path / ".work"
    work_dir.mkdir(parents=True, exist_ok=True)

    db_path = str(work_dir / "minion.db")
    coord_path = str(work_dir / "coordinator.db")
    monkeypatch.setenv("MINION_DB_PATH", db_path)
    monkeypatch.setenv("MINION_COORDINATOR_DB_PATH", coord_path)
    reset_db_path()
    init_db()

    monkeypatch.chdir(tmp_path)
    yield tmp_path

    reset_db_path()


@pytest.fixture()
def isolated_db_with_intel(tmp_path, monkeypatch):
    """Like isolated_db but also creates .work/intel/ directory.

    Used by tests that create/search intel docs and need the intel
    directory tree to exist.
    """
    work_dir = tmp_path / ".work"
    work_dir.mkdir(parents=True, exist_ok=True)
    intel_dir = work_dir / "intel"
    intel_dir.mkdir(parents=True, exist_ok=True)

    db_path = str(work_dir / "minion.db")
    monkeypatch.setenv("MINION_DB_PATH", db_path)
    reset_db_path()
    init_db()

    monkeypatch.chdir(tmp_path)
    yield tmp_path

    reset_db_path()


@pytest.fixture()
def isolated_db_path(isolated_db):
    """Return the DB file path (str) instead of the project root.

    Convenience fixture for tests that need the raw sqlite3 path rather
    than the tmp_path project root.
    """
    return str(isolated_db / ".work" / "minion.db")


# ---------------------------------------------------------------------------
# CLI runner
# ---------------------------------------------------------------------------


@pytest.fixture()
def runner():
    """Click CliRunner for invoking CLI commands in tests."""
    return CliRunner()


# ---------------------------------------------------------------------------
# Agent registration helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def register_lead(isolated_db):
    """Register a lead agent named 'atlas' and return the project root."""
    register_agent_db("atlas", "lead")
    return isolated_db


@pytest.fixture()
def register_coder(isolated_db):
    """Register a coder agent named 'coder-1' and return the project root."""
    register_agent_db("coder-1", "coder")
    return isolated_db


# ---------------------------------------------------------------------------
# Battle plan helper
# ---------------------------------------------------------------------------


def insert_battle_plan(db_path: str, agent_name: str) -> None:
    """Insert an active battle plan row directly — avoids filesystem path issues.

    Reusable helper for tests that need a battle plan without touching the
    filesystem-based plan_file.
    """
    from minion.db import now_iso
    now = now_iso()
    conn = sqlite3.connect(db_path)
    conn.execute(
        """INSERT INTO battle_plan (agent_name, plan_file, status, created_at)
           VALUES (?, ?, 'active', ?)""",
        (agent_name, f".work/battle-plans/{agent_name}-plan.md", now),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Direct DB insert helpers for tasks and agents
# ---------------------------------------------------------------------------


def insert_agent_row(db_path: str, name: str, agent_class: str = "coder") -> None:
    """Insert a minimal agent row directly via sqlite3 (bypasses register_agent_db)."""
    from minion.db import now_iso
    now = now_iso()
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT OR REPLACE INTO agents (name, agent_class, registered_at, last_seen) VALUES (?, ?, ?, ?)",
        (name, agent_class, now, now),
    )
    conn.commit()
    conn.close()


def insert_open_task(db_path: str, title: str = "Test task", flow_type: str = "bugfix") -> int:
    """Insert an open task and return its ID."""
    from minion.db import now_iso
    now = now_iso()
    conn = sqlite3.connect(db_path)
    cur = conn.execute(
        """INSERT INTO tasks (title, status, created_at, updated_at, flow_type)
           VALUES (?, 'open', ?, ?, ?)""",
        (title, now, now, flow_type),
    )
    task_id = cur.lastrowid
    conn.commit()
    conn.close()
    return task_id
