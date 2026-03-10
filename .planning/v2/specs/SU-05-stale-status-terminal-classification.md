# SU-05: Stale Status Terminal Classification

**Wave:** 2 (parallel correctness cluster)
**Requirements:** 1.5
**Dependencies:** None
**Dependents:** SU-02 (soft — state machine verification)

---

## Purpose

Add `"stale"` to `TERMINAL_STATUSES` in dag.py so parent task rollup no longer blocks when child tasks are stale. Currently, a stale child is treated as non-terminal, preventing the parent from advancing.

## Requirements Traceability

- **1.5 (Stale Status Terminal Classification):** "stale status is missing from TERMINAL_STATUSES, causing parent task rollup to block when child tasks are stale."

## Dependencies

None.

## Behavior

### Current State
- `TERMINAL_STATUSES = frozenset({"closed", "abandoned", "obsolete", "completed"})` (dag.py line 14)
- rollup.py imports TERMINAL_STATUSES from dag.py (line 18)
- When all sibling tasks must be in TERMINAL_STATUSES for rollup to trigger, a stale child blocks the parent indefinitely

### Target State

**Change 1:** Add `"stale"` to TERMINAL_STATUSES:
```
TERMINAL_STATUSES = frozenset({"closed", "abandoned", "obsolete", "completed", "stale"})
```

**Change 2:** Verify rollup behavior
- rollup.py `_rollup_task_to_requirement()` checks `row["status"] in TERMINAL_STATUSES` for each sibling
- With stale added, a parent with children `[closed, stale, completed]` will now rollup correctly
- Verify the rollup target status is appropriate when some children are stale (should rollup to "completed" only if at least one child is "closed"/"completed", not if ALL are stale/abandoned)

**Change 3:** Verify state_machines.py
- If state_machines.py defines valid transitions, ensure there are valid transitions INTO "stale" (e.g., from "assigned", "in_progress", "blocked")
- Ensure there are NO valid transitions OUT OF "stale" (it's terminal — once stale, stays stale)
- If state_machines.py doesn't cover task statuses (only daemon/agent), no change needed there

**Change 4:** Verify gates.py
- If gates.py has any terminal-status-aware logic, verify it handles "stale" correctly

### State Changes
- One constant change in dag.py
- No DB schema changes
- No new states — "stale" already exists as a status value in the system, it just wasn't classified as terminal

## Constraints

- Must not change the meaning of other terminal statuses
- Must not affect tasks that are not stale
- Rollup behavior for fully-closed parent chains must remain unchanged

## Edge Cases

1. **All children stale:** Parent has 3 children, all stale. Rollup triggers. What status does parent get? Should be "stale" (propagate upward) — all work abandoned.
2. **Mix of stale and completed:** Parent has children `[completed, stale]`. Rollup triggers. Parent should become "completed" — some work was done.
3. **Mix of stale and closed:** Same as above — parent becomes "closed".
4. **Stale child with non-terminal sibling:** Parent has `[stale, in_progress]`. Rollup should NOT trigger — non-terminal sibling still active.
5. **Deeply nested stale chain:** Grandchild stale -> child rollup -> parent rollup. Verify recursive rollup works with stale.

## Current State

- TERMINAL_STATUSES missing "stale" — confirmed in source code
- rollup.py correctly imports from dag.py — the constant change propagates automatically
- state_machines.py needs verification for stale transitions

## Test Contract

- **Test 1:** Add "stale" to TERMINAL_STATUSES. Assert `"stale" in TERMINAL_STATUSES`.
- **Test 2:** Create parent with children `[closed, stale]`. Trigger rollup. Assert parent advances.
- **Test 3:** Create parent with children `[stale, in_progress]`. Assert rollup does NOT trigger.
- **Test 4:** Create parent with all stale children. Assert parent becomes stale.
- **Test 5:** Verify `is_terminal("stale")` returns True for all flow types.
