"""Backward-compatible /api/* routes for the React frontend.

Purpose: Bridge the React dashboard (which calls /api/agents, /api/tasks, etc.)
         to the new multi-project endpoints (/projects/{name}/agents, etc.).
Rationale: The React frontend was built against the Express server's /api/* routes.
           Rather than rewrite all frontend API calls at once, these compat routes
           auto-resolve to the first registered project, letting the frontend work
           unchanged during migration.
Responsibility: Map /api/* to /projects/{auto-detected-project}/*. Provide /api/login
                as a bridge from username/password auth to cluster token auth.
Organization: Single module with compat handler functions. Will be removed once the
              frontend is updated to use /projects/{name}/* directly.

Implementation order: after handlers/projects.py (depends on project resolution).
"""

from __future__ import annotations

import json
import os
import re
from urllib.parse import urlparse, parse_qs

from minion.network.server import _DB_LOCK
from minion.network.discovery import discover_projects, resolve_project_path
from minion.network.handlers.projects import (
    handle_project_agents,
    handle_project_tasks,
    handle_task_lineage,
    handle_project_messages,
    handle_project_raid_log,
)
from minion.network.handlers.flows import handle_get_flow


def register(router) -> None:
    """Register /api/* compat routes for the React frontend."""
    router.add_post("/api/login", handle_api_login)
    router.add_get("/api/agents", handle_api_agents)
    router.add_get("/api/tasks", handle_api_tasks)
    router.add_get("/api/task-lineage/{task_id}", handle_api_task_lineage)
    router.add_get("/api/messages", handle_api_messages)
    router.add_get("/api/raid-log", handle_api_raid_log)
    router.add_get("/api/flows/{flow_type}", handle_api_flows)
    router.add_get("/api/sprint", handle_api_sprint)
    router.add_get("/api/logs", handle_api_logs)
    router.add_get("/api/logs/{agent_name}", handle_api_agent_log)


def _auto_project_name(db_path: str) -> str | None:
    """Resolve the single/first project name for compat routing."""
    projects = discover_projects(db_path, _DB_LOCK)
    if not projects:
        return None
    # If MINION_COMPAT_PROJECT is set, use that; otherwise first project
    preferred = os.environ.get("MINION_COMPAT_PROJECT", "")
    if preferred:
        for p in projects:
            if p["name"] == preferred:
                return preferred
    return projects[0]["name"]


def handle_api_login(handler, db_path: str, **kwargs) -> None:
    """POST /api/login — bridge from username/password to cluster token auth.

    Accepts: {"username": "...", "password": "<cluster_token>"}
    The password field is validated as the cluster token.
    Returns: {"ok": true, "token": "<cluster_token>"} on success.
    """
    body = handler._parse_json_body()
    if not body:
        handler._json_response(400, {"error": "Invalid JSON body"})
        return

    password = body.get("password", "")
    expected = handler.token

    if not expected:
        # No auth configured — accept any login
        handler._json_response(200, {"ok": True, "token": "dev-mode"})
        return

    if password == expected:
        handler._json_response(200, {"ok": True, "token": expected})
    else:
        handler._json_response(401, {"ok": False, "error": "Invalid credentials"})


def handle_api_agents(handler, db_path: str, **kwargs) -> None:
    """GET /api/agents → delegates to /projects/{auto}/agents."""
    name = _auto_project_name(db_path)
    if not name:
        handler._json_response(200, [])  # empty — no projects registered
        return
    handle_project_agents(handler, db_path, name=name)


def handle_api_tasks(handler, db_path: str, **kwargs) -> None:
    """GET /api/tasks → delegates to /projects/{auto}/tasks."""
    name = _auto_project_name(db_path)
    if not name:
        handler._json_response(200, [])
        return
    handle_project_tasks(handler, db_path, name=name)


def handle_api_task_lineage(handler, db_path: str, task_id: str = "", **kwargs) -> None:
    """GET /api/task-lineage/{id} → delegates to /projects/{auto}/tasks/{id}/lineage."""
    name = _auto_project_name(db_path)
    if not name:
        handler._json_response(404, {"error": "No projects registered"})
        return
    handle_task_lineage(handler, db_path, name=name, task_id=task_id)


def handle_api_messages(handler, db_path: str, **kwargs) -> None:
    """GET /api/messages → delegates to /projects/{auto}/messages."""
    name = _auto_project_name(db_path)
    if not name:
        handler._json_response(200, [])
        return
    handle_project_messages(handler, db_path, name=name)


def handle_api_raid_log(handler, db_path: str, **kwargs) -> None:
    """GET /api/raid-log → delegates to /projects/{auto}/raid-log."""
    name = _auto_project_name(db_path)
    if not name:
        handler._json_response(200, [])
        return
    handle_project_raid_log(handler, db_path, name=name)


def handle_api_flows(handler, db_path: str, flow_type: str = "", **kwargs) -> None:
    """GET /api/flows/{type} → delegates to /projects/{auto}/flows/{type}."""
    name = _auto_project_name(db_path)
    if not name:
        handler._json_response(404, {"error": "No projects registered"})
        return
    handle_get_flow(handler, db_path, project_name=name, flow_type=flow_type)


def _auto_project_path(db_path: str) -> str | None:
    """Resolve the auto-detected project's full path."""
    name = _auto_project_name(db_path)
    if not name:
        return None
    return resolve_project_path(db_path, name, _DB_LOCK)


def handle_api_sprint(handler, db_path: str, **kwargs) -> None:
    """GET /api/sprint — sprint board data from .minion-swarm/sprint.json."""
    project_path = _auto_project_path(db_path)
    if not project_path:
        handler._json_response(200, {"sprint": None, "phases": []})
        return
    sprint_file = os.path.join(project_path, ".minion-swarm", "sprint.json")
    try:
        with open(sprint_file, "r") as f:
            data = json.loads(f.read())
        handler._json_response(200, data)
    except (OSError, json.JSONDecodeError):
        handler._json_response(200, {"sprint": None, "phases": []})


def handle_api_logs(handler, db_path: str, **kwargs) -> None:
    """GET /api/logs — all agent terminal logs from .minion-swarm/logs/."""
    project_path = _auto_project_path(db_path)
    if not project_path:
        handler._json_response(200, {})
        return
    logs_dir = os.path.join(project_path, ".minion-swarm", "logs")
    logs = {}
    try:
        for fname in os.listdir(logs_dir):
            if not fname.endswith(".log"):
                continue
            name = fname[:-4]
            try:
                with open(os.path.join(logs_dir, fname), "r") as f:
                    lines = f.read().split("\n")
                logs[name] = "\n".join(lines[-200:])
            except OSError:
                pass
    except OSError:
        pass
    handler._json_response(200, logs)


def handle_api_agent_log(handler, db_path: str, agent_name: str = "", **kwargs) -> None:
    """GET /api/logs/{agent} — per-agent log tail."""
    project_path = _auto_project_path(db_path)
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "", agent_name)
    if not project_path or not safe_name:
        handler._json_response(200, {"agent": safe_name, "lines": ["(no log file found)"]})
        return

    parsed = urlparse(handler.path)
    params = parse_qs(parsed.query)
    tail = min(int(params.get("tail", ["100"])[0]), 1000)

    log_file = os.path.join(project_path, ".minion-swarm", "logs", f"{safe_name}.log")
    try:
        with open(log_file, "r") as f:
            lines = f.read().split("\n")
        handler._json_response(200, {"agent": safe_name, "lines": lines[-tail:]})
    except OSError:
        handler._json_response(200, {"agent": safe_name, "lines": ["(no log file found)"]})
