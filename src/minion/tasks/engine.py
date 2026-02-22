"""Transition engine — single entry point for all DAG state transitions.

Every status change flows through `apply_transition()`:
  1. Load flow for entity's flow_type
  2. Validate target is in allowed transition set
  3. Check gates on target stage
  4. Check worker eligibility
  5. Apply transition (update DB row)
  6. Log to transition history
  7. Clear assignment if next stage needs different worker class
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .dag import TaskFlow
from .gates import GateResult, all_gates_pass, check_gates
from .loader import load_flow


@dataclass
class TransitionResult:
    success: bool
    from_status: str
    to_status: str | None
    eligible_classes: list[str] | None = None
    gate_failures: list[GateResult] | None = None
    error: str | None = None


def resolve_next(
    flow: TaskFlow,
    current_status: str,
    passed: bool = True,
    explicit_target: str | None = None,
) -> TransitionResult:
    """Determine the next status without applying it.

    Args:
        flow: The loaded TaskFlow DAG
        current_status: Current status of the entity
        passed: Whether the current phase passed or failed
        explicit_target: Override target (for alt_next or dead_end transitions)
    """
    if flow.is_terminal(current_status):
        return TransitionResult(
            success=False, from_status=current_status, to_status=None,
            error=f"'{current_status}' is a terminal stage — no transitions allowed",
        )

    valid = flow.valid_transitions(current_status)
    if not valid:
        return TransitionResult(
            success=False, from_status=current_status, to_status=None,
            error=f"no valid transitions from '{current_status}'",
        )

    if explicit_target:
        if explicit_target not in valid:
            return TransitionResult(
                success=False, from_status=current_status, to_status=explicit_target,
                error=f"'{explicit_target}' is not a valid transition from '{current_status}'. Valid: {sorted(valid)}",
            )
        to_status = explicit_target
    else:
        to_status = flow.next_status(current_status, passed)
        if to_status is None:
            return TransitionResult(
                success=False, from_status=current_status, to_status=None,
                error=f"no {'pass' if passed else 'fail'} transition from '{current_status}'",
            )

    return TransitionResult(success=True, from_status=current_status, to_status=to_status)


def check_transition_gates(
    flow: TaskFlow,
    to_status: str,
    *,
    context_dir: Path | None = None,
    db=None,
    entity_id: int | None = None,
    entity_type: str = "task",
) -> list[GateResult]:
    """Check all gates for the target stage. Returns list of gate results."""
    requires = flow.requires(to_status)
    if not requires:
        return []
    return check_gates(
        requires,
        context_dir=context_dir,
        db=db,
        entity_id=entity_id,
        entity_type=entity_type,
    )


def get_eligible_workers(
    flow: TaskFlow,
    to_status: str,
    class_required: str,
) -> list[str] | None:
    """Which agent classes can work on the target stage. None = current assignee continues."""
    return flow.workers_for(to_status, class_required)


def apply_transition(
    flow_type: str,
    current_status: str,
    class_required: str = "",
    passed: bool = True,
    explicit_target: str | None = None,
    *,
    context_dir: Path | None = None,
    db=None,
    entity_id: int | None = None,
    entity_type: str = "task",
    flows_dir: str | Path | None = None,
) -> TransitionResult:
    """Full transition pipeline — resolve, gate-check, return result.

    Does NOT write to DB — caller handles the actual UPDATE.
    This keeps the engine pure and testable.
    """
    flow = load_flow(flow_type, flows_dir=flows_dir)

    # Step 1: Resolve next status
    result = resolve_next(flow, current_status, passed, explicit_target)
    if not result.success:
        return result

    to_status = result.to_status
    assert to_status is not None

    # Step 2: Check gates
    gate_results = check_transition_gates(
        flow, to_status,
        context_dir=context_dir,
        db=db,
        entity_id=entity_id,
        entity_type=entity_type,
    )
    if gate_results and not all_gates_pass(gate_results):
        failures = [g for g in gate_results if not g.passed]
        return TransitionResult(
            success=False,
            from_status=current_status,
            to_status=to_status,
            gate_failures=failures,
            error=f"gate check failed: {'; '.join(g.message for g in failures)}",
        )

    # Step 3: Determine eligible workers
    eligible = get_eligible_workers(flow, to_status, class_required)

    return TransitionResult(
        success=True,
        from_status=current_status,
        to_status=to_status,
        eligible_classes=eligible,
    )
