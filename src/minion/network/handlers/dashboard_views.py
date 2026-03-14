"""Server-rendered dashboard views — Jinja2 templates for agents, tasks, health, messages.

Purpose: Render HTML dashboard pages using Jinja2 templates and project-local DB data.
Rationale: SU-22 consolidation — provides a server-side rendered alternative to the
           existing JavaScript SPA dashboard. Server-side rendering works without
           CORS, token management, or JS runtime. Ideal for quick status checks.
Responsibility: Route /dashboard/* paths to the correct template with the correct data.
Organization: Single dispatch function that maps URL subpaths to template + query pairs.

Pseudo-logic:
  1. Parse the /dashboard/{page} path
  2. Look up the Jinja2 template for that page
  3. Query the project DB (discovered from first registered project)
  4. Render template with query results
  5. Return HTML string (caller sends as response)
"""

from __future__ import annotations

import logging
import os
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

# Jinja2 template environment — initialized once on first use
_env = None


def _get_env():
    """Lazy-initialize Jinja2 environment with templates directory."""
    global _env
    if _env is None:
        from jinja2 import Environment, FileSystemLoader
        templates_dir = Path(__file__).resolve().parent.parent / "templates"
        _env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=True,
        )
    return _env


def _get_first_project_db(network_db_path: str):
    """Get a connection to the first discovered project's DB.

    Pseudo-logic:
      1. Use discovery.discover_projects() to find registered projects
      2. For the first project with a valid DB, open connection
      3. Return (conn, db_path) or (None, None)
    """
    try:
        from minion.network.server import _DB_LOCK
        from minion.network.discovery import discover_projects
        from minion.network.project_db import get_project_db

        projects = discover_projects(network_db_path, _DB_LOCK)
        for proj in projects:
            conn = get_project_db(proj["path"])
            if conn:
                db_path = os.path.join(proj["path"], ".work", "minion.db")
                return conn, db_path
    except (ImportError, OSError, sqlite3.Error) as e:
        logger.warning("Failed to discover project DB: %s: %s", type(e).__name__, e)
    return None, None


def handle_dashboard_page(path: str, network_db_path: str) -> str | None:
    """Dispatch /dashboard/{page} to the correct template.

    Returns rendered HTML string, or None if path is not a dashboard route.

    Pseudo-logic:
      1. Strip /dashboard prefix, extract page name
      2. Map page to (template_name, query_function)
      3. Get project DB connection
      4. Run query, render template
      5. Return HTML
    """
    # PSEUDO: normalize path — /dashboard/agents → page = "agents"
    clean = path.rstrip("/")
    if clean == "/dashboard":
        # Default: redirect to agents
        clean = "/dashboard/agents"

    parts = clean.split("/")
    # Expected: ["", "dashboard", "page"]
    if len(parts) < 3:
        return None

    page = parts[2]

    # PSEUDO: map page name to template + query
    if page == "agents":
        return _render_agents(network_db_path)
    elif page == "tasks":
        return _render_tasks(network_db_path)
    elif page == "health":
        return _render_health(network_db_path)
    elif page == "messages":
        return _render_messages(network_db_path)
    else:
        return None


def _render_agents(network_db_path: str) -> str:
    """Render agents dashboard page."""
    env = _get_env()
    template = env.get_template("dashboard/agents.html")

    conn, db_path = _get_first_project_db(network_db_path)
    agents = []
    if conn:
        try:
            from minion.dashboard.queries import get_agent_summary
            agents = get_agent_summary(conn)
        except (ImportError, sqlite3.DatabaseError) as e:
            logger.error("Failed to fetch agent summary for dashboard: %s", e)

    return template.render(page="agents", agents=agents)


def _render_tasks(network_db_path: str) -> str:
    """Render tasks pipeline dashboard page."""
    env = _get_env()
    template = env.get_template("dashboard/tasks.html")

    conn, db_path = _get_first_project_db(network_db_path)
    pipeline = {}
    if conn:
        try:
            from minion.dashboard.queries import get_task_pipeline
            pipeline = get_task_pipeline(conn)
        except (ImportError, sqlite3.DatabaseError) as e:
            logger.error("Failed to fetch task pipeline for dashboard: %s", e)

    return template.render(page="tasks", pipeline=pipeline)


def _render_health(network_db_path: str) -> str:
    """Render system health dashboard page."""
    env = _get_env()
    template = env.get_template("dashboard/health.html")

    conn, db_path = _get_first_project_db(network_db_path)
    stats = {"tables": {}, "agents": {}, "tasks": {}, "db_size_bytes": 0}
    if conn:
        try:
            from minion.dashboard.queries import get_system_stats
            stats = get_system_stats(conn, db_path or "")
        except (ImportError, sqlite3.DatabaseError) as e:
            logger.error("Failed to fetch system stats for dashboard: %s", e)

    return template.render(page="health", stats=stats)


def _render_messages(network_db_path: str) -> str:
    """Render recent messages dashboard page."""
    env = _get_env()
    template = env.get_template("dashboard/messages.html")

    conn, db_path = _get_first_project_db(network_db_path)
    messages = []
    if conn:
        try:
            from minion.dashboard.queries import get_recent_messages
            messages = get_recent_messages(conn)
        except (ImportError, sqlite3.DatabaseError) as e:
            logger.error("Failed to fetch recent messages for dashboard: %s", e)

    return template.render(page="messages", messages=messages)
