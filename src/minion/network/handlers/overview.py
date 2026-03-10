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

from datetime import datetime

from minion.network.server import _DB_LOCK
from minion.network.discovery import discover_projects
from minion.network.project_db import get_project_db


def register(router) -> None:
    """Register overview endpoints with the router dispatch table.

    GET /overview → handle_overview
    GET /alerts   → handle_alerts
    """
    # PSEUDO: router.add_get("/overview", handle_overview)
    # PSEUDO: router.add_get("/alerts", handle_alerts)
    router.add_get("/overview", handle_overview)
    router.add_get("/alerts", handle_alerts)


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
    # PSEUDO: return {"projects": N, "backlog": {...}, "requirements": {...},
    #                 "tasks": {...}, "agents": {...}}
    projects = discover_projects(db_path, _DB_LOCK)
    result = {
        "project_count": len(projects),
        "projects": [p["name"] for p in projects],
        "requirements": {},
        "tasks": {},
        "agents": {"total": 0, "by_class": {}, "by_hp_tier": {"healthy": 0, "wounded": 0, "critical": 0, "unknown": 0}},
    }

    for proj in projects:
        conn = get_project_db(proj["path"])
        if not conn:
            continue
        try:
            # Requirement counts by stage
            for row in conn.execute("SELECT stage, COUNT(*) as cnt FROM requirements GROUP BY stage").fetchall():
                stage = row["stage"]
                result["requirements"][stage] = result["requirements"].get(stage, 0) + row["cnt"]

            # Task counts by status
            for row in conn.execute("SELECT status, COUNT(*) as cnt FROM tasks GROUP BY status").fetchall():
                status = row["status"]
                result["tasks"][status] = result["tasks"].get(status, 0) + row["cnt"]

            # Agent counts
            for row in conn.execute("SELECT agent_class, hp_turn_input, hp_tokens_limit FROM agents").fetchall():
                result["agents"]["total"] += 1
                cls = row["agent_class"] or "unknown"
                result["agents"]["by_class"][cls] = result["agents"]["by_class"].get(cls, 0) + 1
                # HP tier
                raw = row["hp_turn_input"]
                limit = row["hp_tokens_limit"]
                if raw is not None and limit and limit > 0:
                    hp_pct = max(0, 100 - (raw / limit * 100))
                    if hp_pct > 60:
                        result["agents"]["by_hp_tier"]["healthy"] += 1
                    elif hp_pct > 30:
                        result["agents"]["by_hp_tier"]["wounded"] += 1
                    else:
                        result["agents"]["by_hp_tier"]["critical"] += 1
                else:
                    result["agents"]["by_hp_tier"]["unknown"] += 1
        except Exception:
            pass

    handler._json_response(200, result)


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
    #   # Unread messages (from project DB)
    #   SELECT messages WHERE read_flag=0 AND timestamp < now - 30min
    #   GROUP BY to_agent → alerts.append({"type": "unread_messages", ...})
    #
    # PSEUDO: sort alerts by severity (critical > warning > info)
    # PSEUDO: return {"alerts": [...]}
    projects = discover_projects(db_path, _DB_LOCK)
    alerts = []
    now = datetime.now()
    terminal_stages = {"completed", "killed", "deferred"}

    for proj in projects:
        conn = get_project_db(proj["path"])
        if not conn:
            continue
        project_name = proj["name"]
        try:
            # Stalled requirements (>1 hour in same stage, not terminal)
            for row in conn.execute(
                "SELECT id, file_path, stage, updated_at FROM requirements "
                "WHERE stage NOT IN ('completed','killed','deferred')"
            ).fetchall():
                try:
                    from minion.db.timestamp_and_agent_registry import parse_iso_to_naive_local
                    updated = parse_iso_to_naive_local(row["updated_at"])
                    age_mins = (now - updated).total_seconds() / 60
                    if age_mins > 60:
                        alerts.append({
                            "type": "stalled_requirement",
                            "severity": "warning",
                            "project": project_name,
                            "requirement_id": row["id"],
                            "file_path": row["file_path"],
                            "stage": row["stage"],
                            "stalled_minutes": round(age_mins),
                        })
                except (ValueError, TypeError):
                    pass

            # HP critical agents
            for row in conn.execute(
                "SELECT name, hp_turn_input, hp_tokens_limit FROM agents"
            ).fetchall():
                raw = row["hp_turn_input"]
                limit = row["hp_tokens_limit"]
                if raw is not None and limit and limit > 0:
                    hp_pct = max(0, 100 - (raw / limit * 100))
                    if hp_pct < 30:
                        alerts.append({
                            "type": "hp_critical",
                            "severity": "critical",
                            "project": project_name,
                            "agent": row["name"],
                            "hp_pct": round(hp_pct),
                        })

            # Unread messages >30min old
            for row in conn.execute(
                "SELECT to_agent, COUNT(*) as cnt, MIN(timestamp) as oldest "
                "FROM messages WHERE read_flag = 0 GROUP BY to_agent"
            ).fetchall():
                try:
                    from minion.db.timestamp_and_agent_registry import parse_iso_to_naive_local
                    oldest = parse_iso_to_naive_local(row["oldest"])
                    age_mins = (now - oldest).total_seconds() / 60
                    if age_mins > 30:
                        alerts.append({
                            "type": "unread_messages",
                            "severity": "warning",
                            "project": project_name,
                            "agent": row["to_agent"],
                            "count": row["cnt"],
                            "oldest_minutes": round(age_mins),
                        })
                except (ValueError, TypeError):
                    pass
        except Exception:
            pass

    # Sort: critical first, then warning
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    alerts.sort(key=lambda a: severity_order.get(a.get("severity", "info"), 2))
    handler._json_response(200, {"alerts": alerts})


def handle_task_lineage(handler, db_path: str, task_id: str = "", **kwargs) -> None:
    """GET /tasks/{task_id}/lineage — DAG transition history for a task.

    Returns ordered list of transitions: from_status, to_status, agent, timestamp.
    Queries transition_log table from all discovered project DBs.

    Time complexity: O(P * T) where P = projects, T = transitions per task.
    """
    if not task_id:
        handler._json_response(400, {"error": "task_id is required in URL: /tasks/{task_id}/lineage"})
        return

    try:
        tid = int(task_id)
    except (ValueError, TypeError):
        handler._json_response(400, {"error": f"task_id must be an integer, got '{task_id}'"})
        return

    projects = discover_projects(db_path, _DB_LOCK)
    transitions = []

    for proj in projects:
        conn = get_project_db(proj["path"])
        if not conn:
            continue
        try:
            rows = conn.execute(
                "SELECT entity_id, from_status, to_status, triggered_by, created_at "
                "FROM transition_log WHERE entity_id = ? AND entity_type = 'task' "
                "ORDER BY created_at ASC",
                (tid,),
            ).fetchall()
            for row in rows:
                transitions.append({
                    "project": proj["name"],
                    "task_id": tid,
                    "from_status": row["from_status"],
                    "to_status": row["to_status"],
                    "agent": row["triggered_by"],
                    "timestamp": row["created_at"],
                })
        except Exception:
            pass

    handler._json_response(200, {"task_id": tid, "transitions": transitions})
