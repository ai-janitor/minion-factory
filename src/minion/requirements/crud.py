"""Requirements CRUD — register, reindex, stage transitions, linking, queries.

Paths stored in the DB are relative to .work/requirements/ so they survive
project directory moves. The filesystem is the source of truth; the DB is a
rebuildable runtime index.
"""

from __future__ import annotations

import os
from typing import Any

from minion.db import get_db, now_iso
from minion.tasks.engine import apply_transition
from minion.tasks.loader import load_flow


def _infer_origin(file_path: str) -> str:
    """Infer origin from the top-level directory of the path.

    features/genesis/001-auth/ → 'feature'
    bugs/preview-word-loss/    → 'bug'
    anything-else/             → first path segment as-is
    """
    top = file_path.split("/")[0].rstrip("/")
    _map = {"features": "feature", "bugs": "bug"}
    return _map.get(top, top)


def _infer_stage_from_fs(abs_path: str) -> str:
    """Estimate stage from filesystem state — used during reindex.

    This is a best-effort heuristic; the DB's recorded stage wins for live rows.
    Logic (in priority order):
      - Has subdirectories  → at least decomposed
      - Has itemized-requirements.md but no subdirs → decomposing
      - Otherwise → seed
    Tasked/reviewing/approved/tasking cannot be inferred from the filesystem alone;
    those stages require DB metadata.
    """
    if not os.path.isdir(abs_path):
        return "seed"

    children = [
        e for e in os.listdir(abs_path)
        if os.path.isdir(os.path.join(abs_path, e))
    ]
    if children:
        return "decomposed"

    if os.path.exists(os.path.join(abs_path, "itemized-requirements.md")):
        return "decomposing"

    return "seed"


def create(file_path: str, title: str, description: str = "", created_by: str = "human") -> dict[str, Any]:
    """Create a requirement folder with README.md and register it in one step.

    file_path is relative to .work/requirements/. Creates the folder,
    writes README.md from title+description, then registers in the index.
    """
    from minion.db import _get_db_path
    work_dir = os.path.dirname(_get_db_path())
    req_root = os.path.join(work_dir, "requirements")
    abs_path = os.path.join(req_root, file_path)

    if os.path.exists(abs_path):
        return {"error": f"Folder already exists: {file_path}"}

    os.makedirs(abs_path, exist_ok=True)
    readme = os.path.join(abs_path, "README.md")
    lines = [f"# {title}\n"]
    if description:
        lines.append(f"\n{description.strip()}\n")
    with open(readme, "w") as f:
        f.writelines(lines)

    result = register(file_path, created_by)
    if "error" in result:
        return result
    result["title"] = title
    return result


def register(file_path: str, created_by: str = "human") -> dict[str, Any]:
    """Register a requirement folder path in the index.

    file_path is relative to .work/requirements/. The folder must contain
    a README.md to be valid.
    """
    file_path = file_path.rstrip("/")
    conn = get_db()
    cursor = conn.cursor()
    now = now_iso()
    try:
        # Check for duplicate
        cursor.execute("SELECT id, stage FROM requirements WHERE file_path = ?", (file_path,))
        existing = cursor.fetchone()
        if existing:
            return {"error": f"Requirement '{file_path}' already registered (id={existing['id']}, stage={existing['stage']})."}

        origin = _infer_origin(file_path)
        cursor.execute(
            """INSERT INTO requirements (file_path, origin, stage, created_by, created_at, updated_at)
               VALUES (?, ?, 'seed', ?, ?, ?)""",
            (file_path, origin, created_by, now, now),
        )
        req_id = cursor.lastrowid
        conn.commit()
        return {"status": "registered", "id": req_id, "file_path": file_path, "origin": origin, "stage": "seed"}
    finally:
        conn.close()


def reindex(work_dir: str) -> dict[str, Any]:
    """Rebuild the requirements index by scanning the filesystem.

    Scans <work_dir>/requirements/, registers every folder with a README.md.
    Existing rows are preserved (stage metadata not overwritten). New rows are
    added with stage inferred from filesystem state.

    work_dir is the .work/ directory for the project.
    """
    req_root = os.path.join(work_dir, "requirements")
    if not os.path.isdir(req_root):
        return {"error": f"Requirements directory not found: {req_root}"}

    conn = get_db()
    cursor = conn.cursor()
    now = now_iso()

    # Fetch existing paths for fast lookup
    cursor.execute("SELECT file_path FROM requirements")
    existing_paths = {row["file_path"] for row in cursor.fetchall()}

    added: list[str] = []
    skipped: list[str] = []

    for dirpath, dirnames, filenames in os.walk(req_root):
        if "README.md" not in filenames:
            continue

        # Compute path relative to .work/requirements/
        rel = os.path.relpath(dirpath, req_root).replace("\\", "/")
        if rel == ".":
            # Skip the root requirements/ folder itself — not a requirement
            continue

        if rel in existing_paths:
            skipped.append(rel)
            continue

        origin = _infer_origin(rel)
        stage = _infer_stage_from_fs(dirpath)

        cursor.execute(
            """INSERT INTO requirements (file_path, origin, stage, created_by, created_at, updated_at)
               VALUES (?, ?, ?, 'reindex', ?, ?)""",
            (rel, origin, stage, now, now),
        )
        added.append(rel)

    conn.commit()
    conn.close()
    return {"status": "reindexed", "added": len(added), "skipped": len(skipped), "paths_added": added}


def update_stage(file_path: str, to_stage: str, skip: bool = False, agent: str = "") -> dict[str, Any]:
    """Advance a requirement to a new stage with transition validation.

    When skip=True and agent is lead-class, automatically walks all intermediate
    stages to reach to_stage. Each step passes through gate checks; the walk
    halts at the first gate failure or invalid transition.

    tasked requires at least one task linked to this path before it can be set.
    rejected always returns to decomposing.
    """
    file_path = file_path.rstrip("/")

    # Validate stage exists in requirement flow
    try:
        flow = load_flow("requirement")
    except FileNotFoundError:
        return {"error": "requirement.yaml flow not found"}
    if to_stage not in flow.stages:
        return {"error": f"Unknown stage '{to_stage}'. Valid: {', '.join(sorted(flow.stages.keys()))}"}

    conn = get_db()
    cursor = conn.cursor()
    now = now_iso()
    try:
        cursor.execute("SELECT id, stage FROM requirements WHERE file_path = ?", (file_path,))
        row = cursor.fetchone()
        if not row:
            return {"error": f"Requirement '{file_path}' not found. Register it first."}

        from_stage = row["stage"]
        req_id = row["id"]

        # Resolve context_dir: file_path is relative to .work/requirements/
        # Derive .work/ from DB path (respects -C flag)
        from pathlib import Path
        from minion.db import _get_db_path
        work_dir = Path(_get_db_path()).parent
        context_dir = work_dir / "requirements" / file_path

        from minion.tasks.engine import check_transition_gates
        from minion.tasks.gates import all_gates_pass

        # skip=True: lead agent walks through all intermediate stages to reach target.
        # Bypasses the single-hop restriction so leads don't manually step each stage.
        _LEAD_CLASSES = {"lead"}
        if skip and agent in _LEAD_CLASSES:
            walked: list[str] = []
            current = from_stage
            for _ in range(30):
                if current == to_stage:
                    break
                # Try direct hop to target first (already valid transition)
                direct = apply_transition(
                    "requirement", current, explicit_target=to_stage,
                    context_dir=context_dir, db=conn, entity_id=req_id, entity_type="requirement",
                )
                if direct.success:
                    walked.append(current)
                    current = to_stage
                    break
                # Otherwise advance one step along the happy path
                step = apply_transition(
                    "requirement", current,
                    context_dir=context_dir, db=conn, entity_id=req_id, entity_type="requirement",
                )
                if not step.success:
                    break
                assert step.to_status is not None
                walked.append(current)
                current = step.to_status
            else:
                pass  # loop exhausted

            final_stage = current
            cursor.execute(
                "UPDATE requirements SET stage = ?, updated_at = ? WHERE file_path = ?",
                (final_stage, now, file_path),
            )
            conn.commit()
            resp: dict[str, Any] = {
                "status": "updated",
                "file_path": file_path,
                "from_stage": from_stage,
                "to_stage": final_stage,
            }
            if walked:
                resp["skipped_through"] = walked
            if final_stage != to_stage:
                resp["warning"] = f"halted at '{final_stage}' — could not reach '{to_stage}' (gate failure or invalid path)"
            return resp

        # Normal path: single transition with full gate validation
        result = apply_transition(
            "requirement", from_stage, explicit_target=to_stage,
            context_dir=context_dir, db=conn, entity_id=req_id, entity_type="requirement",
        )
        if not result.success:
            return {"error": f"Transition blocked: {result.error}"}

        # Auto-advance: keep moving forward while gates pass and no workers needed.
        # Only auto-advance on forward transitions (not fail-backs).
        is_forward = False
        walk = from_stage
        for _ in range(20):
            s = flow.stages.get(walk)
            if s is None:
                break
            if s.next == to_stage or (s.alt_next and s.alt_next == to_stage):
                is_forward = True
                break
            walk = s.next  # type: ignore[assignment]
            if walk is None:
                break

        final_stage = to_stage
        skipped: list[str] = []
        seen: set[str] = {final_stage}
        while is_forward:
            stage_obj = flow.stages.get(final_stage)
            if stage_obj is None or stage_obj.terminal:
                break
            if stage_obj.workers is not None:
                break
            # Don't auto-advance past stages with gate requirements
            # (e.g. itemized, tasked) — they are real checkpoints
            if stage_obj.requires:
                break
            next_stage = stage_obj.next
            if next_stage is None or next_stage in seen:
                break
            seen.add(next_stage)
            gate_results = check_transition_gates(
                flow, next_stage,
                context_dir=context_dir, db=conn, entity_id=req_id, entity_type="requirement",
            )
            if gate_results and not all_gates_pass(gate_results):
                break
            skipped.append(final_stage)
            final_stage = next_stage

        cursor.execute(
            "UPDATE requirements SET stage = ?, updated_at = ? WHERE file_path = ?",
            (final_stage, now, file_path),
        )
        conn.commit()
        resp = {"status": "updated", "file_path": file_path, "from_stage": from_stage, "to_stage": final_stage}
        if skipped:
            resp["auto_advanced_through"] = skipped
        return resp
    finally:
        conn.close()


def link_task(task_id: int, file_path: str) -> dict[str, Any]:
    """Link a task to its source requirement path."""
    file_path = file_path.rstrip("/")
    conn = get_db()
    cursor = conn.cursor()
    now = now_iso()
    try:
        cursor.execute("SELECT id FROM requirements WHERE file_path = ?", (file_path,))
        req_row = cursor.fetchone()
        if not req_row:
            return {"error": f"Requirement '{file_path}' not registered."}
        req_id = req_row[0]

        cursor.execute("SELECT id, requirement_path FROM tasks WHERE id = ?", (task_id,))
        task_row = cursor.fetchone()
        if not task_row:
            return {"error": f"Task #{task_id} not found."}

        cursor.execute(
            "UPDATE tasks SET requirement_path = ?, requirement_id = ?, updated_at = ? WHERE id = ?",
            (file_path, req_id, now, task_id),
        )
        conn.commit()
        return {"status": "linked", "task_id": task_id, "requirement_path": file_path}
    finally:
        conn.close()


def list_requirements(stage: str = "", origin: str = "") -> dict[str, Any]:
    """List requirements with optional stage/origin filters."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        query = "SELECT * FROM requirements WHERE 1=1"
        params: list[str] = []
        if stage:
            query += " AND stage = ?"
            params.append(stage)
        if origin:
            query += " AND origin = ?"
            params.append(origin)
        query += " ORDER BY file_path ASC"
        cursor.execute(query, params)
        rows = [dict(r) for r in cursor.fetchall()]
        return {"requirements": rows}
    finally:
        conn.close()


def get_status(file_path: str) -> dict[str, Any]:
    """Return requirement detail plus linked tasks and completion percentage."""
    file_path = file_path.rstrip("/")
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM requirements WHERE file_path = ?", (file_path,))
        row = cursor.fetchone()
        if not row:
            return {"error": f"Requirement '{file_path}' not found."}

        req = dict(row)

        # All tasks linked directly to this path or any child path (prefix match)
        cursor.execute(
            "SELECT id, title, status, requirement_path FROM tasks WHERE requirement_path = ? OR requirement_path LIKE ?",
            (file_path, file_path + "/%"),
        )
        tasks = [dict(r) for r in cursor.fetchall()]

        closed_count = sum(1 for t in tasks if t["status"] == "closed")
        total = len(tasks)
        pct = int(closed_count / total * 100) if total > 0 else 0

        return {
            "requirement": req,
            "tasks": tasks,
            "task_count": total,
            "closed_count": closed_count,
            "completion_pct": pct,
        }
    finally:
        conn.close()


def get_tree(file_path: str) -> dict[str, Any]:
    """Return a tree of requirements rooted at file_path with their linked tasks."""
    file_path = file_path.rstrip("/")
    conn = get_db()
    cursor = conn.cursor()
    try:
        # Fetch root + all descendants (prefix match)
        cursor.execute(
            "SELECT * FROM requirements WHERE file_path = ? OR file_path LIKE ? ORDER BY file_path ASC",
            (file_path, file_path + "/%"),
        )
        reqs = [dict(r) for r in cursor.fetchall()]
        if not reqs:
            return {"error": f"No requirements found at or under '{file_path}'."}

        # For each requirement, fetch linked tasks
        for req in reqs:
            cursor.execute(
                "SELECT id, title, status FROM tasks WHERE requirement_path = ?",
                (req["file_path"],),
            )
            req["linked_tasks"] = [dict(r) for r in cursor.fetchall()]

        return {"root": file_path, "nodes": reqs}
    finally:
        conn.close()


def get_orphans() -> dict[str, Any]:
    """Return leaf requirements (no children) with no linked tasks.

    A leaf is a requirement whose path is not a prefix of any other registered
    requirement — meaning it has no children in the DB.
    """
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT file_path, stage FROM requirements ORDER BY file_path")
        all_paths = [dict(r) for r in cursor.fetchall()]
        path_set = {r["file_path"] for r in all_paths}

        orphans = []
        for req in all_paths:
            p = req["file_path"]
            # A leaf has no other requirement whose path starts with p + "/"
            is_leaf = not any(other.startswith(p + "/") for other in path_set if other != p)
            if not is_leaf:
                continue

            cursor.execute(
                "SELECT COUNT(*) FROM tasks WHERE requirement_path = ?", (p,)
            )
            if cursor.fetchone()[0] == 0:
                orphans.append(req)

        return {"orphans": orphans}
    finally:
        conn.close()


def get_unlinked_tasks() -> dict[str, Any]:
    """Return tasks that have no requirement_path set."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT id, title, status, created_by, created_at FROM tasks WHERE requirement_path IS NULL ORDER BY id"
        )
        tasks = [dict(r) for r in cursor.fetchall()]
        return {"unlinked_tasks": tasks}
    finally:
        conn.close()
