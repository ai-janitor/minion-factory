"""Write findings.md for a requirement from structured input.

Accepts root_cause, evidence list, and recommendation — writes the
markdown file and advances the requirement stage to findings_ready.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from minion.db import get_db, _get_db_path
from minion.requirements.crud import update_stage


def _resolve_work_dir() -> Path:
    """Derive .work/ directory from the DB path."""
    return Path(_get_db_path()).parent


def findings(file_path: str, spec: dict, created_by: str = "lead") -> dict[str, Any]:
    """Write findings.md and advance requirement to findings_ready.

    Args:
        file_path: Requirement's file_path (relative to .work/requirements/).
        spec: Dict with 'root_cause', 'evidence' (list), 'recommendation'.
        created_by: Agent performing the action (must be registered).

    Returns:
        Summary dict with status, path, and stage info.
    """
    file_path = file_path.rstrip("/")
    work_dir = _resolve_work_dir()
    req_root = work_dir / "requirements"

    # Validate spec has required keys
    for key in ("root_cause", "evidence", "recommendation"):
        if key not in spec:
            return {"error": f"Spec missing required key: '{key}'"}

    if not isinstance(spec["evidence"], list) or len(spec["evidence"]) == 0:
        return {"error": "Spec 'evidence' must be a non-empty list."}

    # Validate requirement exists in DB
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, stage FROM requirements WHERE file_path = ?", (file_path,))
        row = cursor.fetchone()
        if not row:
            return {"error": f"Requirement '{file_path}' not found. Register it first."}

        # Validate agent exists
        cursor.execute("SELECT name FROM agents WHERE name = ?", (created_by,))
        if not cursor.fetchone():
            return {"error": f"Agent '{created_by}' not registered."}
    finally:
        conn.close()

    # Build findings.md content
    evidence_lines = "\n".join(f"- {item}" for item in spec["evidence"])
    content = (
        f"## Root Cause\n\n{spec['root_cause']}\n\n"
        f"## Evidence\n\n{evidence_lines}\n\n"
        f"## Recommendation\n\n{spec['recommendation']}\n"
    )

    # Write findings.md
    req_dir = req_root / file_path
    if not req_dir.is_dir():
        return {"error": f"Requirement directory does not exist: {req_dir}"}

    findings_path = req_dir / "findings.md"
    findings_path.write_text(content)

    # Advance stage to findings_ready
    stage_result = update_stage(file_path, "findings_ready")

    return {
        "status": "findings_written",
        "path": file_path,
        "findings_file": str(findings_path),
        "stage": stage_result.get("to_stage", stage_result.get("error", "unknown")),
    }
