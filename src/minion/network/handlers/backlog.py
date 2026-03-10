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

from urllib.parse import urlparse, parse_qs

from minion.network.handlers._resolve_project_or_404 import resolve_project_or_404


def register(router) -> None:
    """Register backlog endpoints with the router dispatch table.

    GET /projects/{name}/backlog → handle_list_backlog
    """
    # PSEUDO: router.add_get("/projects/{name}/backlog", handle_list_backlog)
    router.add_get("/projects/{name}/backlog", handle_list_backlog)


def handle_list_backlog(handler, db_path: str, name: str = "", **kwargs) -> None:
    """GET /projects/{name}/backlog — backlog items with priority/status filters.

    Query params: ?priority=high|medium|low, ?status=open|promoted|killed|deferred
    Returns: id, file_path, type, title, priority, status, source,
             promoted_to, flow_hint, timestamps.
    """
    # PSEUDO: resolve project_name → project_path
    # PSEUDO: conn = project_db.get_project_db(project_path)
    # PSEUDO: build query: SELECT * FROM backlog
    # PSEUDO: if ?priority filter → add WHERE priority=?
    # PSEUDO: if ?status filter → add WHERE status=?
    # PSEUDO: ORDER BY priority DESC, created_at ASC
    # PSEUDO: return {"backlog": [...]}
    project_path, conn = resolve_project_or_404(handler, db_path, name)
    if conn is None:
        return

    parsed = urlparse(handler.path)
    params = parse_qs(parsed.query)
    priority_filter = params.get("priority", [None])[0]
    status_filter = params.get("status", [None])[0]

    query = "SELECT id, file_path, type, title, priority, status, source, promoted_to, flow_hint, created_by, created_at, updated_at FROM backlog"
    conditions = []
    bind = []
    if priority_filter:
        conditions.append("priority = ?")
        bind.append(priority_filter)
    if status_filter:
        conditions.append("status = ?")
        bind.append(status_filter)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY CASE priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 WHEN 'low' THEN 3 ELSE 4 END, created_at ASC"

    cursor = conn.execute(query, bind)
    cols = [d[0] for d in cursor.description]
    rows = [dict(zip(cols, row)) for row in cursor.fetchall()]

    handler._json_response(200, {"backlog": rows})
