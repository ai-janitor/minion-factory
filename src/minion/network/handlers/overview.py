"""System-wide overview endpoints — /overview, /alerts.

Purpose: Aggregate data across ALL registered projects for sys-lead monitoring.
Rationale: The sys-lead needs a single view of the entire fleet — agent health,
           task progress, requirement pipeline stages, and actionable alerts.
           These endpoints scan all project DBs and aggregate counts.
Responsibility: Cross-project aggregation reads. No writes.
Organization: Two endpoints — /overview for counts/summaries, /alerts for actionable items.

Implementation order: 8th (depends on project_db + discovery — needs all project DBs).
"""

from __future__ import annotations


def register(router) -> None:
    """Register overview endpoints with the router dispatch table.

    GET /overview → handle_overview
    GET /alerts   → handle_alerts
    """
    # PSEUDO: router.add_get("/overview", handle_overview)
    # PSEUDO: router.add_get("/alerts", handle_alerts)
    pass


def handle_overview(handler, db_path: str, **kwargs) -> None:
    """GET /overview — system-wide summary across all projects.

    Aggregates: project count, backlog counts by status, requirement counts by stage,
    task counts by status, agent counts by HP tier and class.

    HP tiers: healthy (>60%), wounded (30-60%), critical (<30%).
    """
    # PSEUDO: projects = discovery.discover_projects(db_path)
    # PSEUDO: init counters: backlog={}, requirements={}, tasks={}, agents={}
    # PSEUDO: for each project:
    #   conn = project_db.get_project_db(project_path) — may fail if DB missing
    #   if conn:
    #     aggregate backlog counts by status
    #     aggregate requirement counts by stage
    #     aggregate task counts by status
    #     aggregate agent counts:
    #       read HP, compute tier (healthy/wounded/critical)
    #       count by agent_class
    # PSEUDO: agents.total = sum across all projects
    # PSEUDO: alerts = _compute_alerts(projects, db_path) — reuse from handle_alerts
    # PSEUDO: return {"projects": N, "backlog": {...}, "requirements": {...},
    #                 "tasks": {...}, "agents": {...}, "alerts": [...]}
    raise NotImplementedError


def handle_alerts(handler, db_path: str, **kwargs) -> None:
    """GET /alerts — actionable alerts for sys-lead monitoring.

    Alert types:
    - stalled_requirement: requirement in same stage for >1 hour
    - hp_critical: agent HP below 30%
    - unread_messages: agent has unread messages older than 30 minutes
    - missing_flow_hint: backlog item has no flow_hint set
    """
    # PSEUDO: projects = discovery.discover_projects(db_path)
    # PSEUDO: alerts = []
    # PSEUDO: for each project:
    #   conn = project_db.get_project_db(project_path)
    #   if not conn: continue
    #
    #   # Stalled requirements
    #   SELECT requirements WHERE updated_at < now - 1 hour AND stage NOT IN terminal_stages
    #   for each → alerts.append({"type": "stalled_requirement", ...})
    #
    #   # HP critical agents
    #   SELECT agents with HP computation, WHERE hp_pct < 30
    #   for each → alerts.append({"type": "hp_critical", ...})
    #
    #   # Unread messages (from network DB, not project DB)
    #   SELECT messages WHERE read_flag=0 AND timestamp < now - 30min
    #   GROUP BY to_agent → alerts.append({"type": "unread_messages", ...})
    #
    #   # Missing flow hints
    #   SELECT backlog WHERE flow_hint IS NULL AND status='open'
    #   for each → alerts.append({"type": "missing_flow_hint", ...})
    #
    # PSEUDO: sort alerts by severity (critical > warning > info)
    # PSEUDO: return {"alerts": [...]}
    raise NotImplementedError
