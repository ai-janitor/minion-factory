# Test Capability

1. Write tests that prove the code works, not tests that pass. Test behavior and outputs, not implementation details.
2. This is the phase where exception handling gets added. If a code path can fail, write a test that triggers the failure, then add the try/except to handle it. Error handling is earned through a failing test, not guessed upfront.
3. Cover the edges: empty inputs, None, boundary values, concurrency if applicable. Happy path should already work from the code phase.
4. Every test must be runnable independently. No test should depend on another test's side effects or ordering.
5. When a test reveals a bug, file it via `minion create-task` before fixing. The bug exists independently of the test.

## Test Layers

Use the right layer for what you're testing:

### Unit: decision logic with seeded state
For functions that decide based on DB/state: create a temp DB, seed it with known rows, call the function, assert the decision. Cover the full matrix — every combination of state that changes the outcome. Example: a function that returns True/False based on task status should be tested with open tasks, closed tasks, no tasks, other agent's tasks, blocked tasks, etc.

### Unit: pure functions with input/output sequences
For stateless logic (counters, accumulators, threshold checks): feed sequences of inputs, assert outputs. No DB, no mocks. Example: a streak counter that fires after N consecutive low values — test with mixed sequences, resets, boundary values, and excluded inputs (like boot turns).

### Replay: prove it catches real failures
When we have production logs of a known failure, feed that real data through the fix. The test must:
- Fire before the damage point (where the system should have intervened)
- NOT fire during the healthy period (no false positives)
- Quantify how much waste it prevents (turns saved, tokens saved)
This is the highest-confidence test — real data, real failure, real proof.

### Integration: lifecycle
Test the full lifecycle end-to-end: spawn → work → complete → shutdown. Verify state transitions in the DB, process lifecycle (started/killed), and that the system does NOT respawn when it shouldn't. Also test the failure path: give the system work that's already done and verify it detects the no-op and stops.
