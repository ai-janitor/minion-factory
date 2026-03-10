"""Shared project resolution helper — resolve project name to DB connection or 404.

Purpose: Eliminate duplication of _resolve_or_404 across handler modules.
Rationale: projects.py, requirements.py, and backlog.py all need the same
           pattern: resolve project_name → project_path → DB connection, or
           send a 404 JSON error. Centralizing avoids 3+ copies of the same logic.
Responsibility: Single function that resolves a project name and returns
                (project_path, conn) or sends a 404 and returns (None, None).
Organization: Imported by all handler modules that operate on project-scoped data.
"""

from __future__ import annotations

from minion.network.server import _DB_LOCK
from minion.network.discovery import resolve_project_path
from minion.network.project_db import get_project_db


def resolve_project_or_404(handler, db_path: str, project_name: str):
    """Resolve project_name to path and get DB connection, or send 404.

    Returns (project_path, conn). If resolution fails at any step, sends a JSON
    404 response via handler._json_response and returns (None, None) or
    (project_path, None) so callers can short-circuit with `if conn is None: return`.
    """
    # PSEUDO: look up project_name in network DB → project_path
    # PSEUDO: if not found → 404 "Project not found"
    # PSEUDO: get cached DB connection for project_path
    # PSEUDO: if no .work/minion.db → 404 "no minion.db"
    # PSEUDO: return (project_path, conn)
    project_path = resolve_project_path(db_path, project_name, _DB_LOCK)
    if not project_path:
        handler._json_response(404, {"error": f"Project '{project_name}' not found"})
        return None, None
    conn = get_project_db(project_path)
    if conn is None:
        handler._json_response(404, {
            "error": f"Project '{project_name}' has no .work/minion.db",
            "path": project_path,
        })
        return project_path, None
    return project_path, conn
