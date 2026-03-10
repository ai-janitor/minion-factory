"""Project-scoped endpoints — /projects, /projects/{name}/agents|tasks|messages|raid-log|tasks/{id}/lineage.

Purpose: Serve per-project data by reading from project-local .work/minion.db files.
Rationale: The dashboard needs to show project-level detail (agents, tasks, messages,
           raid log) for any registered project. These endpoints bridge the network
           coordinator to per-project SQLite databases discovered via agent project_paths.
Responsibility: All reads from project-local DBs. Uses project_db.get_project_db() for
                connection caching and discovery.discover_projects() for project listing.
Organization: URL pattern /projects/{name}/... routes here. Project name is the last
              path component of project_path.

Implementation order: 4th (depends on project_db + discovery).
"""

from __future__ import annotations

import os
from urllib.parse import urlparse, parse_qs

from minion.network.server import _DB_LOCK
from minion.network.discovery import discover_projects
from minion.network.handlers._resolve_project_or_404 import resolve_project_or_404


def register(router) -> None:
    """Register project-scoped endpoints with the router dispatch table."""
    router.add_get("/projects", handle_list_projects)
    router.add_get("/projects/{name}/agents", handle_project_agents)
    router.add_get("/projects/{name}/tasks", handle_project_tasks)
    router.add_get("/projects/{name}/tasks/{task_id}/lineage", handle_task_lineage)
    router.add_get("/projects/{name}/messages", handle_project_messages)
    router.add_get("/projects/{name}/raid-log", handle_project_raid_log)


def handle_list_projects(handler, db_path: str, **kwargs) -> None:
    """GET /projects — list all discovered projects with agent counts."""
    projects = discover_projects(db_path, _DB_LOCK)
    handler._json_response(200, {"projects": projects})


def handle_project_agents(handler, db_path: str, name: str = "", **kwargs) -> None:
    """GET /projects/{name}/agents — agents from project-local DB with full detail."""
    project_path, conn = resolve_project_or_404(handler, db_path, name)
    if conn is None:
        return

    try:
        rows = conn.execute("""
            SELECT a.name, a.agent_class, a.model, a.status, a.transport,
                   a.hp_input_tokens, a.hp_output_tokens, a.hp_tokens_limit,
                   a.hp_turn_input, a.hp_turn_output, a.hp_updated_at,
                   a.last_seen, a.context_summary, a.current_zone, a.current_role,
                   a.registered_at,
                   t.id AS task_id, t.title AS task_title, t.status AS task_status
            FROM agents a
            LEFT JOIN tasks t ON t.assigned_to = a.name AND t.status = 'in_progress'
            ORDER BY a.last_seen DESC
        """).fetchall()
    except Exception as e:
        handler._json_response(500, {"error": f"DB query failed: {e}"})
        return

    agents = []
    for row in rows:
        agent = dict(row)
        # Compute HP percentage
        raw = agent.get("hp_turn_input") or agent.get("hp_input_tokens")
        limit = agent.get("hp_tokens_limit")
        used = min(raw or 0, limit) if limit else raw
        hp_pct = max(0, round(100 - (used / limit * 100))) if limit and used else None
        hp_status = None
        if hp_pct is not None:
            hp_status = "Healthy" if hp_pct > 50 else "Wounded" if hp_pct > 25 else "CRITICAL"
        # Build current_task
        current_task = None
        if agent.get("task_id"):
            current_task = {
                "id": agent["task_id"],
                "title": agent["task_title"],
                "status": agent["task_status"],
            }
        # Clean up joined fields
        for k in ("task_id", "task_title", "task_status"):
            agent.pop(k, None)
        agent["hp_pct"] = hp_pct
        agent["hp_status"] = hp_status
        agent["current_task"] = current_task
        agents.append(agent)

    handler._json_response(200, {"agents": agents})


def handle_project_tasks(handler, db_path: str, name: str = "", **kwargs) -> None:
    """GET /projects/{name}/tasks — tasks from project-local DB."""
    project_path, conn = resolve_project_or_404(handler, db_path, name)
    if conn is None:
        return

    # Parse query params
    parsed = urlparse(handler.path)
    params = parse_qs(parsed.query)
    status_filter = params.get("status", [None])[0]
    assigned_filter = params.get("assigned_to", [None])[0]
    limit = min(int(params.get("limit", ["100"])[0]), 500)
    offset = int(params.get("offset", ["0"])[0])

    query = "SELECT id, title, status, assigned_to, created_by, project, zone, " \
            "blocked_by, activity_count, progress, created_at, updated_at " \
            "FROM tasks"
    conditions = []
    args = []
    if status_filter:
        conditions.append("status = ?")
        args.append(status_filter)
    if assigned_filter:
        conditions.append("assigned_to = ?")
        args.append(assigned_filter)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY updated_at DESC LIMIT ? OFFSET ?"
    args.extend([limit, offset])

    try:
        rows = conn.execute(query, args).fetchall()
    except Exception as e:
        handler._json_response(500, {"error": f"DB query failed: {e}"})
        return

    handler._json_response(200, {"tasks": [dict(r) for r in rows]})


def handle_task_lineage(handler, db_path: str, name: str = "",
                        task_id: str = "", **kwargs) -> None:
    """GET /projects/{name}/tasks/{id}/lineage — task detail + full status history."""
    project_path, conn = resolve_project_or_404(handler, db_path, name)
    if conn is None:
        return

    try:
        tid = int(task_id)
    except (ValueError, TypeError):
        handler._json_response(400, {"error": "Invalid task ID"})
        return

    try:
        task = conn.execute("SELECT * FROM tasks WHERE id = ?", (tid,)).fetchone()
    except Exception as e:
        handler._json_response(500, {"error": f"DB query failed: {e}"})
        return

    if not task:
        handler._json_response(404, {"error": "Task not found"})
        return

    task_dict = dict(task)
    try:
        history = conn.execute(
            "SELECT from_status, to_status, agent, timestamp "
            "FROM task_history WHERE task_id = ? ORDER BY timestamp ASC",
            (tid,),
        ).fetchall()
    except Exception:
        history = []

    handler._json_response(200, {
        "task": task_dict,
        "history": [dict(r) for r in history],
        "flow_type": task_dict.get("task_type") or task_dict.get("flow_type") or "bugfix",
    })


def handle_project_messages(handler, db_path: str, name: str = "", **kwargs) -> None:
    """GET /projects/{name}/messages — messages from project-local DB."""
    project_path, conn = resolve_project_or_404(handler, db_path, name)
    if conn is None:
        return

    parsed = urlparse(handler.path)
    params = parse_qs(parsed.query)
    limit = min(int(params.get("limit", ["50"])[0]), 200)
    from_filter = params.get("from", [None])[0]
    to_filter = params.get("to", [None])[0]

    query = "SELECT id, from_agent, to_agent, content_file, timestamp, read_flag, is_cc " \
            "FROM messages"
    conditions = []
    args = []
    if from_filter:
        conditions.append("from_agent = ?")
        args.append(from_filter)
    if to_filter:
        conditions.append("to_agent = ?")
        args.append(to_filter)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY timestamp DESC LIMIT ?"
    args.append(limit)

    try:
        rows = conn.execute(query, args).fetchall()
    except Exception as e:
        handler._json_response(500, {"error": f"DB query failed: {e}"})
        return

    messages = []
    for row in rows:
        msg = dict(row)
        content_file = msg.get("content_file")
        if content_file:
            try:
                with open(content_file, "r") as f:
                    raw = f.read()
                msg["content"] = raw[:200] + "…" if len(raw) > 200 else raw
            except OSError:
                msg["content"] = "(file not found)"
        messages.append(msg)

    handler._json_response(200, {"messages": messages})


def handle_project_raid_log(handler, db_path: str, name: str = "", **kwargs) -> None:
    """GET /projects/{name}/raid-log — raid log entries from project-local DB."""
    project_path, conn = resolve_project_or_404(handler, db_path, name)
    if conn is None:
        return

    try:
        rows = conn.execute(
            "SELECT id, agent_name, entry_file, priority, created_at "
            "FROM raid_log ORDER BY created_at DESC"
        ).fetchall()
    except Exception as e:
        handler._json_response(500, {"error": f"DB query failed: {e}"})
        return

    entries = []
    for row in rows:
        entry = dict(row)
        entry_file = entry.get("entry_file")
        if entry_file:
            try:
                with open(entry_file, "r") as f:
                    entry["content"] = f.read()
            except OSError:
                entry["content"] = "(file not found)"
        entries.append(entry)

    handler._json_response(200, {"entries": entries})
