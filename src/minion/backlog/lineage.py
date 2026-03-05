"""Backlog lineage — full audit trail from backlog item to task closure.

Purpose: Given a backlog ID or path, trace the complete lifecycle:
  backlog item → promotion → requirement → tasks → DAG stage transitions → closure.

Rationale: Leads need to verify DAG compliance mechanically, not by asking agents.
This assembles the audit trail from backlog, requirements, tasks, and transition_log.

Responsibility: Query-only — reads from DB, never writes.

Organization: Called by CLI (backlog_cmds.py) and API handlers.
"""

from __future__ import annotations

from typing import Any

from minion.db import get_db


def lineage(
    file_path: str | None = None,
    item_id: int | None = None,
) -> dict[str, Any]:
    """Assemble the full lineage of a backlog item.

    Accepts either file_path or item_id. Returns a dict with:
    - backlog: item metadata (who filed, when, type, priority, status)
    - promotion: who promoted, when, target requirement path
    - requirement: requirement record (id, stage, flow_type, created_by)
    - tasks: list of tasks linked to this requirement, each with:
      - task metadata (id, title, status, assigned_to, flow_type, class_required)
      - transitions: ordered list of stage changes from transition_log
      - comments: task_comments entries
    - timeline: flat chronological list of all events
    """

    # --- Resolve backlog item ---
    conn = get_db()
    try:
        if item_id is not None:
            row = conn.execute(
                "SELECT * FROM backlog WHERE id = ?", (item_id,)
            ).fetchone()
        elif file_path is not None:
            file_path = file_path.strip("/")
            row = conn.execute(
                "SELECT * FROM backlog WHERE file_path = ?", (file_path,)
            ).fetchone()
        else:
            raise ValueError("Provide --id or a file path.")

        if not row:
            identifier = f"id={item_id}" if item_id is not None else f"path='{file_path}'"
            raise ValueError(f"Backlog item not found: {identifier}")

        backlog_id = row["id"]
        backlog_data = {
            "id": backlog_id,
            "file_path": row["file_path"],
            "type": row["type"],
            "title": row["title"],
            "priority": row["priority"],
            "status": row["status"],
            "source": row["source"],
            "created_by": row["created_by"],
            "created_at": row["created_at"],
            "flow_hint": row["flow_hint"],
        }

        result: dict[str, Any] = {"backlog": backlog_data}
        timeline: list[dict[str, Any]] = []

        # Timeline: backlog created
        timeline.append({
            "event": "backlog_created",
            "timestamp": row["created_at"],
            "agent": row["created_by"] or row["source"],
            "detail": f"Filed as {row['type']}: {row['title']}",
        })

        # --- Promotion event ---
        promoted_to = row["promoted_to"]
        # Check for promoted_by column (may not exist on older DBs)
        promoted_by = None
        try:
            promoted_by = row["promoted_by"]
        except (IndexError, KeyError):
            pass

        if row["status"] == "promoted" and promoted_to:
            # Get promotion timestamp from transition_log if available
            promo_transition = conn.execute(
                "SELECT triggered_by, created_at FROM transition_log "
                "WHERE entity_id = ? AND entity_type = 'backlog' AND to_status = 'promoted' "
                "ORDER BY created_at DESC LIMIT 1",
                (backlog_id,),
            ).fetchone()

            promo_agent = promoted_by or (promo_transition["triggered_by"] if promo_transition else None)
            promo_time = promo_transition["created_at"] if promo_transition else row["updated_at"]

            result["promotion"] = {
                "promoted_to": promoted_to,
                "promoted_by": promo_agent,
                "promoted_at": promo_time,
            }

            timeline.append({
                "event": "promoted",
                "timestamp": promo_time,
                "agent": promo_agent,
                "detail": f"Promoted to requirement: {promoted_to}",
            })

            # --- Requirement record ---
            req_row = conn.execute(
                "SELECT id, file_path, origin, stage, flow_type, created_by, created_at "
                "FROM requirements WHERE file_path = ?",
                (promoted_to,),
            ).fetchone()

            if req_row:
                req_id = req_row["id"]
                result["requirement"] = {
                    "id": req_id,
                    "file_path": req_row["file_path"],
                    "origin": req_row["origin"],
                    "stage": req_row["stage"],
                    "flow_type": req_row["flow_type"],
                    "created_by": req_row["created_by"],
                    "created_at": req_row["created_at"],
                }

                # --- Tasks linked to this requirement ---
                task_rows = conn.execute(
                    "SELECT id, title, status, assigned_to, created_by, flow_type, "
                    "class_required, result_file, created_at, updated_at "
                    "FROM tasks WHERE requirement_id = ? ORDER BY id",
                    (req_id,),
                ).fetchall()

                tasks_out: list[dict[str, Any]] = []
                for task in task_rows:
                    task_id = task["id"]
                    task_data: dict[str, Any] = {
                        "id": task_id,
                        "title": task["title"],
                        "status": task["status"],
                        "assigned_to": task["assigned_to"],
                        "created_by": task["created_by"],
                        "flow_type": task["flow_type"],
                        "class_required": task["class_required"],
                        "result_file": task["result_file"],
                        "created_at": task["created_at"],
                    }

                    # Timeline: task created
                    timeline.append({
                        "event": "task_created",
                        "timestamp": task["created_at"],
                        "agent": task["created_by"],
                        "detail": f"Task #{task_id}: {task['title']}",
                    })

                    # Stage transitions for this task
                    transitions = conn.execute(
                        "SELECT from_status, to_status, triggered_by, created_at "
                        "FROM transition_log "
                        "WHERE entity_id = ? AND entity_type = 'task' "
                        "ORDER BY created_at",
                        (task_id,),
                    ).fetchall()

                    task_data["transitions"] = [
                        {
                            "from": t["from_status"],
                            "to": t["to_status"],
                            "by": t["triggered_by"],
                            "at": t["created_at"],
                        }
                        for t in transitions
                    ]

                    for t in transitions:
                        timeline.append({
                            "event": "task_transition",
                            "timestamp": t["created_at"],
                            "agent": t["triggered_by"],
                            "detail": f"Task #{task_id}: {t['from_status']} -> {t['to_status']}",
                        })

                    # Comments for this task
                    comments = conn.execute(
                        "SELECT agent_name, phase, comment, created_at "
                        "FROM task_comments WHERE task_id = ? ORDER BY created_at",
                        (task_id,),
                    ).fetchall()

                    if comments:
                        task_data["comments"] = [
                            {
                                "agent": c["agent_name"],
                                "phase": c["phase"],
                                "comment": c["comment"],
                                "at": c["created_at"],
                            }
                            for c in comments
                        ]

                    tasks_out.append(task_data)

                if tasks_out:
                    result["tasks"] = tasks_out

        elif row["status"] in ("killed", "deferred"):
            result["disposition"] = {
                "status": row["status"],
                "updated_at": row["updated_at"],
            }
            timeline.append({
                "event": row["status"],
                "timestamp": row["updated_at"],
                "agent": None,
                "detail": f"Backlog item {row['status']}",
            })

        # Sort timeline chronologically
        timeline.sort(key=lambda e: e["timestamp"])
        result["timeline"] = timeline

        return result

    finally:
        conn.close()
