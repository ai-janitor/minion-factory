"""SQL queries for the TUI dashboard.
All queries use PRAGMA query_only=ON connection — no writes permitted.
Returns list[sqlite3.Row] so render layer can access columns by name.

Purpose: SQL queries for the TUI dashboard.
Rationale: Extracted into own module following single-responsibility principle.
Responsibility: SQL queries for the TUI dashboard. NOT responsible for unrelated concerns.
Organization: Standalone functions and/or a single class. See source."""

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
    """Daemon agents with HP metrics for bar rendering.

    Computes effective_last_seen as the most recent of last_seen,
    context_updated_at, or registered_at — so newly registered agents
    that haven't heartbeated yet don't show "never".
    """
    cursor = conn.execute("""
        SELECT
            name,
            agent_class,
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
