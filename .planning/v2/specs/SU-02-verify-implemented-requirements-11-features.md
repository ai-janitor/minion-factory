# SU-02: Verify Implemented Requirements — 11 Features

**Wave:** 1 (parallel with wave 0)
**Requirements:** 1.3, 1.4, 1.8, 2.2, 2.3, 2.5, 2.8, 5.3.3, 5.3.4, 5.4.1, 5.4.3
**Dependencies:** None (soft: SU-05 for 2.5 state machine verification)
**Dependents:** None

---

## Purpose

Write or verify tests for 11 already-implemented features that lack test coverage. No production code changes. Each item needs at least one test proving the behavior works as documented.

## Requirements Traceability

| Req | Feature | Implementation Location |
|-----|---------|------------------------|
| 1.3 | Poll path resolution (walk-up) | `src/minion/defaults.py` `resolve_db_path()` |
| 1.4 | Global agent heartbeat | `src/minion/polling.py` `touch_coordinator_activity()` |
| 1.8 | Backlog promote null validation | `src/minion/backlog/promote.py` slug derivation |
| 2.2 | Data lifecycle management (pruning) | `src/minion/db/prune.py` `prune_old_records()` |
| 2.3 | Unbounded log rotation | `src/minion/daemon/runner/_execution.py` stream rotation |
| 2.5 | Formal state machines | `src/minion/state_machines.py` |
| 2.8 | Message type taxonomy | `src/minion/comms/send.py` VALID_MSG_TYPES |
| 5.3.3 | Error remediation hints | `src/minion/output.py` `_add_remediation_hint()` |
| 5.3.4 | Fuzzy matching CLI | `src/minion/cli/main.py` FuzzyGroup |
| 5.4.1 | Auth scope-based narrowing | `src/minion/auth.py` SCOPE_RESTRICTIONS |
| 5.4.3 | Cycle detection in flow YAML | `src/minion/tasks/loader.py` `_detect_cycles()` |

## Dependencies

- **Soft dependency on SU-05:** The 2.5 (state machines) test should verify that `stale` transitions are valid. If SU-05 completes first, test against the updated TERMINAL_STATUSES. If not, write the test against current state and note it needs update.

## Behavior

For each of the 11 features, write one or more tests that:

### 1.3 — Poll Path Resolution
- **Test:** Create a nested directory structure with `.work/minion.db` at the top. Call `resolve_db_path()` from a subdirectory. Assert it finds the DB.
- **Test:** Call from a directory with no `.work/minion.db` anywhere in the ancestor chain. Assert it returns None or raises appropriately.

### 1.4 — Global Agent Heartbeat
- **Test:** Call `touch_coordinator_activity(agent_name)`. Verify the coordinator DB has an updated `last_seen` timestamp for the agent.
- **Test:** Verify heartbeat creates the agent entry if it doesn't exist in coordinator DB.

### 1.8 — Backlog Promote Null Validation
- **Test:** Call `promote()` with a valid file_path. Assert `promoted_to` in the result is never None or empty.
- **Test:** Call `promote()` with edge-case file_path (trailing slash, nested path). Assert slug derivation produces a valid non-empty value.

### 2.2 — Data Lifecycle (Pruning)
- **Test:** Insert old records (>30 days) into messages, transition_log, invocation_log. Call `prune_old_records()`. Assert old records are deleted.
- **Test:** Insert recent records (<30 days). Call `prune_old_records()`. Assert recent records survive.

### 2.3 — Log Rotation
- **Test:** Create a stream.jsonl file exceeding the max size threshold. Trigger rotation logic. Assert original file is renamed to `.1` and a new file is created.

### 2.5 — Formal State Machines
- **Test:** Call `validate_transition()` with a valid transition (e.g., "idle" -> "running" for daemon). Assert it returns True.
- **Test:** Call `validate_transition()` with an invalid transition. Assert it raises `InvalidTransition`.
- **Test:** Verify all states in DAEMON_TRANSITIONS and AGENT_STATUS_TRANSITIONS are reachable.
- **Note:** After SU-05 completes, add test verifying "stale" is a valid terminal state.

### 2.8 — Message Type Taxonomy
- **Test:** Call `send()` with each valid msg_type. Assert all succeed.
- **Test:** Call `send()` with an invalid msg_type. Assert it is rejected with a clear error.

### 5.3.3 — Error Remediation Hints
- **Test:** Trigger a known error pattern (e.g., "not registered"). Assert the output includes a remediation hint.
- **Test:** Trigger an unknown error. Assert no hint is added (no crash, graceful degradation).

### 5.3.4 — Fuzzy Matching
- **Test:** Invoke the CLI with a misspelled command (e.g., "statsu" instead of "status"). Assert the output suggests the correct command.

### 5.4.1 — Auth Scope Narrowing
- **Test:** Call `require_scope("sys")` with an agent that has sys scope. Assert it passes.
- **Test:** Call `require_scope("sys")` with an agent that lacks sys scope. Assert it blocks.

### 5.4.3 — Cycle Detection
- **Test:** Load a flow YAML with a cycle (stage A -> B -> A). Assert `_detect_cycles()` raises an error.
- **Test:** Load a valid flow YAML with no cycles. Assert it loads without error.

## Constraints

- Zero production code changes
- Tests must be runnable with `uv run pytest`
- Each test must be independent (no test-order dependencies)
- Use existing conftest.py fixtures where applicable (isolated_db, etc.)

## Edge Cases

- **Feature regression:** If any test fails, the feature is broken — file a bug immediately, do not fix in this spec unit.
- **Missing test infrastructure:** If a feature requires test setup that doesn't exist (e.g., coordinator DB fixture), create minimal fixture in conftest.py.
- **2.5 + SU-05 ordering:** If SU-05 hasn't completed when writing 2.5 tests, write against current TERMINAL_STATUSES and leave a TODO comment for stale.

## Current State

- All 11 features have production code implementations
- Test coverage varies: some have partial tests, others have none
- conftest.py exists with shared fixtures

## Test Contract

- All 11 features have at least one passing test
- Total new tests: minimum 20 (some features need multiple tests)
- All tests pass with `uv run pytest` on clean checkout
