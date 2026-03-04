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


def register(router) -> None:
    """Register requirements endpoints with the router dispatch table.

    GET /projects/{name}/requirements              → handle_list_requirements
    GET /projects/{name}/requirements/{id}/lineage  → handle_requirement_lineage
    """
    # PSEUDO: router.add_get("/projects/{name}/requirements", handle_list_requirements)
    # PSEUDO: router.add_get("/projects/{name}/requirements/{id}/lineage", handle_requirement_lineage)
    pass


def handle_list_requirements(handler, db_path: str, project_name: str = "", **kwargs) -> None:
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
    raise NotImplementedError


def handle_requirement_lineage(handler, db_path: str, project_name: str = "",
                               requirement_id: str = "", **kwargs) -> None:
    """GET /projects/{name}/requirements/{id}/lineage — full requirement DAG history.

    Returns: requirement detail, stage_history (every transition with timestamp
    and who advanced it), children (recursive tree), linked_tasks, completion_pct.

    Stage history from requirements.updated_at deltas and transition_log table.
    """
    # PSEUDO: resolve project_name → project_path
    # PSEUDO: conn = project_db.get_project_db(project_path)
    # PSEUDO: SELECT requirement by id → 404 if not found
    # PSEUDO: build stage_history:
    #   if transition_log table exists:
    #     SELECT * FROM transition_log WHERE entity_type='requirement' AND entity_id=id
    #   else:
    #     reconstruct from requirement updated_at timestamps
    # PSEUDO: find children: SELECT * FROM requirements WHERE parent_id=id (recursive)
    # PSEUDO: find linked tasks: SELECT * FROM tasks WHERE requirement_path matches
    # PSEUDO: compute completion_pct
    # PSEUDO: return {"requirement": {...}, "stage_history": [...],
    #                 "children": [...], "linked_tasks": [...], "completion_pct": N}
    raise NotImplementedError
