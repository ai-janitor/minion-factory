"""Decompose a parent requirement into children from a spec file.

One command replaces ~5 manual steps per child: mkdir, write README,
register, create task, link task. A 3-child decomposition goes from
~15 operations to one.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from minion.db import get_db, _get_db_path
from minion.requirements.crud import register, link_task, update_stage
from minion.tasks.create_task import create_task


def _load_spec(spec_path: str) -> dict:
    """Load and validate a decomposition spec file (YAML or JSON)."""
    with open(spec_path) as f:
        spec = yaml.safe_load(f)

    if not isinstance(spec, dict) or "children" not in spec:
        raise ValueError("Spec file must contain a 'children' key with a list of child definitions.")

    children = spec["children"]
    if not isinstance(children, list) or len(children) == 0:
        raise ValueError("Spec 'children' must be a non-empty list.")

    for i, child in enumerate(children):
        if "slug" not in child:
            raise ValueError(f"Child {i + 1} missing required 'slug' field.")
        if "title" not in child:
            raise ValueError(f"Child {i + 1} missing required 'title' field.")

    return spec


def _resolve_work_dir() -> Path:
    """Derive .work/ directory from the DB path."""
    return Path(_get_db_path()).parent


def decompose(parent_path: str, spec: dict, agent_name: str = "lead") -> dict[str, Any]:
    """Decompose a parent requirement into children defined in spec.

    For each child: creates folder, writes README, registers requirement,
    creates task, links task. Then advances parent to 'tasked'.

    Args:
        parent_path: Parent requirement's file_path (relative to .work/requirements/).
        spec: Parsed spec dict with 'children' list.
        agent_name: Agent performing the decomposition (must be registered).

    Returns:
        Summary dict with status, children created, and task IDs.
    """
    parent_path = parent_path.rstrip("/")
    work_dir = _resolve_work_dir()
    req_root = work_dir / "requirements"

    # Validate parent exists in DB
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, stage FROM requirements WHERE file_path = ?", (parent_path,))
        row = cursor.fetchone()
        if not row:
            return {"error": f"Parent requirement '{parent_path}' not found. Register it first."}

        parent_stage = row["stage"]
        # Valid stages for decomposition: decomposing, or stages with alt_next: decomposing
        valid_stages = {"decomposing", "seed", "itemizing", "itemized", "investigating", "findings_ready"}
        if parent_stage not in valid_stages:
            return {"error": f"Parent is in stage '{parent_stage}' — cannot decompose. Valid stages: {', '.join(sorted(valid_stages))}"}

        # Validate agent exists
        cursor.execute("SELECT name FROM agents WHERE name = ?", (agent_name,))
        if not cursor.fetchone():
            return {"error": f"Agent '{agent_name}' not registered."}
    finally:
        conn.close()

    children_spec = spec["children"]
    created_children: list[dict[str, Any]] = []
    task_ids: list[int] = []

    # Phase 1: Create all children (folders, READMEs, register, create tasks)
    for i, child in enumerate(children_spec):
        num = f"{i + 1:03d}"
        slug = child["slug"]
        title = child["title"]
        description = child.get("description", title)
        task_type = child.get("task_type", "feature")

        child_rel_path = f"{parent_path}/{num}-{slug}"
        child_abs_path = req_root / child_rel_path

        # 1. Create folder
        child_abs_path.mkdir(parents=True, exist_ok=True)

        # 2. Write README.md
        readme_path = child_abs_path / "README.md"
        readme_content = f"# {title}\n\n{description.strip()}\n"
        readme_path.write_text(readme_content)

        # 3. Register child requirement
        reg_result = register(child_rel_path, created_by=agent_name)
        if "error" in reg_result:
            return {"error": f"Failed to register child '{child_rel_path}': {reg_result['error']}"}

        # 4. Create task
        task_result = create_task(
            agent_name=agent_name,
            title=title,
            task_file=str(readme_path),
            task_type=task_type,
        )
        if "error" in task_result:
            return {"error": f"Failed to create task for '{child_rel_path}': {task_result['error']}"}

        task_id = int(task_result["task_id"])
        task_ids.append(task_id)

        # 5. Link task to child requirement
        link_result = link_task(task_id, child_rel_path)
        if "error" in link_result:
            return {"error": f"Failed to link task #{task_id} to '{child_rel_path}': {link_result['error']}"}

        created_children.append({
            "path": child_rel_path,
            "task_id": task_id,
            "title": title,
        })

    # Phase 2: Resolve blocked_by references between siblings
    for i, child in enumerate(children_spec):
        blocked_by_refs = child.get("blocked_by", [])
        if not blocked_by_refs:
            continue

        blocker_str_parts = []
        for ref in blocked_by_refs:
            # 1-based index into children
            idx = int(ref) - 1
            if idx < 0 or idx >= len(task_ids):
                return {"error": f"Child {i + 1} has invalid blocked_by reference: {ref} (valid range: 1-{len(task_ids)})"}
            blocker_str_parts.append(str(task_ids[idx]))

        if blocker_str_parts:
            blocker_str = ",".join(blocker_str_parts)
            conn = get_db()
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "UPDATE tasks SET blocked_by = ? WHERE id = ?",
                    (blocker_str, task_ids[i]),
                )
                conn.commit()
            finally:
                conn.close()

    # Phase 3: Advance parent to 'tasked' (auto-advance handles further gates)
    stage_result = update_stage(parent_path, "tasked")

    return {
        "status": "decomposed",
        "parent_path": parent_path,
        "children_created": len(created_children),
        "tasks_created": len(task_ids),
        "children": created_children,
        "parent_stage": stage_result.get("to_stage", stage_result.get("error", "unknown")),
    }
