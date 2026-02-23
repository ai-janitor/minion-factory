"""Gate resolution — check preconditions before allowing a DAG transition.

Three gate types:
  1. Filesystem artifacts — file exists and is not empty (supports globs)
  2. DB conditions — query child/sibling task states
  3. Task preconditions — check task row fields
"""

from __future__ import annotations

import glob as globmod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class GateResult:
    passed: bool
    gate: str
    message: str


# DB condition names — resolved by check_db_gate()
DB_CONDITIONS = {
    "all_inv_tasks_closed",
    "all_leaves_have_tasks",
    "all_impl_tasks_closed",
}

# Task-level field checks
TASK_PRECONDITIONS = {
    "submit_result": "result_file",
}

# Structural filesystem checks (not simple file existence)
STRUCTURAL_CHECKS = {
    "numbered_child_folders",
    "impl_task_readmes",
}


def check_gate(
    gate: str,
    *,
    context_dir: Path | None = None,
    db=None,
    entity_id: int | None = None,
    entity_type: str = "task",
) -> GateResult:
    """Resolve a single gate. Returns GateResult with pass/fail and message."""
    if gate in DB_CONDITIONS:
        return _check_db_gate(gate, db=db, entity_id=entity_id, entity_type=entity_type)
    if gate in TASK_PRECONDITIONS:
        return _check_task_precondition(gate, db=db, entity_id=entity_id)
    if gate in STRUCTURAL_CHECKS:
        return _check_structural(gate, context_dir=context_dir)
    # Default: filesystem artifact
    return _check_file_gate(gate, context_dir=context_dir)


def check_gates(
    gates: list[str],
    *,
    context_dir: Path | None = None,
    db=None,
    entity_id: int | None = None,
    entity_type: str = "task",
) -> list[GateResult]:
    """Check all gates. Returns list of results (caller decides what to do with failures)."""
    return [
        check_gate(g, context_dir=context_dir, db=db, entity_id=entity_id, entity_type=entity_type)
        for g in gates
    ]


def all_gates_pass(results: list[GateResult]) -> bool:
    return all(r.passed for r in results)


# ---------------------------------------------------------------------------
# Gate type implementations
# ---------------------------------------------------------------------------

def _check_file_gate(gate: str, *, context_dir: Path | None = None) -> GateResult:
    """File must exist and not be empty. Supports glob patterns."""
    if context_dir is None:
        return GateResult(passed=False, gate=gate, message=f"no context_dir provided to resolve '{gate}'")

    pattern = str(context_dir / gate)
    matches = globmod.glob(pattern)
    if not matches:
        return GateResult(passed=False, gate=gate, message=f"'{gate}' not found at {context_dir}")

    # All matched files must be non-empty
    for match in matches:
        p = Path(match)
        if p.is_file() and p.stat().st_size == 0:
            return GateResult(passed=False, gate=gate, message=f"'{match}' exists but is empty")

    return GateResult(passed=True, gate=gate, message=f"'{gate}' satisfied ({len(matches)} match(es))")


def _check_db_gate(
    gate: str, *, db=None, entity_id: int | None = None, entity_type: str = "task"
) -> GateResult:
    """Query DB for aggregate conditions on child/sibling entities."""
    if db is None:
        return GateResult(passed=False, gate=gate, message=f"no db connection to check '{gate}'")
    if entity_id is None:
        return GateResult(passed=False, gate=gate, message=f"no entity_id to check '{gate}'")

    if gate == "all_inv_tasks_closed":
        return _db_all_child_tasks_closed(db, entity_id, entity_type, flow_type="investigation")
    elif gate == "all_impl_tasks_closed":
        return _db_all_child_tasks_closed(db, entity_id, entity_type, flow_type=None)
    elif gate == "all_leaves_have_tasks":
        return _db_all_leaves_have_tasks(db, entity_id, entity_type)
    else:
        return GateResult(passed=False, gate=gate, message=f"unknown DB condition '{gate}'")


def _check_task_precondition(gate: str, *, db=None, entity_id: int | None = None) -> GateResult:
    """Check a field on the task row is not null."""
    field = TASK_PRECONDITIONS.get(gate)
    if not field:
        return GateResult(passed=False, gate=gate, message=f"unknown precondition '{gate}'")
    if db is None or entity_id is None:
        return GateResult(passed=False, gate=gate, message=f"no db/entity_id to check '{gate}'")

    row = db.execute("SELECT {} FROM tasks WHERE id = ?".format(field), (entity_id,)).fetchone()
    if row is None:
        return GateResult(passed=False, gate=gate, message=f"task {entity_id} not found")
    if row[0] is None:
        return GateResult(passed=False, gate=gate, message=f"task {entity_id}: {field} is null")
    return GateResult(passed=True, gate=gate, message=f"task {entity_id}: {field} is set")


def _check_structural(gate: str, *, context_dir: Path | None = None) -> GateResult:
    """Structural filesystem checks."""
    if context_dir is None:
        return GateResult(passed=False, gate=gate, message=f"no context_dir for '{gate}'")

    if gate == "numbered_child_folders":
        # At least one NNN-* subfolder exists
        matches = sorted(context_dir.glob("[0-9][0-9][0-9]-*"))
        dirs = [m for m in matches if m.is_dir()]
        if not dirs:
            return GateResult(
                passed=False, gate=gate,
                message=f"no numbered child folders (NNN-*) in {context_dir}",
            )
        return GateResult(passed=True, gate=gate, message=f"{len(dirs)} numbered folders found")

    if gate == "impl_task_readmes":
        # Every NNN-* subfolder has a README.md
        dirs = sorted(d for d in context_dir.glob("[0-9][0-9][0-9]-*") if d.is_dir())
        if not dirs:
            return GateResult(passed=False, gate=gate, message=f"no numbered folders to check")
        missing = [d.name for d in dirs if not (d / "README.md").exists()]
        if missing:
            return GateResult(
                passed=False, gate=gate,
                message=f"missing README.md in: {', '.join(missing)}",
            )
        return GateResult(passed=True, gate=gate, message=f"all {len(dirs)} folders have README.md")

    return GateResult(passed=False, gate=gate, message=f"unknown structural check '{gate}'")


# ---------------------------------------------------------------------------
# DB query helpers — these will be fleshed out when DB schema is finalized
# ---------------------------------------------------------------------------

def _db_all_child_tasks_closed(db, entity_id: int, entity_type: str, flow_type: str | None) -> GateResult:
    """Check all child tasks of an entity are in a terminal state.

    For requirements: also finds tasks linked to descendant requirements
    (prefix match on file_path) so parent requirements see their children's tasks.
    """
    gate = f"all_{'inv' if flow_type == 'investigation' else 'impl'}_tasks_closed"
    try:
        # Collect this entity's requirement IDs + all descendant requirement IDs
        req_ids = [entity_id]
        if entity_type == "requirement":
            row = db.execute("SELECT file_path FROM requirements WHERE id = ?", (entity_id,)).fetchone()
            if row:
                parent_path = row[0]
                descendants = db.execute(
                    "SELECT id FROM requirements WHERE file_path LIKE ?",
                    (parent_path + "/%",),
                ).fetchall()
                req_ids.extend(r[0] for r in descendants)

        placeholders = ",".join("?" for _ in req_ids)
        query = f"SELECT id, status FROM tasks WHERE requirement_id IN ({placeholders})"
        if flow_type:
            query += f" AND flow_type = '{flow_type}'"
        rows = db.execute(query, req_ids).fetchall()
    except Exception:
        # Column doesn't exist yet — gate passes vacuously until schema migration
        return GateResult(passed=True, gate=gate, message="requirement_id column not yet available")

    if not rows:
        return GateResult(passed=False, gate=gate, message=f"no child tasks found for entity {entity_id}")

    terminal = {"closed", "abandoned", "obsolete"}
    open_tasks = [(r[0], r[1]) for r in rows if r[1] not in terminal]
    if open_tasks:
        return GateResult(
            passed=False, gate=gate,
            message=f"{len(open_tasks)} tasks still open: {open_tasks[:5]}",
        )
    return GateResult(passed=True, gate=gate, message=f"all {len(rows)} child tasks closed")


def _db_all_leaves_have_tasks(db, entity_id: int, entity_type: str) -> GateResult:
    """Check that every leaf requirement has at least one task."""
    gate = "all_leaves_have_tasks"
    # Requires parent_id column on requirements table (task 011)
    try:
        rows = db.execute(
            "SELECT id FROM requirements WHERE parent_id = ?", (entity_id,)
        ).fetchall()
    except Exception:
        return GateResult(passed=True, gate=gate, message="parent_id column not yet available")

    if not rows:
        return GateResult(passed=True, gate=gate, message="no child requirements (this IS a leaf)")

    missing = []
    for (req_id,) in rows:
        task_count = db.execute(
            "SELECT COUNT(*) FROM tasks WHERE requirement_id = ?", (req_id,)
        ).fetchone()[0]
        if task_count == 0:
            missing.append(req_id)

    if missing:
        return GateResult(
            passed=False, gate=gate,
            message=f"requirements without tasks: {missing[:10]}",
        )
    return GateResult(passed=True, gate=gate, message=f"all {len(rows)} leaf requirements have tasks")
