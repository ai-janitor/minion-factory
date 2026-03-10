# SU-05: Stale Status Terminal Classification

**Wave:** 2 (parallel correctness cluster)
**Requirements:** 1.5
**Dependencies:** None
**Dependents:** None (soft dep to SU-02 for state machine verification)

## Domain Preamble

The `stale` status is missing from `TERMINAL_STATUSES` in dag.py, causing parent task rollup to block when child tasks are marked stale. This spec adds `"stale"` to the terminal set and verifies downstream effects in rollup.py and gates.py. Must coordinate with state machine validation (2.5 already implemented) to ensure stale transitions are valid. One constant change with controlled ripple.

## Scope

- Add `"stale"` to `TERMINAL_STATUSES` frozenset in `dag.py`
- Verify rollup.py behavior with stale children
- Verify gates.py behavior with stale status
- Coordinate with state_machines.py for valid stale transitions

## Affected Files

- `src/minion/tasks/dag.py`
- `src/minion/tasks/rollup.py`
- `tests/test_dag*.py`

## Boundary Edges

- E-11 (soft): → SU-02 (state-transition: stale in TERMINAL_STATUSES affects state machine verification)
- B-01 (internal): dag.py ↔ rollup.py (state-transition: rollup reads TERMINAL_STATUSES)
