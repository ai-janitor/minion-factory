"""Promote a backlog item into the requirement pipeline.
Copies the backlog README.md into .work/requirements/{target}/, registers the
requirement in the DB, and updates the backlog row to status=promoted.
Includes DAG crew requirements and available characters on success.

Purpose: Promote a backlog item into the requirement pipeline.
Rationale: Extracted into own module for single-responsibility backlog management.
Responsibility: Promote a backlog item into the requirement pipeline. NOT responsible for unrelated concerns.
Organization: Standalone functions and/or a single class. See source."""

from __future__ import annotations

import os
import shutil

import yaml
from typing import Any

from minion.db import _get_db_path, get_db, now_iso
from minion.requirements.crud import register

from .path_resolution_and_slug import _get_backlog_path

# Backlog types that map to the 'bug' requirement origin; everything else → 'feature'
_BUG_TYPES = {"bug"}


def _scan_crew_characters(needed_classes: set[str]) -> list[dict[str, str]]:
    """Scan all crew YAMLs for characters matching needed classes.

    Returns list of {name, class, crew, snippet} dicts.
    Snippet is the first sentence of the character's system prompt.
    """
    import glob

    import yaml

    from minion.crew.spawn import _all_search_paths, _role_to_class

    characters: list[dict[str, str]] = []
    seen_names: set[str] = set()

    for search_dir in _all_search_paths():
        for yaml_path in glob.glob(os.path.join(search_dir, "*.yaml")):
            try:
                with open(yaml_path) as f:
                    crew = yaml.safe_load(f)
                if not crew or "agents" not in crew:
                    continue
                crew_name = os.path.splitext(os.path.basename(yaml_path))[0]
                for agent_name, cfg in crew.get("agents", {}).items():
                    if agent_name in seen_names:
                        continue
                    role = cfg.get("role", "coder")
                    agent_class = _role_to_class(role)
                    if agent_class not in needed_classes:
                        continue
                    # Extract first sentence of system prompt as snippet
                    system = cfg.get("system", "")
                    snippet = ""
                    for line in system.strip().splitlines():
                        line = line.strip()
                        if line and not line.startswith("ON STARTUP") and not line.startswith("You are"):
                            snippet = line[:80]
                            break
                    seen_names.add(agent_name)
                    characters.append({
                        "name": agent_name,
                        "class": agent_class,
                        "crew": crew_name,
                        "snippet": snippet,
                    })
            except (yaml.YAMLError, OSError, KeyError):
                continue
    return characters


def _promote_single(
    file_path: str,
    origin: str,
    slug: str,
    flow: str,
    agent_name: str,
    agent_class: str,
    backlog_id: int,
    backlog_type: str,
    backlog_title: str,
    backlog_readme: str,
    req_root: str,
    cursor: Any,
    prev_status: str,
) -> dict[str, Any]:
    """Create a single requirement from a backlog item. Internal helper.

    Purpose: Encapsulate the per-requirement creation logic so it can be called
    once (count=1) or N times (count>1) without duplicating code.
    Returns the per-requirement result dict.
    """
    req_folder_name = f"{origin}s"  # bugs/ or features/
    req_rel_path = f"{req_folder_name}/{slug}"
    req_abs_path = os.path.join(req_root, req_folder_name, slug)

    # --- Guard: requirement folder must not already exist ---
    if os.path.exists(req_abs_path):
        raise ValueError(
            f"Requirement folder already exists at '{req_abs_path}'. Cannot overwrite."
        )

    # --- Create the requirement folder and copy README ---
    os.makedirs(req_abs_path, exist_ok=False)
    if os.path.exists(backlog_readme):
        shutil.copy2(backlog_readme, os.path.join(req_abs_path, "README.md"))

    # --- Register requirement in DB ---
    reg_result = register(file_path=req_rel_path, created_by="backlog-promote", flow_type=flow)
    if "error" in reg_result:
        # Rollback: remove the folder we just created
        shutil.rmtree(req_abs_path, ignore_errors=True)
        raise RuntimeError(f"Failed to register requirement: {reg_result['error']}")

    # --- SU-07: Ensure requirement_id propagates for lineage tracking ---
    requirement_id = reg_result.get("id") or reg_result.get("requirement_id")
    if requirement_id is None:
        fallback_conn = get_db()
        try:
            fallback_row = fallback_conn.execute(
                "SELECT id FROM requirements WHERE file_path = ? ORDER BY id DESC LIMIT 1",
                (req_rel_path,),
            ).fetchone()
            if fallback_row:
                requirement_id = fallback_row["id"]
        finally:
            fallback_conn.close()

    return {
        "requirement_id": requirement_id,
        "file_path": req_rel_path,
        "abs_path": req_abs_path,
        "registration": reg_result,
    }


def promote(
    file_path: str,
    origin: str | None = None,
    db: str | None = None,
    slug: str | None = None,
    flow: str = "requirement",
    agent_name: str | None = None,
    count: int = 1,
    slugs: list[str] | None = None,
) -> dict[str, Any]:
    """Promote an open backlog item to one or more requirements.

    file_path is relative to .work/backlog/ (e.g. 'bugs/preview-final-word-loss').
    flow selects the requirement lifecycle DAG — 'requirement' (default, 9 stages)
    or 'requirement-lite' (4 stages: seed -> decomposing -> tasked -> completed).
    agent_name is required — only lead class agents can promote.

    When count=1 (default): creates exactly 1 requirement (existing behavior).
    When count>1: creates N requirements, one per slug in the slugs list.
    The promoted_to field stores a comma-separated list of requirement paths.
    Items already promoted can be re-promoted with count>1 to add more requirements.

    Steps:
    1. Auth gate: verify agent exists and is lead class.
    2. Verify backlog item exists and status is open (or promoted when count>1).
    3. Infer origin (bug|feature) from backlog type if not provided.
    4. For each slug: create requirement folder, copy README, register in DB.
    5. Update backlog row: status=promoted, promoted_to=comma-separated paths.
    6. Append to the backlog README.md Outcome section.
    7. Inject class duties reminder from _agent-classes.yaml.
    8. Return summary dict with all created requirements.
    """
    # --- Auth gate: only lead class can promote ---
    if not agent_name:
        raise ValueError("--agent is required for backlog promote.")

    file_path = file_path.strip("/")

    # --- Resolve paths ---
    db_path = db or _get_db_path()
    work_dir = os.path.dirname(db_path)
    backlog_root = _get_backlog_path(db)
    req_root = os.path.join(work_dir, "requirements")

    backlog_item_dir = os.path.join(backlog_root, file_path)
    backlog_readme = os.path.join(backlog_item_dir, "README.md")

    # --- Verify agent is lead class ---
    conn = get_db()
    try:
        agent_row = conn.execute(
            "SELECT agent_class FROM agents WHERE name = ?", (agent_name,)
        ).fetchone()
        if not agent_row:
            raise ValueError(f"Agent '{agent_name}' not registered.")
        agent_class = agent_row["agent_class"]
        if agent_class != "lead":
            raise ValueError(
                f"BLOCKED: Agent '{agent_name}' (class '{agent_class}') cannot promote. "
                f"Only lead class can promote backlog items."
            )
    finally:
        conn.close()

    # --- Verify backlog item exists and check status ---
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT id, type, title, status, promoted_to FROM backlog WHERE file_path = ?",
            (file_path,),
        )
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Backlog item '{file_path}' not found.")

        status = row["status"]
        existing_promoted_to = row["promoted_to"] or ""

        # Status gate: allow re-promotion (status=promoted) when count>1
        if status == "promoted" and count <= 1:
            raise ValueError(
                f"Backlog item '{file_path}' is already promoted to '{row['promoted_to']}'. "
                f"Use --count N --slugs to add more requirements."
            )
        if status in ("killed", "deferred"):
            raise ValueError(
                f"Backlog item '{file_path}' has status '{status}' and cannot be promoted."
            )
        if status not in ("open", "promoted"):
            raise ValueError(
                f"Backlog item '{file_path}' has unexpected status '{status}'. Expected 'open'."
            )

        backlog_type = row["type"] or ""
        backlog_id = row["id"]

        # --- Infer origin ---
        if origin is None:
            origin = "bug" if backlog_type in _BUG_TYPES else "feature"

        # --- Build the list of slugs to create ---
        if count == 1:
            # Single promote: existing behavior
            effective_slugs = [slug or file_path.split("/")[-1]]
        else:
            # Multi promote: slugs list is mandatory (validated by CLI)
            if not slugs or len(slugs) != count:
                raise ValueError(f"--slugs must provide exactly {count} slug names.")
            effective_slugs = slugs

        # --- Create each requirement ---
        created_requirements: list[dict[str, Any]] = []
        created_paths: list[str] = []
        for s in effective_slugs:
            req_info = _promote_single(
                file_path=file_path,
                origin=origin,
                slug=s,
                flow=flow,
                agent_name=agent_name,
                agent_class=agent_class,
                backlog_id=backlog_id,
                backlog_type=backlog_type,
                backlog_title=row["title"],
                backlog_readme=backlog_readme,
                req_root=req_root,
                cursor=cursor,
                prev_status=status,
            )
            created_requirements.append(req_info)
            created_paths.append(req_info["file_path"])

        # --- Update backlog row ---
        # Merge new paths with any existing promoted_to paths
        all_paths = []
        if existing_promoted_to:
            all_paths = [p.strip() for p in existing_promoted_to.split(",") if p.strip()]
        all_paths.extend(created_paths)
        promoted_to_value = ",".join(all_paths)

        now = now_iso()
        cursor.execute(
            "UPDATE backlog SET status = 'promoted', promoted_to = ?, promoted_by = ?, updated_at = ? WHERE id = ?",
            (promoted_to_value, agent_name, now, backlog_id),
        )

        # Log promotion to transition_log for lineage tracking
        from_status = status if status != "promoted" else "promoted"
        cursor.execute(
            "INSERT INTO transition_log (entity_id, entity_type, from_status, to_status, triggered_by, created_at) "
            "VALUES (?, 'backlog', ?, 'promoted', ?, ?)",
            (backlog_id, from_status, agent_name, now),
        )

        conn.commit()

        # --- Append to backlog README Outcome section ---
        date_str = now[:10]  # YYYY-MM-DD
        for cp in created_paths:
            outcome_line = f"Promoted to requirement: {cp} on {date_str}\n"
            if os.path.exists(backlog_readme):
                with open(backlog_readme, "a") as f:
                    f.write(f"\n{outcome_line}")

        # Build DAG stage guide for the assigned flow
        dag_guide = ""
        try:
            from minion.tasks.loader import load_flow
            flow_obj = load_flow(flow)
            stages = [s.name for s in flow_obj.stages]
            dag_guide = " -> ".join(stages)
        except (ImportError, FileNotFoundError, ValueError, AttributeError):
            dag_guide = f"(flow '{flow}' — run `minion flow show {flow}` for stages)"

        # Load class duties from _agent-classes.yaml
        duties_text = ""
        try:
            from minion.tasks.agent_classes import get_class_duties
            duties_text = get_class_duties(agent_class)
        except (ImportError, FileNotFoundError, KeyError):
            duties_text = ""

        # Extract required crew classes from DAG flow
        required_crew: list[dict[str, Any]] = []
        try:
            from minion.tasks.loader import load_flow as _load_flow
            flow_obj = _load_flow(flow)
            class_stages = flow_obj.all_required_classes()
            for cls, stages in sorted(class_stages.items()):
                required_crew.append({"class": cls, "stages": stages})
        except (ImportError, FileNotFoundError, ValueError):
            pass

        # Scan crew YAMLs for available characters matching required classes
        available_characters: list[dict[str, str]] = []
        try:
            needed_classes = {r["class"] for r in required_crew}
            if needed_classes:
                available_characters = _scan_crew_characters(needed_classes)
        except (ImportError, OSError):
            pass

        # --- Build result ---
        if count == 1:
            # Single promote: backward-compatible result shape
            req_info = created_requirements[0]
            result: dict[str, Any] = {
                "status": "promoted",
                "requirement_id": req_info["requirement_id"],
                "backlog": {
                    "id": backlog_id,
                    "file_path": file_path,
                    "type": backlog_type,
                    "title": row["title"],
                    "promoted_to": promoted_to_value,
                },
                "requirement": req_info["registration"],
                "next_steps": (
                    f"Follow the DAG: {dag_guide}. "
                    f"Check status: minion req status --path {req_info['file_path']}. "
                    f"Advance stage: minion req update --path {req_info['file_path']} --stage <next>. "
                    f"Decompose: minion req decompose --path {req_info['file_path']} --by <agent> --inline '<yaml>'"
                ),
            }
        else:
            # Multi promote: return list of created requirements
            result = {
                "status": "promoted",
                "count": count,
                "backlog": {
                    "id": backlog_id,
                    "file_path": file_path,
                    "type": backlog_type,
                    "title": row["title"],
                    "promoted_to": promoted_to_value,
                },
                "requirements": [
                    {
                        "requirement_id": r["requirement_id"],
                        "file_path": r["file_path"],
                        "registration": r["registration"],
                    }
                    for r in created_requirements
                ],
                "next_steps": (
                    f"Follow the DAG: {dag_guide}. "
                    f"Created {count} requirements: {', '.join(created_paths)}."
                ),
            }
        if duties_text:
            result["duties_reminder"] = duties_text
        if required_crew:
            result["required_crew"] = required_crew
        if available_characters:
            result["available_characters"] = available_characters
        return result
    finally:
        conn.close()
