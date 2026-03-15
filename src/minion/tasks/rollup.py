"""Parent-child rollup — advance parent when all children reach terminal state.
When a child task closes:
  1. Query all siblings (same parent_id or requirement_id)
  2. Check if all siblings are terminal
  3. If yes, advance parent through the engine (gates, validation)
  4. Recursive — parent rollup may trigger grandparent rollup
  5. When a requirement reaches terminal, auto-close its originating backlog item
  6. When a requirement reaches terminal, auto-deregister the advancing agent

Purpose: Parent-child rollup — advance parent when all children reach terminal state.
Rationale: Extracted into own module for single-responsibility task management.
Responsibility: Parent-child rollup — advance parent when all children reach terminal state.
  Also closes backlog items and deregisters agents when their promoted requirement reaches terminal.
Organization: Standalone functions and/or a single class. See source."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .dag import TERMINAL_STATUSES  # single source of truth — defined in dag.py


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
    """Check if closing this child should advance its parent. Returns rollup chain.

    Time complexity: O(C * D) where C = number of sibling children per parent level,
    D = depth of parent chain (task -> requirement -> parent requirement -> grandparent...).
    Each level queries all siblings to check terminal status, then recurses up.
    Worst case with deeply nested requirements: O(C * D) DB queries.
    """
    # Precondition assertions — backlog #63
    assert db is not None, "db connection must not be None"
    assert isinstance(child_id, int) and child_id > 0, f"child_id must be a positive int, got {child_id}"
    assert child_type in ("task", "requirement"), f"child_type must be 'task' or 'requirement', got '{child_type}'"

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
    except (KeyError, sqlite3.OperationalError):
        return  # requirement_id or parent_id column not yet available

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

    # All terminal — determine rollup status
    # SU-05: If ALL children are stale, parent becomes stale (propagate abandonment).
    # If mix of stale + completed/closed, parent advances normally (some work was done).
    children_statuses = [s["status"] for s in siblings]
    all_stale = all(s == "stale" for s in children_statuses)

    if all_stale:
        # All work abandoned — propagate stale directly without engine transition
        from ..db import now_iso

        now = now_iso()
        req_row = db.execute(
            "SELECT id, stage FROM requirements WHERE id = ?", (req_id,)
        ).fetchone()
        if req_row is None:
            return
        db.execute(
            "UPDATE requirements SET stage = 'stale', updated_at = ? WHERE id = ?",
            (now, req_id),
        )
        db.commit()
        results.append(RollupResult(
            triggered=True, entity_type="requirement", entity_id=req_id,
            from_status=req_row["stage"], to_status="stale",
        ))
        # Auto-close backlog item when requirement reaches terminal (stale)
        _rollup_requirement_to_backlog(db, req_id, results=results)
        _rollup_requirement_to_parent(db, req_id, context_dir=context_dir, results=results)
        return

    # Normal rollup — advance requirement via engine
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

        # Auto-close backlog item when requirement reaches terminal
        if transition.to_status in TERMINAL_STATUSES:
            _rollup_requirement_to_backlog(db, req_id, results=results)

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
    except (KeyError, sqlite3.OperationalError):
        return  # SU-17: narrowed — parent_id column not yet available

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

    # SU-05: If ALL children are stale, parent becomes stale
    children_statuses = [s["stage"] for s in siblings]
    all_stale = all(s == "stale" for s in children_statuses)

    if all_stale:
        from ..db import now_iso

        now = now_iso()
        parent_row = db.execute(
            "SELECT id, stage FROM requirements WHERE id = ?", (parent_id,)
        ).fetchone()
        if parent_row is None:
            return
        db.execute(
            "UPDATE requirements SET stage = 'stale', updated_at = ? WHERE id = ?",
            (now, parent_id),
        )
        db.commit()
        results.append(RollupResult(
            triggered=True, entity_type="requirement", entity_id=parent_id,
            from_status=parent_row["stage"], to_status="stale",
        ))
        _rollup_requirement_to_parent(db, parent_id, context_dir=context_dir, results=results)
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

        # Auto-close backlog item when parent requirement reaches terminal
        if transition.to_status in TERMINAL_STATUSES:
            _rollup_requirement_to_backlog(db, parent_id, results=results)

        # Recursive: grandparent
        _rollup_requirement_to_parent(db, parent_id, context_dir=context_dir, results=results)
    else:
        results.append(RollupResult(
            triggered=False, entity_type="requirement", entity_id=parent_id,
            from_status=parent_row["stage"],
            error=transition.error,
        ))


# ---------------------------------------------------------------------------
# Backlog auto-close — close backlog items when their promoted requirement
# reaches a terminal stage (completed, stale, done, etc.)
# ---------------------------------------------------------------------------


def _rollup_requirement_to_backlog(
    db, req_id: int, *, results: list[RollupResult]
) -> None:
    """Auto-close a backlog item when its promoted requirement reaches terminal.

    Looks up the requirement's file_path, then finds backlog items whose
    promoted_to field contains that path. For multi-promote (comma-separated
    promoted_to), only closes the backlog item if ALL promoted requirements
    have reached terminal stages.

    Time complexity: O(B) where B = number of backlog items with promoted status
    that reference this requirement path.
    """
    try:
        req_row = db.execute(
            "SELECT file_path FROM requirements WHERE id = ?", (req_id,)
        ).fetchone()
    except (KeyError, sqlite3.OperationalError):
        return  # requirements table not available

    if req_row is None:
        return

    req_path = req_row["file_path"]

    # Find backlog items that were promoted to this requirement path.
    # promoted_to can be a single path or comma-separated list.
    # Use LIKE to match the requirement path within the promoted_to field.
    try:
        backlog_rows = db.execute(
            "SELECT id, file_path, status, promoted_to FROM backlog "
            "WHERE status = 'promoted' AND promoted_to LIKE ?",
            (f"%{req_path}%",),
        ).fetchall()
    except (KeyError, sqlite3.OperationalError):
        return  # backlog table not available

    if not backlog_rows:
        return

    from ..db import now_iso

    for bl_row in backlog_rows:
        promoted_to = bl_row["promoted_to"] or ""
        req_paths = [p.strip() for p in promoted_to.split(",") if p.strip()]

        # Verify the exact path is in the list (not just a substring match)
        if req_path not in req_paths:
            continue

        # For multi-promote: only close if ALL promoted requirements are terminal
        all_terminal = True
        for rp in req_paths:
            r = db.execute(
                "SELECT stage FROM requirements WHERE file_path = ?", (rp,)
            ).fetchone()
            if r is None:
                # Requirement not found — treat as terminal (may have been deleted)
                continue
            if r["stage"] not in TERMINAL_STATUSES:
                all_terminal = False
                break

        if not all_terminal:
            continue

        # All promoted requirements are terminal — close the backlog item
        now = now_iso()
        db.execute(
            "UPDATE backlog SET status = 'closed', updated_at = ? WHERE id = ?",
            (now, bl_row["id"]),
        )
        db.commit()

        results.append(RollupResult(
            triggered=True, entity_type="backlog", entity_id=bl_row["id"],
            from_status="promoted", to_status="closed",
        ))


# ---------------------------------------------------------------------------
# Agent auto-deregister — deregister the agent that advanced a requirement
# to a terminal stage (completed, stale, done, etc.)
# Prevents ghost agents from lingering in the registry after work is done.
# ---------------------------------------------------------------------------


def deregister_agent_on_completion(
    db, agent_name: str, *, results: list[RollupResult]
) -> None:
    """Auto-deregister an agent when a requirement reaches terminal stage.

    Called from update_stage() when the requirement transitions to a terminal
    stage. Only deregisters if the agent is currently registered.

    Uses a lightweight DB-only deregister (DELETE from agents table + release
    file claims) rather than the full comms.register.deregister() which also
    touches the coordinator DB, roster files, and inbox directories. The full
    cleanup is best-effort — the critical path is removing the agent from the
    local DB so it no longer appears in the registry.

    Time complexity: O(C) where C = file claims held by the agent.
    """
    if not agent_name:
        return

    try:
        row = db.execute(
            "SELECT name FROM agents WHERE name = ?", (agent_name,)
        ).fetchone()
    except Exception:
        return  # agents table not available or other DB issue

    if row is None:
        return  # agent not registered — nothing to do

    try:
        # Release file claims held by this agent
        db.execute("DELETE FROM file_claims WHERE agent_name = ?", (agent_name,))
        db.execute("DELETE FROM file_waitlist WHERE agent_name = ?", (agent_name,))
        # Remove the agent from the registry
        db.execute("DELETE FROM agents WHERE name = ?", (agent_name,))
        db.commit()

        results.append(RollupResult(
            triggered=True, entity_type="agent", entity_id=0,
            from_status="registered", to_status="deregistered",
            error=None,
        ))
    except Exception:
        # Best-effort — don't break the rollup chain if deregister fails
        results.append(RollupResult(
            triggered=False, entity_type="agent", entity_id=0,
            error=f"failed to deregister agent '{agent_name}'",
        ))
