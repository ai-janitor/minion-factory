"""Coordinator team tasks — lightweight cross-machine handoff/status layer.

Not a replacement for repo-local backlog/task/DAG. This is the shared
coordinator-side record for work requests, specs, and status handoff.

Purpose: Team task CRUD on the coordinator.
Rationale: Allows work handoff through the API without SCP or repo checkout.
Responsibility: Create, list, show, assign, update status, comment on tasks
  stored in the coordinator network.db."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime

logger = logging.getLogger(__name__)

from minion.network.server import _DB_LOCK, _get_server_db


# Schema for team_tasks and team_task_comments — created on first use
_TEAM_TASKS_SCHEMA = """
CREATE TABLE IF NOT EXISTS team_tasks (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id          INTEGER REFERENCES channels(id),
    title               TEXT NOT NULL,
    body_text           TEXT,
    created_by_agent    TEXT NOT NULL,
    created_by_uuid     TEXT,
    assigned_to_agent   TEXT,
    assigned_to_uuid    TEXT,
    status              TEXT NOT NULL DEFAULT 'open',
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL,
    completed_at        TEXT
);

CREATE TABLE IF NOT EXISTS team_task_comments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id     INTEGER NOT NULL REFERENCES team_tasks(id),
    author_agent TEXT NOT NULL,
    author_uuid TEXT,
    body_text   TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_team_tasks_channel ON team_tasks(channel_id);
CREATE INDEX IF NOT EXISTS idx_team_tasks_assigned ON team_tasks(assigned_to_agent);
CREATE INDEX IF NOT EXISTS idx_team_task_comments_task ON team_task_comments(task_id);
"""


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """Create team_tasks tables if they don't exist."""
    conn.executescript(_TEAM_TASKS_SCHEMA)


def register(router) -> None:
    """Register team task endpoints."""
    router.add_post("/team/tasks", handle_create_task)
    router.add_get("/team/tasks", handle_list_tasks)
    router.add_get("/team/tasks/{task_id}", handle_show_task)
    router.add_post("/team/tasks/{task_id}/assign", handle_assign_task)
    router.add_post("/team/tasks/{task_id}/status", handle_update_status)
    router.add_post("/team/tasks/{task_id}/comment", handle_add_comment)


def handle_create_task(handler, db_path: str, **kwargs) -> None:
    """POST /team/tasks — create a coordinator team task.

    Body: {
        "title": "...",
        "body_text": "...",
        "channel": "llama-metal",
        "created_by": "codex-lead",
        "assigned_to": "trashcan-lead"  (optional)
    }
    """
    body = handler._parse_json_body()
    if not body:
        return

    title = body.get("title", "").strip()
    if not title:
        handler._json_response(400, {"error": "title is required"})
        return

    body_text = body.get("body_text", "")
    channel_name = body.get("channel", "")
    created_by = body.get("created_by", "")
    assigned_to = body.get("assigned_to", "")
    now = datetime.now().isoformat()

    with _DB_LOCK:
        conn = _get_server_db(db_path)
        try:
            _ensure_schema(conn)

            # Resolve channel_id
            channel_id = None
            if channel_name:
                ch = conn.execute("SELECT id FROM channels WHERE name = ?", (channel_name,)).fetchone()
                if ch:
                    channel_id = ch[0]

            # Resolve UUIDs
            created_uuid = None
            if created_by:
                r = conn.execute("SELECT agent_uuid FROM agents WHERE name = ?", (created_by,)).fetchone()
                if r:
                    created_uuid = r[0]

            assigned_uuid = None
            if assigned_to:
                r = conn.execute("SELECT agent_uuid FROM agents WHERE name = ?", (assigned_to,)).fetchone()
                if r:
                    assigned_uuid = r[0]

            status = "assigned" if assigned_to else "open"

            conn.execute(
                "INSERT INTO team_tasks (channel_id, title, body_text, created_by_agent, created_by_uuid, "
                "assigned_to_agent, assigned_to_uuid, status, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (channel_id, title, body_text, created_by, created_uuid,
                 assigned_to, assigned_uuid, status, now, now),
            )
            conn.commit()
            task_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        finally:
            conn.close()

    handler._json_response(201, {
        "status": "created", "id": task_id, "title": title,
        "assigned_to": assigned_to, "task_status": status,
    })


def handle_list_tasks(handler, db_path: str, **kwargs) -> None:
    """GET /team/tasks — list coordinator team tasks.

    Query params: ?channel=, ?status=, ?assigned_to=
    """
    from urllib.parse import parse_qs, urlparse
    parsed = urlparse(handler.path)
    params = parse_qs(parsed.query)

    channel = params.get("channel", [None])[0]
    status_filter = params.get("status", [None])[0]
    assigned = params.get("assigned_to", [None])[0]

    with _DB_LOCK:
        conn = _get_server_db(db_path)
        try:
            _ensure_schema(conn)

            query = "SELECT t.*, c.name as channel_name FROM team_tasks t LEFT JOIN channels c ON t.channel_id = c.id WHERE 1=1"
            query_params = []

            if channel:
                query += " AND c.name = ?"
                query_params.append(channel)
            if status_filter:
                query += " AND t.status = ?"
                query_params.append(status_filter)
            if assigned:
                query += " AND t.assigned_to_agent = ?"
                query_params.append(assigned)

            query += " ORDER BY t.updated_at DESC LIMIT 50"
            rows = conn.execute(query, query_params).fetchall()
            tasks = [dict(r) for r in rows]
        finally:
            conn.close()

    handler._json_response(200, {"tasks": tasks})


def handle_show_task(handler, db_path: str, task_id: str = "", **kwargs) -> None:
    """GET /team/tasks/{task_id} — show task detail with comments."""
    try:
        tid = int(task_id)
    except (ValueError, TypeError):
        handler._json_response(400, {"error": "task_id must be an integer"})
        return

    with _DB_LOCK:
        conn = _get_server_db(db_path)
        try:
            _ensure_schema(conn)
            task = conn.execute(
                "SELECT t.*, c.name as channel_name FROM team_tasks t "
                "LEFT JOIN channels c ON t.channel_id = c.id WHERE t.id = ?", (tid,)
            ).fetchone()

            if not task:
                handler._json_response(404, {"error": f"Task {tid} not found"})
                return

            comments = conn.execute(
                "SELECT * FROM team_task_comments WHERE task_id = ? ORDER BY created_at ASC", (tid,)
            ).fetchall()
        finally:
            conn.close()

    handler._json_response(200, {
        "task": dict(task),
        "comments": [dict(c) for c in comments],
    })


def handle_assign_task(handler, db_path: str, task_id: str = "", **kwargs) -> None:
    """POST /team/tasks/{task_id}/assign — assign or reassign a task.

    Body: {"assigned_to": "agent-name"}
    """
    body = handler._parse_json_body()
    if not body:
        return

    try:
        tid = int(task_id)
    except (ValueError, TypeError):
        handler._json_response(400, {"error": "task_id must be an integer"})
        return

    assigned_to = body.get("assigned_to", "").strip()
    now = datetime.now().isoformat()

    with _DB_LOCK:
        conn = _get_server_db(db_path)
        try:
            _ensure_schema(conn)
            assigned_uuid = None
            if assigned_to:
                r = conn.execute("SELECT agent_uuid FROM agents WHERE name = ?", (assigned_to,)).fetchone()
                if r:
                    assigned_uuid = r[0]

            conn.execute(
                "UPDATE team_tasks SET assigned_to_agent = ?, assigned_to_uuid = ?, "
                "status = CASE WHEN status = 'open' THEN 'assigned' ELSE status END, updated_at = ? WHERE id = ?",
                (assigned_to, assigned_uuid, now, tid),
            )
            conn.commit()
        finally:
            conn.close()

    handler._json_response(200, {"status": "assigned", "task_id": tid, "assigned_to": assigned_to})


def handle_update_status(handler, db_path: str, task_id: str = "", **kwargs) -> None:
    """POST /team/tasks/{task_id}/status — update task status.

    Body: {"status": "in_progress|blocked|done|canceled", "comment": "optional note"}
    """
    body = handler._parse_json_body()
    if not body:
        return

    try:
        tid = int(task_id)
    except (ValueError, TypeError):
        handler._json_response(400, {"error": "task_id must be an integer"})
        return

    new_status = body.get("status", "").strip()
    valid_statuses = {"open", "assigned", "in_progress", "blocked", "done", "canceled"}
    if new_status not in valid_statuses:
        handler._json_response(400, {"error": f"Invalid status. Must be one of: {', '.join(sorted(valid_statuses))}"})
        return

    comment = body.get("comment", "").strip()
    agent = body.get("agent", "").strip()
    now = datetime.now().isoformat()

    with _DB_LOCK:
        conn = _get_server_db(db_path)
        try:
            _ensure_schema(conn)
            updates = {"status": new_status, "updated_at": now}
            if new_status == "done":
                updates["completed_at"] = now

            set_clause = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(f"UPDATE team_tasks SET {set_clause} WHERE id = ?",
                         list(updates.values()) + [tid])

            # Auto-add comment on status change if provided
            if comment:
                agent_uuid = None
                if agent:
                    r = conn.execute("SELECT agent_uuid FROM agents WHERE name = ?", (agent,)).fetchone()
                    if r:
                        agent_uuid = r[0]
                conn.execute(
                    "INSERT INTO team_task_comments (task_id, author_agent, author_uuid, body_text, created_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (tid, agent or "system", agent_uuid, f"[{new_status}] {comment}", now),
                )

            conn.commit()
        finally:
            conn.close()

    handler._json_response(200, {"status": "updated", "task_id": tid, "task_status": new_status})


def handle_add_comment(handler, db_path: str, task_id: str = "", **kwargs) -> None:
    """POST /team/tasks/{task_id}/comment — append a comment.

    Body: {"agent": "name", "body_text": "..."}
    """
    body = handler._parse_json_body()
    if not body:
        return

    try:
        tid = int(task_id)
    except (ValueError, TypeError):
        handler._json_response(400, {"error": "task_id must be an integer"})
        return

    agent = body.get("agent", "").strip()
    body_text = body.get("body_text", "").strip()
    if not body_text:
        handler._json_response(400, {"error": "body_text is required"})
        return

    now = datetime.now().isoformat()

    with _DB_LOCK:
        conn = _get_server_db(db_path)
        try:
            _ensure_schema(conn)
            agent_uuid = None
            if agent:
                r = conn.execute("SELECT agent_uuid FROM agents WHERE name = ?", (agent,)).fetchone()
                if r:
                    agent_uuid = r[0]

            conn.execute(
                "INSERT INTO team_task_comments (task_id, author_agent, author_uuid, body_text, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (tid, agent or "anonymous", agent_uuid, body_text, now),
            )
            # Update task updated_at
            conn.execute("UPDATE team_tasks SET updated_at = ? WHERE id = ?", (now, tid))
            conn.commit()
            comment_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        finally:
            conn.close()

    handler._json_response(201, {"status": "commented", "task_id": tid, "comment_id": comment_id})
