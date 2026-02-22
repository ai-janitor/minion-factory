"""Context lifecycle — stub creation, content checking, path resolution.

Handles the three phases of context:
  1. Stage entry: create stub from template if file doesn't exist
  2. Pull-task: assemble context chain (task + parent + sibling)
  3. Stage exit: verify context file is not empty/stub-only
"""

from __future__ import annotations

import shutil
from pathlib import Path

from .loader import _find_flows_dir

# Marker line present in template stubs — if this is the only content, stub is unfilled
STUB_MARKER = "<!-- STUB: fill in below -->"


def resolve_context_path(
    context_template: str,
    *,
    task_id: int | None = None,
    req_path: str | Path | None = None,
    work_dir: str | Path | None = None,
) -> Path:
    """Resolve a context path template like '{req_path}/findings.md'."""
    result = context_template
    if task_id is not None:
        result = result.replace("{task_id}", str(task_id))
    if req_path is not None:
        result = result.replace("{req_path}", str(req_path))
    if work_dir is not None:
        result = result.replace("{work_dir}", str(work_dir))

    path = Path(result)
    if not path.is_absolute() and work_dir:
        path = Path(work_dir) / path
    return path


def create_stub(
    context_path: Path,
    *,
    template_name: str | None = None,
    flows_dir: Path | None = None,
) -> bool:
    """Create a stub file from template. Returns True if created, False if already exists.

    If file already exists (retry scenario), preserves existing content.
    """
    if context_path.exists():
        return False

    context_path.parent.mkdir(parents=True, exist_ok=True)

    if template_name:
        fdir = flows_dir or _find_flows_dir()
        template_path = fdir / template_name
        if template_path.exists():
            shutil.copy2(template_path, context_path)
            return True

    # No template — create minimal stub
    context_path.write_text(f"{STUB_MARKER}\n")
    return True


def is_stub_only(context_path: Path) -> bool:
    """Check if a context file is still just a stub (unfilled template)."""
    if not context_path.exists():
        return True
    content = context_path.read_text().strip()
    if not content:
        return True
    # Strip the marker and check if anything meaningful remains
    without_marker = content.replace(STUB_MARKER, "").strip()
    # Also strip common template placeholders
    for placeholder in ["TODO:", "[ ]", "<!-- "]:
        without_marker = without_marker.replace(placeholder, "")
    without_marker = without_marker.strip()
    if not without_marker:
        return True
    # If only blank lines and comments remain, it's still a stub
    lines = [l.strip() for l in without_marker.split("\n") if l.strip()]
    meaningful = [l for l in lines if not l.startswith("#") and not l.startswith("<!--")]
    return len(meaningful) == 0


def assemble_context_chain(
    *,
    db=None,
    task_id: int | None = None,
    requirement_id: int | None = None,
) -> dict[str, list[dict[str, str]]]:
    """Assemble three-dimensional context chain for pull-task.

    Returns:
        {
            "task_chain": [{stage, path}, ...],    # this task's history
            "parent_chain": [{stage, path}, ...],  # requirement history
            "sibling_context": [{task_id, stage, path}, ...]  # sibling task contexts
        }
    """
    result: dict[str, list[dict[str, str]]] = {
        "task_chain": [],
        "parent_chain": [],
        "sibling_context": [],
    }

    if db is None:
        return result

    # Task chain — this task's transition history
    if task_id is not None:
        try:
            rows = db.execute(
                "SELECT from_status, to_status, context_path FROM transition_log "
                "WHERE entity_id = ? AND entity_type = 'task' ORDER BY created_at",
                (task_id,),
            ).fetchall()
            result["task_chain"] = [
                {"stage": r["to_status"], "path": r["context_path"] or ""}
                for r in rows
            ]
        except Exception:
            pass  # transition_log not yet created (task 011)

    # Parent chain — requirement's transition history
    if requirement_id is not None:
        try:
            rows = db.execute(
                "SELECT from_status, to_status, context_path FROM transition_log "
                "WHERE entity_id = ? AND entity_type = 'requirement' ORDER BY created_at",
                (requirement_id,),
            ).fetchall()
            result["parent_chain"] = [
                {"stage": r["to_status"], "path": r["context_path"] or ""}
                for r in rows
            ]
        except Exception:
            pass

        # Sibling context — other tasks under same requirement
        try:
            rows = db.execute(
                "SELECT t.id, tl.to_status, tl.context_path FROM tasks t "
                "JOIN transition_log tl ON tl.entity_id = t.id AND tl.entity_type = 'task' "
                "WHERE t.requirement_id = ? AND t.id != ? "
                "ORDER BY t.id, tl.created_at",
                (requirement_id, task_id or -1),
            ).fetchall()
            result["sibling_context"] = [
                {"task_id": str(r["id"]), "stage": r["to_status"], "path": r["context_path"] or ""}
                for r in rows
            ]
        except Exception:
            pass

    return result
