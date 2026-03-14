"""Requirements endpoints — /projects/{name}/requirements, /requirements/{id}/lineage.

Purpose: Expose requirement stage tracking and DAG lineage for the dashboard.
Rationale: Requirements flow through a multi-stage pipeline (seed → itemizing →
           itemized → investigating → findings_ready → decomposing → tasked →
           in_progress → completed). The dashboard needs both the current state
           and the full transition history.
Responsibility: All reads from the requirements table and related stage history
                in project-local DBs.
Organization: Two endpoints — list with filters, and single-requirement lineage.

Implementation order: 6th (depends on project_db).
New endpoint — not in ui/server.js.
"""

from __future__ import annotations

import logging
import sqlite3
import sqlite3
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)

from minion.network.handlers._resolve_project_or_404 import resolve_project_or_404


def register(router) -> None:
    """Register requirements endpoints with the router dispatch table.

    GET /projects/{name}/requirements              → handle_list_requirements
    GET /projects/{name}/requirements/{id}/lineage  → handle_requirement_lineage
    """
    # PSEUDO: router.add_get("/projects/{name}/requirements", handle_list_requirements)
    # PSEUDO: router.add_get("/projects/{name}/requirements/{id}/lineage", handle_requirement_lineage)
    router.add_get("/projects/{name}/requirements", handle_list_requirements)
    router.add_get("/projects/{name}/requirements/{id}/lineage", handle_requirement_lineage)


def handle_list_requirements(handler, db_path: str, name: str = "", **kwargs) -> None:
    """GET /projects/{name}/requirements — all requirements with stage tracking.

    Query params: ?stage=, ?flow_type=
    Returns: id, file_path, origin, stage, flow_type, parent_id, timestamps,
             linked_task_count, completion_pct.
    """
    # PSEUDO: resolve project_name → project_path
    # PSEUDO: conn = project_db.get_project_db(project_path)
    # PSEUDO: SELECT requirements with optional stage/flow_type filters
    # PSEUDO: for each requirement:
    #   count linked tasks (tasks WHERE requirement_path matches)
    #   compute completion_pct = closed_tasks / total_tasks * 100
    # PSEUDO: return {"requirements": [...]}
    project_path, conn = resolve_project_or_404(handler, db_path, name)
    if conn is None:
        return

    parsed = urlparse(handler.path)
    params = parse_qs(parsed.query)
    stage_filter = params.get("stage", [None])[0]
    flow_filter = params.get("flow_type", [None])[0]

    query = "SELECT id, file_path, origin, stage, flow_type, parent_id, created_by, created_at, updated_at FROM requirements"
    conditions = []
    args = []
    if stage_filter:
        conditions.append("stage = ?")
        args.append(stage_filter)
    if flow_filter:
        conditions.append("flow_type = ?")
        args.append(flow_filter)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY id ASC"

    try:
        rows = conn.execute(query, args).fetchall()
    except sqlite3.DatabaseError as e:
        handler._json_response(500, {"error": f"DB query failed: {e}"})
        return

    requirements = []
    for row in rows:
        req = dict(row)
        # Count linked tasks
        try:
            task_rows = conn.execute(
                "SELECT COUNT(*) as total, SUM(CASE WHEN status = 'closed' THEN 1 ELSE 0 END) as closed "
                "FROM tasks WHERE requirement_id = ?",
                (req["id"],),
            ).fetchone()
            total = task_rows["total"] if task_rows else 0
            closed = task_rows["closed"] if task_rows else 0
            req["linked_task_count"] = total
            req["completion_pct"] = round(closed / total * 100) if total > 0 else 0
        except sqlite3.DatabaseError:
            req["linked_task_count"] = 0
            req["completion_pct"] = 0
        requirements.append(req)

    handler._json_response(200, {"requirements": requirements})


def handle_requirement_lineage(handler, db_path: str, name: str = "",
                               id: str = "", **kwargs) -> None:
    """GET /projects/{name}/requirements/{id}/lineage — full requirement DAG history.

    Returns: requirement detail, stage_history (every transition with timestamp
    and who advanced it), children (recursive tree), linked_tasks, completion_pct.

    Stage history from transition_log table if available.
    """
    # PSEUDO: resolve project_name → project_path
    # PSEUDO: conn = project_db.get_project_db(project_path)
    # PSEUDO: SELECT requirement by id → 404 if not found
    # PSEUDO: build stage_history:
    #   if transition_log table exists:
    #     SELECT * FROM transition_log WHERE entity_type='requirement' AND entity_id=id
    #   else:
    #     return empty history
    # PSEUDO: find children: SELECT * FROM requirements WHERE parent_id=id
    # PSEUDO: find linked tasks: SELECT * FROM tasks WHERE requirement_id=id
    # PSEUDO: compute completion_pct
    # PSEUDO: return {"requirement": {...}, "stage_history": [...],
    #                 "children": [...], "linked_tasks": [...], "completion_pct": N}
    project_path, conn = resolve_project_or_404(handler, db_path, name)
    if conn is None:
        return

    try:
        req_id = int(id)
    except (ValueError, TypeError):
        handler._json_response(400, {"error": "Invalid requirement ID"})
        return

    try:
        row = conn.execute("SELECT * FROM requirements WHERE id = ?", (req_id,)).fetchone()
    except sqlite3.DatabaseError as e:
        handler._json_response(500, {"error": f"DB query failed: {e}"})
        return

    if not row:
        handler._json_response(404, {"error": f"Requirement {req_id} not found"})
        return

    req = dict(row)

    # Stage history from transition_log
    stage_history = []
    try:
        history_rows = conn.execute(
            "SELECT from_status, to_status, agent, timestamp "
            "FROM transition_log WHERE entity_type = 'requirement' AND entity_id = ? "
            "ORDER BY timestamp ASC",
            (req_id,),
        ).fetchall()
        stage_history = [dict(r) for r in history_rows]
    except sqlite3.DatabaseError as e:
        logger.error("Failed to fetch stage history for requirement %s: %s", req_id, e)

    # Children
    children = []
    try:
        child_rows = conn.execute(
            "SELECT id, file_path, stage, created_at, updated_at FROM requirements WHERE parent_id = ?",
            (req_id,),
        ).fetchall()
        children = [dict(r) for r in child_rows]
    except sqlite3.DatabaseError as e:
        logger.error("Failed to fetch children for requirement %s: %s", req_id, e)

    # Linked tasks
    linked_tasks = []
    try:
        task_rows = conn.execute(
            "SELECT id, title, status, assigned_to, created_at, updated_at "
            "FROM tasks WHERE requirement_id = ?",
            (req_id,),
        ).fetchall()
        linked_tasks = [dict(r) for r in task_rows]
    except sqlite3.DatabaseError as e:
        logger.error("Failed to fetch linked tasks for requirement %s: %s", req_id, e)

    total = len(linked_tasks)
    closed = sum(1 for t in linked_tasks if t.get("status") == "closed")
    completion_pct = round(closed / total * 100) if total > 0 else 0

    handler._json_response(200, {
        "requirement": req,
        "stage_history": stage_history,
        "children": children,
        "linked_tasks": linked_tasks,
        "completion_pct": completion_pct,
    })
