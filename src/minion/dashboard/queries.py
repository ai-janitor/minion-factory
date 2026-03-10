"""SQL queries for the TUI dashboard.
All queries use PRAGMA query_only=ON connection — no writes permitted.
Returns list[sqlite3.Row] so render layer can access columns by name.

Purpose: SQL queries for the TUI dashboard.
Rationale: Extracted into own module following single-responsibility principle.
Responsibility: SQL queries for the TUI dashboard. NOT responsible for unrelated concerns.
Organization: Standalone functions and/or a single class. See source."""

from __future__ import annotations

import sqlite3

from minion.tasks.dag import TERMINAL_STATUSES

# Build SQL literal from the single source of truth — safe (values are code-controlled, not user input).
_TERMINAL_SQL = ", ".join(f"'{s}'" for s in sorted(TERMINAL_STATUSES))


def fetch_tasks(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Active tasks ordered by status priority then ID.

    Excludes terminal states. Includes blocked_by for tree rendering.
    """
    cursor = conn.execute("""
        SELECT
            t.id,
            SUBSTR(t.title, 1, 40)          AS title_short,
            t.status,
            COALESCE(t.assigned_to, '—')    AS assignee,
            COALESCE(t.class_required, '')  AS class_req,
            t.flow_type,
            t.blocked_by,
            t.activity_count,
            t.result_file IS NOT NULL       AS has_result
        FROM tasks t
        WHERE t.status NOT IN (""" + _TERMINAL_SQL + """)
        ORDER BY
            CASE t.status
                WHEN 'in_progress' THEN 0
                WHEN 'assigned'    THEN 1
                WHEN 'fixed'       THEN 2
                WHEN 'verified'    THEN 3
                WHEN 'open'        THEN 4
                ELSE 5
            END,
            t.id ASC
        LIMIT 50
    """)
    return cursor.fetchall()


def fetch_agents(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Daemon agents with HP metrics for bar rendering.

    Computes effective_last_seen as the most recent of last_seen,
    context_updated_at, or registered_at — so newly registered agents
    that haven't heartbeated yet don't show "never".
    """
    cursor = conn.execute("""
        SELECT
            name,
            agent_class,
            COALESCE(model, '')                                             AS model,
            status,
            transport,
            COALESCE(hp_input_tokens, 0)  + COALESCE(hp_output_tokens, 0)  AS tokens_used,
            COALESCE(hp_tokens_limit, 0)                                    AS tokens_limit,
            hp_updated_at,
            last_seen,
            registered_at,
            MAX(
                COALESCE(last_seen, ''),
                COALESCE(context_updated_at, ''),
                COALESCE(registered_at, '')
            ) AS effective_last_seen
        FROM agents
        WHERE transport IN ('daemon', 'daemon-ts', 'terminal')
        ORDER BY agent_class, name
    """)
    return cursor.fetchall()


def get_agent_summary(conn: sqlite3.Connection) -> list[dict]:
    """Query all agents with health data for web dashboard.

    SU-22: Returns enriched agent list with HP percentage, current task, unread count.
    """
    agents = []
    for row in conn.execute(
        "SELECT name, agent_class, status, hp_turn_input, hp_tokens_limit, "
        "last_seen, registered_at FROM agents ORDER BY agent_class, name"
    ).fetchall():
        agent = dict(row)
        # Compute HP percentage
        raw = agent.get("hp_turn_input")
        limit = agent.get("hp_tokens_limit")
        if raw is not None and limit and limit > 0:
            agent["hp_pct"] = max(0, round(100 - (raw / limit * 100)))
        else:
            agent["hp_pct"] = None

        # Current task
        task_row = conn.execute(
            "SELECT id, title, status FROM tasks WHERE assigned_to = ? "
            f"AND status NOT IN ({_TERMINAL_SQL}) LIMIT 1",
            (agent["name"],),
        ).fetchone()
        agent["current_task"] = dict(task_row) if task_row else None

        # Unread message count
        unread = conn.execute(
            "SELECT COUNT(*) FROM messages WHERE to_agent = ? AND read_flag = 0",
            (agent["name"],),
        ).fetchone()
        agent["unread_count"] = unread[0] if unread else 0

        agents.append(agent)
    return agents


def get_task_pipeline(conn: sqlite3.Connection) -> dict[str, list[dict]]:
    """Query tasks grouped by status for kanban-style display.

    SU-22: Returns {status: [task_dicts]} for web dashboard pipeline view.
    """
    pipeline: dict[str, list[dict]] = {}
    for row in conn.execute(
        "SELECT id, title, status, assigned_to, flow_type, updated_at "
        "FROM tasks ORDER BY updated_at DESC"
    ).fetchall():
        task = dict(row)
        status = task["status"]
        if status not in pipeline:
            pipeline[status] = []
        pipeline[status].append(task)
    return pipeline


def get_system_stats(conn: sqlite3.Connection, db_path: str = "") -> dict:
    """Query DB and system stats for web dashboard health view.

    SU-22: Returns DB size, row counts per table, WAL mode, agent/task counts.
    """
    import os
    stats: dict = {"tables": {}, "agents": {}, "tasks": {}}

    # DB file size
    if db_path and os.path.exists(db_path):
        stats["db_size_bytes"] = os.path.getsize(db_path)
    else:
        stats["db_size_bytes"] = 0

    # WAL mode
    try:
        mode = conn.execute("PRAGMA journal_mode").fetchone()
        stats["journal_mode"] = mode[0] if mode else "unknown"
    except Exception:
        stats["journal_mode"] = "unknown"

    # Row counts per table
    try:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        for (table_name,) in tables:
            try:
                count = conn.execute(f"SELECT COUNT(*) FROM [{table_name}]").fetchone()[0]
                stats["tables"][table_name] = count
            except Exception:
                stats["tables"][table_name] = -1
    except Exception:
        pass

    # Agent breakdown
    try:
        stats["agents"]["total"] = conn.execute("SELECT COUNT(*) FROM agents").fetchone()[0]
        for row in conn.execute("SELECT agent_class, COUNT(*) as cnt FROM agents GROUP BY agent_class").fetchall():
            stats["agents"][row["agent_class"] or "unknown"] = row["cnt"]
    except Exception:
        pass

    # Task breakdown
    try:
        stats["tasks"]["total"] = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        for row in conn.execute("SELECT status, COUNT(*) as cnt FROM tasks GROUP BY status").fetchall():
            stats["tasks"][row["status"]] = row["cnt"]
    except Exception:
        pass

    return stats


def get_recent_messages(conn: sqlite3.Connection, limit: int = 50) -> list[dict]:
    """Query recent messages for web dashboard message view.

    SU-22: Returns last N messages with all fields, newest first.
    """
    rows = conn.execute(
        "SELECT * FROM messages ORDER BY timestamp DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


def fetch_backlog(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Promoted backlog items — items that have been promoted to tasks.

    Shows backlog items with their promoted_to task ID so the TUI can display
    the DAG stage of the linked task. Only shows items with status != 'closed'.
    Backlog #112: TUI dashboard should show promoted backlog items with DAG stage.
    """
    # The backlog table may not exist in older DBs — fail gracefully
    try:
        cursor = conn.execute("""
            SELECT
                b.id,
                b.type,
                SUBSTR(b.title, 1, 35)              AS title_short,
                b.priority,
                b.status,
                b.promoted_to,
                COALESCE(t.status, '')               AS task_status,
                COALESCE(t.assigned_to, '')          AS task_assignee,
                b.updated_at
            FROM backlog b
            LEFT JOIN tasks t ON b.promoted_to = CAST(t.id AS TEXT)
            WHERE b.status NOT IN ('closed', 'abandoned', 'killed')
            ORDER BY
                CASE b.priority
                    WHEN 'critical' THEN 0
                    WHEN 'high'     THEN 1
                    WHEN 'medium'   THEN 2
                    WHEN 'low'      THEN 3
                    ELSE 4
                END,
                b.id ASC
            LIMIT 20
        """)
        return cursor.fetchall()
    except Exception:
        return []


def fetch_activity(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Recent task status transitions — one per task, most recent only."""
    cursor = conn.execute("""
        SELECT
            task_id,
            title,
            from_status,
            to_status,
            agent,
            timestamp
        FROM (
            SELECT
                tl.entity_id   AS task_id,
                SUBSTR(t.title, 1, 25)  AS title,
                tl.from_status,
                tl.to_status,
                tl.triggered_by AS agent,
                tl.created_at   AS timestamp,
                ROW_NUMBER() OVER (
                    PARTITION BY tl.entity_id
                    ORDER BY tl.created_at DESC
                ) AS rn
            FROM transition_log tl
            JOIN tasks t ON t.id = tl.entity_id
            WHERE tl.entity_type = 'task'
        )
        WHERE rn = 1
        ORDER BY timestamp DESC
        LIMIT 8
    """)
    return cursor.fetchall()
