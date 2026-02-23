"""SQL queries for the TUI dashboard.

All queries use PRAGMA query_only=ON connection — no writes permitted.
Returns list[sqlite3.Row] so render layer can access columns by name.
"""

from __future__ import annotations

import sqlite3


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
        WHERE t.status NOT IN ('closed', 'abandoned', 'stale', 'obsolete')
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
    """Daemon agents with HP metrics for bar rendering."""
    cursor = conn.execute("""
        SELECT
            name,
            agent_class,
            status,
            transport,
            COALESCE(hp_input_tokens, 0)  + COALESCE(hp_output_tokens, 0)  AS tokens_used,
            COALESCE(hp_tokens_limit, 0)                                    AS tokens_limit,
            hp_updated_at,
            last_seen
        FROM agents
        WHERE transport IN ('daemon', 'daemon-ts', 'terminal')
        ORDER BY agent_class, name
    """)
    return cursor.fetchall()


def fetch_activity(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Recent task status transitions for the activity feed."""
    cursor = conn.execute("""
        SELECT
            tl.entity_id   AS task_id,
            SUBSTR(t.title, 1, 25)  AS title,
            tl.from_status,
            tl.to_status,
            tl.triggered_by AS agent,
            tl.created_at   AS timestamp
        FROM transition_log tl
        JOIN tasks t ON t.id = tl.entity_id
        WHERE tl.entity_type = 'task'
        ORDER BY tl.created_at DESC
        LIMIT 8
    """)
    return cursor.fetchall()
