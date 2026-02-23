"""Write itemized-requirements.md from a structured spec file.

Accepts a YAML spec with numbered items and writes them as a numbered
list to the requirement's folder, then advances stage to 'itemized'.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from minion.db import get_db, _get_db_path
from minion.requirements.crud import update_stage


def _load_spec(spec_path: str) -> dict:
    """Load and validate an itemization spec file (YAML)."""
    with open(spec_path) as f:
        spec = yaml.safe_load(f)

    if not isinstance(spec, dict) or "items" not in spec:
        raise ValueError("Spec file must contain an 'items' key with a list of requirement items.")

    items = spec["items"]
    if not isinstance(items, list) or len(items) == 0:
        raise ValueError("Spec 'items' must be a non-empty list.")

    for i, item in enumerate(items):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"Item {i + 1} must be a non-empty string.")

    return spec


def _resolve_work_dir() -> Path:
    """Derive .work/ directory from the DB path."""
    return Path(_get_db_path()).parent


def itemize(file_path: str, spec: dict, created_by: str = "lead") -> dict[str, Any]:
    """Write itemized-requirements.md from spec and advance stage.

    Args:
        file_path: Requirement's file_path (relative to .work/requirements/).
        spec: Parsed spec dict with 'items' list.
        created_by: Agent performing the itemization.

    Returns:
        Summary dict with status, items written, and new stage.
    """
    file_path = file_path.rstrip("/")
    work_dir = _resolve_work_dir()
    req_root = work_dir / "requirements"

    # Validate requirement exists in DB
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, stage FROM requirements WHERE file_path = ?", (file_path,))
        row = cursor.fetchone()
        if not row:
            return {"error": f"Requirement '{file_path}' not found. Register it first."}

        req_stage = row["stage"]
        valid_stages = {"seed", "itemizing"}
        if req_stage not in valid_stages:
            return {"error": f"Requirement is in stage '{req_stage}' — cannot itemize. Valid stages: {', '.join(sorted(valid_stages))}"}

        # Validate agent exists
        cursor.execute("SELECT name FROM agents WHERE name = ?", (created_by,))
        if not cursor.fetchone():
            return {"error": f"Agent '{created_by}' not registered."}
    finally:
        conn.close()

    # Build numbered list content
    items = spec["items"]
    lines = [f"{i + 1}. {item.strip()}" for i, item in enumerate(items)]
    content = "# Itemized Requirements\n\n" + "\n".join(lines) + "\n"

    # Write to requirement folder
    req_dir = req_root / file_path
    if not req_dir.is_dir():
        return {"error": f"Requirement folder '{req_dir}' does not exist on disk."}

    output_path = req_dir / "itemized-requirements.md"
    output_path.write_text(content)

    # Advance stage to 'itemized'
    stage_result = update_stage(file_path, "itemized")

    return {
        "status": "itemized",
        "file_path": file_path,
        "items_written": len(items),
        "output_file": str(output_path),
        "new_stage": stage_result.get("to_stage", stage_result.get("error", "unknown")),
    }
