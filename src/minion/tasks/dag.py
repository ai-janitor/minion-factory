"""TaskFlow — query transitions, workers, and requirements from a loaded DAG.

Purpose: TaskFlow — query transitions, workers, and requirements from a loaded DAG.
Rationale: Extracted into own module for single-responsibility task management.
Responsibility: TaskFlow — query transitions, workers, and requirements from a loaded DAG. NOT responsible for unrelated concerns.
Organization: Standalone functions and/or a single class. See source."""

from __future__ import annotations

from dataclasses import dataclass, field

# Single source of truth for terminal task statuses.
# Import this everywhere instead of redefining inline — was drifting across rollup.py, gates.py.
TERMINAL_STATUSES: frozenset[str] = frozenset({"closed", "abandoned", "obsolete", "completed", "stale", "done"})


@dataclass
class Stage:
    name: str
    description: str
    next: str | None = None
    fail: str | None = None
    alt_next: str | None = None
    workers: dict[str, list[str]] | list[str] | None = None
    requires: list[str] = field(default_factory=list)
    terminal: bool = False
    skip: bool = False
    parked: bool = False
    spawns: str | None = None
    protocol: str | None = None
    context: str | None = None
    context_template: str | None = None
    gate: str | None = None


@dataclass
class TaskFlow:
    name: str
    description: str
    stages: dict[str, Stage]
    dead_ends: list[str] = field(default_factory=list)

    def _resolve_skip(self, stage_name: str | None, seen: set[str] | None = None) -> str | None:
        """Follow skip chain until we hit a non-skipped stage or None.

        Time complexity: O(k) where k = length of skip chain (bounded by number of stages).
        Space complexity: O(k) for the seen set (cycle detection).
        """
        if stage_name is None:
            return None
        if seen is None:
            seen = set()
        if stage_name in seen:
            return None
        seen.add(stage_name)
        stage = self.stages.get(stage_name)
        if stage is None:
            return stage_name
        if stage.skip:
            return self._resolve_skip(stage.next, seen)
        return stage_name

    def next_status(self, current: str, passed: bool = True) -> str | None:
        """Given current status and pass/fail, return the next status.
        Resolves skip stages — if next stage has skip=true, jump to the one after.

        Time complexity: O(1) dict lookup + O(k) skip resolution.
        """
        stage = self.stages.get(current)
        if stage is None or stage.terminal:
            return None
        target = stage.next if passed else stage.fail
        return self._resolve_skip(target)

    def workers_for(self, status: str, class_required: str) -> list[str] | None:
        """Which agent classes can work on this stage for a task with given class_required.
        Returns None if the already-assigned agent continues.

        Time complexity: O(1) — two dict lookups.
        """
        stage = self.stages.get(status)
        if stage is None:
            return None
        workers = stage.workers
        if workers is None:
            return None
        if isinstance(workers, list):
            return workers
        if class_required in workers:
            return workers[class_required]
        return workers.get("default")

    def all_required_classes(self, class_required: str = "") -> dict[str, list[str]]:
        """Return all unique worker classes needed across all stages.

        Returns dict mapping class_name → list of stage names where that class is needed.
        Skips stages where workers is None (current assignee continues).

        Time complexity: O(S * W) where S = number of stages, W = max workers per stage.
        """
        class_stages: dict[str, list[str]] = {}
        for stage_name, stage in self.stages.items():
            eligible = self.workers_for(stage_name, class_required)
            if eligible is not None:
                for cls in eligible:
                    class_stages.setdefault(cls, []).append(stage_name)
        return class_stages

    def requires(self, status: str) -> list[str]:
        """Preconditions before transitioning INTO this status."""
        stage = self.stages.get(status)
        if stage is None:
            return []
        return stage.requires

    def valid_transitions(self, current: str) -> set[str]:
        """All valid next statuses from current (including dead_ends and alt_next).

        Time complexity: O(D + k) where D = number of dead_ends, k = skip chain length.
        """
        stage = self.stages.get(current)
        if stage is None or stage.terminal:
            return set()
        result = set(self.dead_ends)
        next_resolved = self._resolve_skip(stage.next)
        if next_resolved:
            result.add(next_resolved)
        if stage.fail:
            result.add(stage.fail)
        if stage.alt_next:
            alt_resolved = self._resolve_skip(stage.alt_next)
            if alt_resolved:
                result.add(alt_resolved)
        return result

    def transition(self, current: str, class_required: str, passed: bool = True) -> Transition | None:
        """Single-call routing: next status + eligible worker classes."""
        to_status = self.next_status(current, passed)
        if to_status is None:
            return None
        eligible = self.workers_for(to_status, class_required)
        return Transition(to_status=to_status, eligible_classes=eligible)

    def is_terminal(self, status: str) -> bool:
        """Is this a terminal stage?"""
        stage = self.stages.get(status)
        if stage is None:
            return False
        return stage.terminal

    def has_gate(self, gate_name: str) -> bool:
        """Check if any stage in the flow has a gate with the given name."""
        return any(s.gate == gate_name for s in self.stages.values())

    def past_gate(self, current_status: str, gate_name: str) -> bool:
        """Check if current_status is at or past the stage with the given gate.

        Walks the happy path from the gated stage. If current_status is the
        gated stage or any stage reachable from it, returns True.

        Time complexity: O(S) where S = number of stages (linear walk + linear scan for gate).
        """
        # Find the stage with this gate
        gated_stage = None
        for name, stage in self.stages.items():
            if stage.gate == gate_name:
                gated_stage = name
                break
        if gated_stage is None:
            return True  # no gate = always past it

        # Walk from gated stage forward — if current_status is reachable, we're past
        reachable: set[str] = {gated_stage}
        cursor = self.stages[gated_stage].next
        visited: set[str] = set()
        while cursor and cursor not in visited:
            visited.add(cursor)
            reachable.add(cursor)
            stage = self.stages.get(cursor)
            if stage is None:
                break
            cursor = stage.next
        return current_status in reachable

    def render_dag(self, current_status: str | None = None) -> str:
        """Render DAG as inline text showing phases and current position.

        Example: open → assigned → [IN_PROGRESS] → fixed(oracle) → verified(lead) → closed

        Time complexity: O(S) where S = number of stages (linear walk of happy path).
        """
        # Walk the happy path from first stage
        parts: list[str] = []
        visited: set[str] = set()
        # Find the starting stage (first one that nothing points to as 'next')
        pointed_to = {s.next for s in self.stages.values() if s.next}
        starts = [name for name in self.stages if name not in pointed_to]
        cursor = starts[0] if starts else next(iter(self.stages), None)

        while cursor and cursor not in visited:
            visited.add(cursor)
            stage = self.stages.get(cursor)
            if stage is None:
                break

            # Format: [STATUS] if current, status(workers) otherwise
            label = cursor.upper() if current_status and cursor == current_status else cursor
            if current_status and cursor == current_status:
                label = f"[{label}]"

            # Show worker classes if stage reassigns
            workers = stage.workers
            if workers and cursor != current_status:
                if isinstance(workers, list):
                    label += f"({','.join(workers)})"
                elif isinstance(workers, dict):
                    # Use default workers list
                    default = workers.get("default", [])
                    if default:
                        label += f"({','.join(default)})"

            parts.append(label)
            cursor = stage.next

        return " → ".join(parts)


@dataclass
class Transition:
    to_status: str
    eligible_classes: list[str] | None  # None = current assignee continues
