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


# ---------------------------------------------------------------------------
# queries.fetch_backlog — exception narrowing (bug #203)
# ---------------------------------------------------------------------------


def test_fetch_backlog_returns_empty_on_missing_table(tmp_path):
    """fetch_backlog returns [] for OperationalError (no such table — fresh install).

    OperationalError is a subclass of DatabaseError and is the error SQLite raises
    for 'no such table: backlog'. This case must be handled gracefully — not every
    install has the backlog table yet.
    """
    from unittest.mock import MagicMock, patch
    from minion.dashboard.queries import fetch_backlog
    import sqlite3

    conn = MagicMock()
    conn.execute.side_effect = sqlite3.OperationalError("no such table: backlog")

    result = fetch_backlog(conn)
    assert result == []


def test_fetch_backlog_raises_on_non_operational_database_error(tmp_path):
    """fetch_backlog must NOT swallow non-OperationalError DatabaseErrors.

    DatabaseErrors other than OperationalError (e.g. disk I/O failure, corruption)
    indicate real DB health problems that must propagate to the caller, not be hidden
    as an empty backlog list (bug #203).
    """
    from unittest.mock import MagicMock
    from minion.dashboard.queries import fetch_backlog
    import sqlite3

    # DatabaseError that is NOT an OperationalError — simulates corruption/IO failure
    class FakeDatabaseError(sqlite3.DatabaseError):
        pass

    conn = MagicMock()
    conn.execute.side_effect = FakeDatabaseError("disk I/O error")

    with pytest.raises(sqlite3.DatabaseError):
        fetch_backlog(conn)


def test_fetch_backlog_returns_rows_on_success(tmp_path):
    """fetch_backlog returns rows when backlog table exists and query succeeds."""
    from minion.dashboard.queries import fetch_backlog
    from minion.db import now_iso

    db_path = str(tmp_path / ".work" / "minion.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Insert a backlog row — table exists from init_db (via isolated_db fixture)
    now = now_iso()
    conn.execute(
        """INSERT INTO backlog
           (type, title, priority, status, file_path, created_at, updated_at, source, created_by)
           VALUES ('bug', 'Test backlog item', 'high', 'open', 'bugs/test-item', ?, ?, 'human', 'test')""",
        (now, now),
    )
    conn.commit()

    rows = fetch_backlog(conn)
    conn.close()

    assert len(rows) == 1
    assert rows[0]["title_short"] == "Test backlog item"
