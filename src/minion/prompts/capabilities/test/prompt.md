# Test Capability

1. Write tests that prove the code works, not tests that pass. Test behavior and outputs, not implementation details.
2. This is the phase where exception handling gets added. If a code path can fail, write a test that triggers the failure, then add the try/except to handle it. Error handling is earned through a failing test, not guessed upfront.
3. Cover the edges: empty inputs, None, boundary values, concurrency if applicable. Happy path should already work from the code phase.
4. Every test must be runnable independently. No test should depend on another test's side effects or ordering.
5. When a test reveals a bug, file it via `minion create-task` before fixing. The bug exists independently of the test.
