# Research: Dependency Analysis — Cross-Requirement Dependencies

## High-Impact Dependencies (must sequence correctly)

### 1.5 (stale terminal) blocks 2.5 (formal state machines)
Adding `stale` to TERMINAL_STATUSES affects state machine validation. Both changes should be coordinated.

### 2.1 (bare exceptions) depends on 2.9 (pattern registry)
Pattern registry should define the error handling convention BEFORE narrowing exceptions — otherwise each file gets a different narrowing strategy.

### 2.4 (contracts/assertions) depends on 2.9 (pattern registry)
Assertion convention (what to assert, where) should be documented before adding more assertions.

### 4.1 (dependency violations) depends on 4.2 (code duplication)
Fixing dependency inversion may require extracting shared code first, which overlaps with deduplication.

### 5.1 (network API) depends on 4.5 (dead code cleanup)
Scaling endpoints should be verified/cleaned before adding new network API commands.

### 5.2 (cross-project coord) depends on 1.2 (global comms fix)
Cross-project coordination relies on global comms working correctly.

## Independent Clusters (can parallelize)

### Cluster A: Correctness bugs (1.1-1.10)
Most correctness items are independent of each other. Exception: 1.5 affects rollup behavior.

### Cluster B: Test infrastructure (3.1-3.3)
Test infrastructure work is independent of feature/bug work but should be done early so new tests follow the pattern.

### Cluster C: CLI consistency (4.3)
Verb vocabulary, exit codes, short flags — all independent of each other and of other work streams.

### Cluster D: Feature requests (5.1-5.5)
Features are lower priority and mostly independent, except 5.2 depends on 1.2.

## Recommended Sequencing
1. Pattern registry (2.9) — establishes conventions for everything else
2. Correctness bugs (1.1-1.10) — fix broken behavior first
3. Test infrastructure (3.1) — enable proper testing for all subsequent work
4. Reliability debt (2.1-2.8) — improve existing code quality
5. Code hygiene (4.1-4.5) — clean up duplication and coupling
6. Features (5.1-5.5) — extend capabilities last

## Items Already Fully Addressed (skip in decomposition)
Based on research, these clean requirements are already implemented:
- 1.3 (poll path resolution — walk-up logic exists)
- 1.4 (global agent heartbeat — coordinator touch exists)
- 1.8 (backlog promote null validation — slug derivation prevents nulls)
- 2.2 (data lifecycle — prune.py exists)
- 2.3 (unbounded logs — stream rotation exists)
- 2.5 (formal state machines — state_machines.py exists)
- 2.8 (message type taxonomy — VALID_MSG_TYPES exists)
- 5.4.3 (cycle detection — _detect_cycles in loader.py)
- 5.3.3 (error remediation hints — output.py has pattern matching)
- 5.3.4 (fuzzy matching — FuzzyGroup in main.py)
- 5.4.1 (auth scope narrowing — SCOPE_RESTRICTIONS exists)

That's 11 of 73 items already fully implemented = ~15% done. Remaining: 62 items.
