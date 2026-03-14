"""backlog fast-track — composite add+promote+define in one shot.

Purpose: Eliminate the 3-command chain (backlog add → backlog promote → task define)
that causes error-retry cycles due to flag mismatches between commands.

Rationale: The promote→define pipeline has 5 known friction points: flag name
mismatches, missing battle-plan warnings, and undiscoverable sequencing. This
composite command absorbs all three steps and returns a single result dict.

Responsibility: Orchestrate add+promote+define for one backlog item. Returns a
combined JSON with backlog_id, requirement_id, requirement_path, task_id.
NOT responsible for individual step validation beyond what each step enforces.

Organization: Single public function `fast_track()`. Calls the existing `add`,
`promote`, and `define_task` functions — does not duplicate their logic.
"""

from __future__ import annotations

from typing import Any


def fast_track(
    agent_name: str,
    item_type: str,
    title: str,
    description: str,
    priority: str = "medium",
    task_type: str = "feature",
    flow_hint: str = "",
    req_flow: str = "requirement-lite",
    slug: str | None = None,
) -> dict[str, Any]:
    """Composite command: backlog add → backlog promote → task define.

    All three steps run in sequence. If any step fails, the error is returned
    with a 'failed_at' field indicating which step failed.

    Steps:
    1. backlog add — create the backlog item
    2. backlog promote — promote to requirement (requires lead class)
    3. task define — create implementation task linked to requirement

    Returns combined result with backlog_id, requirement_id, requirement_path, task_id.
    Warnings from promote (e.g. missing battle plan) surface as top-level 'warnings' list.
    """
    result: dict[str, Any] = {}

    # --- Step 1: backlog add ---
    from minion.backlog.add_item import add as _add
    try:
        add_result = _add(
            item_type=item_type,
            title=title,
            source=agent_name,
            description=description,
            priority=priority,
            flow_hint=flow_hint or task_type,
        )
    except Exception as e:
        return {"error": str(e), "failed_at": "backlog_add"}

    if "error" in add_result:
        add_result["failed_at"] = "backlog_add"
        return add_result

    backlog_id = add_result.get("id")
    backlog_path = add_result.get("file_path", "")
    result["backlog_id"] = backlog_id
    result["backlog_path"] = backlog_path

    # --- Step 2: backlog promote ---
    from minion.backlog.promote import promote as _promote
    try:
        promote_result = _promote(
            file_path=backlog_path,
            origin=None,
            slug=slug,
            flow=req_flow,
            agent_name=agent_name,
        )
    except ValueError as e:
        return {"error": str(e), "failed_at": "backlog_promote", "backlog_id": backlog_id, "backlog_path": backlog_path}
    except Exception as e:
        return {"error": str(e), "failed_at": "backlog_promote", "backlog_id": backlog_id, "backlog_path": backlog_path}

    if "error" in promote_result:
        promote_result["failed_at"] = "backlog_promote"
        promote_result["backlog_id"] = backlog_id
        return promote_result

    requirement_id = promote_result.get("requirement_id")
    req_file_path = promote_result.get("requirement", {}).get("file_path") or promote_result.get("requirement", {}).get("path")
    result["requirement_id"] = requirement_id
    result["requirement_path"] = req_file_path

    # Surface battle-plan and other warnings from promote
    if "warnings" in promote_result:
        result["warnings"] = promote_result["warnings"]

    # --- Step 3: task define ---
    from minion.tasks.define import define_task
    try:
        define_result = define_task(
            agent_name=agent_name,
            title=title,
            description=description,
            task_type=task_type,
            requirement_id=requirement_id,
        )
    except Exception as e:
        return {
            **result,
            "error": str(e),
            "failed_at": "task_define",
        }

    if "error" in define_result:
        define_result["failed_at"] = "task_define"
        define_result.update(result)
        return define_result

    result["task_id"] = define_result.get("task_id")
    result["task_slug"] = define_result.get("title", title)
    result["status"] = "fast_tracked"
    result["flow"] = define_result.get("flow", task_type)
    result["dag"] = define_result.get("dag", "")

    return result
