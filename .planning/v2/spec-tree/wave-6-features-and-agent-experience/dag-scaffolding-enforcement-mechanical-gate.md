# SU-21: DAG Scaffolding Enforcement — Mechanical Gate

**Wave:** 6 (depends on SU-03 DAG self-review changes)
**Requirements:** 5.4.2
**Dependencies:** SU-03 (DAG changes must be coordinated)
**Dependents:** None

## Domain Preamble

The "no code without scaffolding" rule is currently prompt-enforced only. This spec adds a mechanical gate in the DAG flow preventing code commits without scaffolding stage completion. Could be a pre-commit hook or a DAG stage check in `complete_phase()`. Builds on SU-03's changes to the same function — both add validation checks that are additive (AND logic).

## Scope

- Add scaffolding-completion check to DAG phase advancement
- Coordinate with SU-03's agent-identity check (both modify `complete_phase()`)
- Checks are additive AND — both must pass for phase advancement

## Affected Files

- `src/minion/tasks/update_task.py`
- `src/minion/tasks/dag.py`

## Boundary Edges

- E-06: SU-03 → this (state-transition: shared `complete_phase()` validation block)
