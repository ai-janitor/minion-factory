"""Backlog endpoints — /projects/{name}/backlog.

Purpose: Expose backlog items for the dashboard — the pre-requirement pipeline.
Rationale: Backlog items are raw ideas/issues that get promoted to requirements.
           The dashboard needs visibility into the backlog to show the full
           pipeline from idea → requirement → task → completion.
Responsibility: Reads from the backlog table in project-local DBs.
Organization: Single list endpoint with priority/status filters.

Implementation order: 7th (depends on project_db).
New endpoint — not in ui/server.js.
"""

from __future__ import annotations


def register(router) -> None:
    """Register backlog endpoints with the router dispatch table.

    GET /projects/{name}/backlog → handle_list_backlog
    """
    # PSEUDO: router.add_get("/projects/{name}/backlog", handle_list_backlog)
    pass


def handle_list_backlog(handler, db_path: str, project_name: str = "", **kwargs) -> None:
    """GET /projects/{name}/backlog — backlog items with priority/status filters.

    Query params: ?priority=high|medium|low, ?status=open|promoted|killed|deferred
    Returns: id, file_path, type, title, priority, status, source,
             promoted_to, timestamps.
    """
    # PSEUDO: resolve project_name → project_path
    # PSEUDO: conn = project_db.get_project_db(project_path)
    # PSEUDO: build query: SELECT * FROM backlog
    # PSEUDO: if ?priority filter → add WHERE priority=?
    # PSEUDO: if ?status filter → add WHERE status=?
    # PSEUDO: ORDER BY priority DESC, created_at ASC
    # PSEUDO: return {"backlog": [...]}
    raise NotImplementedError
