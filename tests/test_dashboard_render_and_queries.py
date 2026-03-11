"""Tests for dashboard queries.py and render.py — data fetch and ANSI rendering.

Purpose: Verify dashboard queries return correct data shapes and render functions
         produce string output. Tests use isolated DB with sample data.
Rationale: The TUI dashboard is the primary observability tool for multi-agent
           operations. If queries return wrong data or render crashes, operators
           lose visibility into agent health and task state.
Responsibility: Test fetch_tasks, fetch_agents, fetch_activity, token_bar,
                render_screen. NOT responsible for loop.py (real-time refresh).
Organization: Queries section (DB-backed), then render section (pure functions).
"""

from __future__ import annotations

import sqlite3

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.db]


# ---------------------------------------------------------------------------
# Auto-apply isolated_db from conftest to every test in this module
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _use_isolated_db(isolated_db):
    """Delegate to conftest.isolated_db; autouse ensures every test gets DB isolation."""


def _get_ro_conn(tmp_path) -> sqlite3.Connection:
    """Open a read-only connection to the test DB (mirrors dashboard usage)."""
    db_path = str(tmp_path / ".work" / "minion.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _insert_agent(tmp_path, name="agent-1", agent_class="coder", status="ready",
                  transport="daemon"):
    """Insert a sample agent row into the test DB."""
    from minion.db import now_iso
    now = now_iso()
    db_path = str(tmp_path / ".work" / "minion.db")
    conn = sqlite3.connect(db_path)
    conn.execute(
        """INSERT OR REPLACE INTO agents
           (name, agent_class, status, transport, registered_at, last_seen,
            hp_input_tokens, hp_output_tokens, hp_tokens_limit)
           VALUES (?, ?, ?, ?, ?, ?, 5000, 3000, 100000)""",
        (name, agent_class, status, transport, now, now),
    )
    conn.commit()
    conn.close()


def _insert_task(tmp_path, title="Test task", status="open", flow_type="bugfix"):
    """Insert a sample task row into the test DB."""
    from minion.db import now_iso
    now = now_iso()
    db_path = str(tmp_path / ".work" / "minion.db")
    conn = sqlite3.connect(db_path)
    task_file = str(tmp_path / ".work" / "tasks" / f"{title.replace(' ', '-')}.md")
    conn.execute(
        """INSERT INTO tasks (title, status, created_at, updated_at, flow_type, activity_count, task_file, created_by)
           VALUES (?, ?, ?, ?, ?, 0, ?, 'test-agent')""",
        (title, status, now, now, flow_type, task_file),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# queries.fetch_tasks
# ---------------------------------------------------------------------------


def test_fetch_tasks_returns_active_tasks(tmp_path):
    """fetch_tasks returns tasks that are not in terminal states."""
    from minion.dashboard.queries import fetch_tasks

    _insert_task(tmp_path, title="Active bug", status="open")
    _insert_task(tmp_path, title="Closed bug", status="closed")

    conn = _get_ro_conn(tmp_path)
    try:
        rows = fetch_tasks(conn)
        titles = [r["title_short"] for r in rows]
        assert "Active bug" in titles
        assert "Closed bug" not in titles
    finally:
        conn.close()


def test_fetch_tasks_empty_db(tmp_path):
    """fetch_tasks returns empty list when no tasks exist."""
    from minion.dashboard.queries import fetch_tasks

    conn = _get_ro_conn(tmp_path)
    try:
        rows = fetch_tasks(conn)
        assert rows == []
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# queries.fetch_agents
# ---------------------------------------------------------------------------


def test_fetch_agents_returns_daemon_agents(tmp_path):
    """fetch_agents returns agents with daemon or terminal transport."""
    from minion.dashboard.queries import fetch_agents

    _insert_agent(tmp_path, name="daemon-a", transport="daemon")
    _insert_agent(tmp_path, name="terminal-a", transport="terminal")

    conn = _get_ro_conn(tmp_path)
    try:
        rows = fetch_agents(conn)
        names = [r["name"] for r in rows]
        assert "daemon-a" in names
        assert "terminal-a" in names
    finally:
        conn.close()


def test_fetch_agents_empty_db(tmp_path):
    """fetch_agents returns empty list when no agents registered."""
    from minion.dashboard.queries import fetch_agents

    conn = _get_ro_conn(tmp_path)
    try:
        rows = fetch_agents(conn)
        assert rows == []
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# queries.fetch_activity
# ---------------------------------------------------------------------------


def test_fetch_activity_empty_db(tmp_path):
    """fetch_activity returns empty list when no transitions logged."""
    from minion.dashboard.queries import fetch_activity

    conn = _get_ro_conn(tmp_path)
    try:
        rows = fetch_activity(conn)
        assert rows == []
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# render.token_bar — pure function
# ---------------------------------------------------------------------------


def test_token_bar_low_usage():
    """token_bar with low usage shows green-ish bar."""
    from minion.dashboard.render import token_bar

    result = token_bar(used=1000, limit=100000)
    assert isinstance(result, str)
    assert len(result) > 0


def test_token_bar_unknown_limit():
    """token_bar with limit <= 100 shows unknown state."""
    from minion.dashboard.render import token_bar

    result = token_bar(used=0, limit=0)
    assert "(---)" in result


def test_token_bar_high_usage():
    """token_bar at >75% usage still returns a string."""
    from minion.dashboard.render import token_bar

    result = token_bar(used=80000, limit=100000)
    assert isinstance(result, str)


# ---------------------------------------------------------------------------
# render.render_screen — integration of all sections
# ---------------------------------------------------------------------------


def test_render_screen_with_data(tmp_path):
    """render_screen produces a non-empty string with all three data sections."""
    from minion.dashboard.queries import fetch_tasks, fetch_agents, fetch_activity
    from minion.dashboard.render import render_screen

    _insert_task(tmp_path, title="Build widget", status="in_progress")
    _insert_agent(tmp_path, name="coder-1", transport="daemon")

    conn = _get_ro_conn(tmp_path)
    try:
        tasks = fetch_tasks(conn)
        agents = fetch_agents(conn)
        activity = fetch_activity(conn)
    finally:
        conn.close()

    screen, click_map = render_screen(tasks, agents, activity, width=120, height=40)
    assert isinstance(screen, str)
    assert isinstance(click_map, dict)
    assert "TASKS" in screen
    assert "AGENTS" in screen
    assert "ACTIVITY" in screen


def test_render_screen_empty_data():
    """render_screen handles empty data gracefully."""
    from minion.dashboard.render import render_screen

    screen, click_map = render_screen([], [], [], width=80, height=24)
    assert isinstance(screen, str)
    assert isinstance(click_map, dict)
    assert "no active tasks" in screen
