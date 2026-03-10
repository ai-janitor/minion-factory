# SU-09: Contract and Assertion Expansion — Critical Interfaces

**Wave:** 3 (depends on SU-01 pattern registry)
**Requirements:** 2.4
**Dependencies:** SU-01
**Dependents:** None

---

## Purpose

Expand precondition/postcondition assertions from 45 to comprehensive coverage across critical interfaces. The pattern registry (SU-01) defines where and how to assert; this spec applies it systematically.

## Requirements Traceability

- **2.4 (Contracts and Assertions):** "Zero contracts or assertions in cross-cutting code (only 5 asserts in production — now 45). Add precondition/postcondition assertions on critical interfaces."

## Dependencies

- **SU-01 (Pattern Registry):** "Contracts and Assertions" section defines: what to assert, where to assert, exception types.

## Behavior

### Current State
- 45 assertions in production code (up from 5 in v1)
- Added during v1 in: polling.py, comms/send.py, tasks/update_task.py, db/prune.py, state_machines.py
- Pattern: `assert param, "param must not be empty"` for strings, `assert isinstance(x, int) and x > 0` for IDs

### Target Coverage

**Tier 1 — DB layer (db/ package):**
- `db/agents.py`: every public function that takes agent_name — assert non-empty string
- `db/connection.py`: `connect()` — assert path is non-empty, `get_db()` — assert returned connection is not None
- `db/prune.py`: already has assertions — verify completeness

**Tier 2 — Crew lifecycle (crew/ package):**
- `crew/spawn.py`: assert crew YAML is valid dict, assert agent_name not empty, assert class is valid
- `crew/stand_down.py`: assert agent_name not empty
- `crew/register.py`: assert name and class not empty, assert class is in VALID_CLASSES

**Tier 3 — Lifecycle (lifecycle.py):**
- `cold_start()`: assert agent_name not empty
- `fenix_down()`: assert agent_name not empty, assert context dict is not None
- `refresh()`: assert agent_name not empty

**Tier 4 — Comms (comms/ package):**
- `comms/delivery.py`: already has assertions — verify completeness
- `comms/send.py`: already has assertions — verify completeness
- `comms/inbox.py`: assert agent_name not empty for check_inbox

**Tier 5 — Tasks (tasks/ package):**
- `tasks/create.py`: assert title not empty, assert flow_type is valid
- `tasks/close.py`: assert task_id is positive int
- `tasks/update_task.py`: already has assertions — verify completeness

### Assertion Pattern (from pattern registry)

```python
# Precondition — function entry
assert agent_name, "agent_name must not be empty"
assert isinstance(task_id, int) and task_id > 0, f"task_id must be positive int, got {task_id}"

# Postcondition — before return (where applicable)
assert result is not None, "expected non-None result"
```

### Inputs/Outputs
- No changes to function signatures
- No changes to return types
- Assertions raise AssertionError on violation (stdlib behavior)

## Constraints

- Follow pattern registry convention exactly
- Do NOT add assertions inside CLI command handlers — Click handles parameter validation
- Do NOT add assertions in test code
- Assertions must not duplicate existing validation (if a function already returns error dict for empty agent_name, the assertion is redundant — but assertions catch programming errors, validation catches user errors, so both are acceptable)
- Must not change any function's behavior for valid inputs

## Edge Cases

1. **Assert vs validate:** Some functions do both `assert agent_name` and `if not agent_name: return error`. The assert catches programming bugs (caller passed None), the validation catches user input errors. Both are valid.
2. **Performance-sensitive paths:** Assertions in hot loops (e.g., poll loop inner iteration) should be outside the loop, not inside. Assert once at function entry, not per iteration.
3. **None vs empty string:** `assert param` catches both None and "". If a function accepts "" as valid input, use `assert param is not None` instead.
4. **List/dict params:** For collection params, assert they are the right type: `assert isinstance(agents, list)`, not just truthy (empty list is valid).
5. **Python -O flag:** When Python runs with optimization (`-O`), assertions are stripped. This is acceptable — assertions are development-time safety nets, not runtime validation.

## Current State

- 45 assertions exist across 5 modules
- Pattern is established and consistent
- Gap: db/agents.py, crew/spawn.py, lifecycle.py, tasks/create.py, tasks/close.py

## Test Contract

- **Test 1:** Call a Tier 1 function with empty agent_name. Assert AssertionError raised.
- **Test 2:** Call a Tier 2 function with invalid class. Assert AssertionError raised.
- **Test 3:** All existing tests still pass (assertions don't fire on valid inputs).
- **Test 4:** Count assertions: `grep -r "^    assert " src/minion/ | wc -l` should be >= 80 (roughly double current 45).
