"""Parent-child rollup — advance parent when all children reach terminal state.

When a child task closes:
  1. Query all siblings (same parent_id or requirement_id)
  2. Check if all siblings are terminal
  3. If yes, advance parent through the engine (gates, validation)
  4. Recursive — parent rollup may trigger grandparent rollup
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


TERMINAL_STATUSES = {"closed", "abandoned", "obsolete", "completed"}


@dataclass
class RollupResult:
    triggered: bool
    entity_type: str
    entity_id: int
    from_status: str | None = None
    to_status: str | None = None
    error: str | None = None


def check_and_rollup(
    db,
    child_id: int,
    child_type: str = "task",
    *,
    context_dir: Path | None = None,
) -> list[RollupResult]:
    """Check if closing this child should advance its parent. Returns rollup chain."""
    results: list[RollupResult] = []

    if child_type == "task":
        _rollup_task_to_requirement(db, child_id, context_dir=context_dir, results=results)
    elif child_type == "requirement":
        _rollup_requirement_to_parent(db, child_id, context_dir=context_dir, results=results)

    return results


def _rollup_task_to_requirement(
    db, task_id: int, *, context_dir: Path | None, results: list[RollupResult]
) -> None:
    """If all tasks under a requirement are terminal, advance the requirement."""
    try:
        row = db.execute(
            "SELECT requirement_id FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
    except Exception:
        return  # requirement_id column not yet available

    if row is None or row["requirement_id"] is None:
        return

    req_id = row["requirement_id"]

    # Check all sibling tasks
    siblings = db.execute(
        "SELECT id, status FROM tasks WHERE requirement_id = ?", (req_id,)
    ).fetchall()

    if not siblings:
        return

    all_terminal = all(s["status"] in TERMINAL_STATUSES for s in siblings)
    if not all_terminal:
        results.append(RollupResult(
            triggered=False, entity_type="requirement", entity_id=req_id,
            error=f"{sum(1 for s in siblings if s['status'] not in TERMINAL_STATUSES)} tasks still open",
        ))
        return

    # All terminal — advance requirement
    req_row = db.execute(
        "SELECT id, stage, flow_type FROM requirements WHERE id = ?", (req_id,)
    ).fetchone()
    if req_row is None:
        return

    current_stage = req_row["stage"]
    flow_type = req_row["flow_type"] or "requirement"

    # Use engine to determine and validate transition
    from .engine import apply_transition

    transition = apply_transition(
        flow_type, current_stage, passed=True,
        context_dir=context_dir, db=db, entity_id=req_id, entity_type="requirement",
    )

    if transition.success:
        # Apply the transition to the requirement
        from ..db import get_db, now_iso

        now = now_iso()
        db.execute(
            "UPDATE requirements SET stage = ?, updated_at = ? WHERE id = ?",
            (transition.to_status, now, req_id),
        )
        db.commit()

        results.append(RollupResult(
            triggered=True, entity_type="requirement", entity_id=req_id,
            from_status=current_stage, to_status=transition.to_status,
        ))

        # Recursive: check if this requirement's parent should also advance
        _rollup_requirement_to_parent(db, req_id, context_dir=context_dir, results=results)
    else:
        results.append(RollupResult(
            triggered=False, entity_type="requirement", entity_id=req_id,
            from_status=current_stage,
            error=transition.error,
        ))


def _rollup_requirement_to_parent(
    db, req_id: int, *, context_dir: Path | None, results: list[RollupResult]
) -> None:
    """If all child requirements under a parent are terminal, advance the parent."""
    try:
        row = db.execute(
            "SELECT parent_id FROM requirements WHERE id = ?", (req_id,)
        ).fetchone()
    except Exception:
        return  # parent_id column not yet available

    if row is None or row["parent_id"] is None:
        return

    parent_id = row["parent_id"]

    # Check all sibling requirements
    siblings = db.execute(
        "SELECT id, stage FROM requirements WHERE parent_id = ?", (parent_id,)
    ).fetchall()

    if not siblings:
        return

    all_terminal = all(s["stage"] in TERMINAL_STATUSES for s in siblings)
    if not all_terminal:
        return

    # All terminal — advance parent requirement
    parent_row = db.execute(
        "SELECT id, stage, flow_type FROM requirements WHERE id = ?", (parent_id,)
    ).fetchone()
    if parent_row is None:
        return

    from .engine import apply_transition

    transition = apply_transition(
        parent_row["flow_type"] or "requirement",
        parent_row["stage"],
        passed=True,
        context_dir=context_dir, db=db, entity_id=parent_id, entity_type="requirement",
    )

    if transition.success:
        from ..db import now_iso

        now = now_iso()
        db.execute(
            "UPDATE requirements SET stage = ?, updated_at = ? WHERE id = ?",
            (transition.to_status, now, parent_id),
        )
        db.commit()

        results.append(RollupResult(
            triggered=True, entity_type="requirement", entity_id=parent_id,
            from_status=parent_row["stage"], to_status=transition.to_status,
        ))

        # Recursive: grandparent
        _rollup_requirement_to_parent(db, parent_id, context_dir=context_dir, results=results)
    else:
        results.append(RollupResult(
            triggered=False, entity_type="requirement", entity_id=parent_id,
            from_status=parent_row["stage"],
            error=transition.error,
        ))
