# Research Findings Summary — v2

## Key Takeaways

### 1. 11 of 73 requirements are already fully implemented (~15%)
The v1 remediation session addressed more items than tracked. These are done:
- 1.3 (poll walk-up), 1.4 (heartbeat), 1.8 (promote validation)
- 2.2 (pruning), 2.3 (log rotation), 2.5 (state machines), 2.8 (msg types)
- 5.3.3 (error hints), 5.3.4 (fuzzy matching), 5.4.1 (auth scopes), 5.4.3 (cycle detection)

### 2. 8 items are partially implemented — need completion, not creation
- 1.2 (global comms — routing works, edge case remains)
- 1.6 (poll determinism — Stop hook exists, needs hardening)
- 1.7 (backlog lineage — promote logs, downstream task linkage unclear)
- 1.9 (backlog auth — promote checks, other mutations unchecked)
- 2.1 (bare exceptions — down from 103 to 87, needs continued narrowing)
- 2.4 (assertions — up from 5 to 45, needs continued expansion)
- 2.6/2.7 (documentation — partial Big-O and assumption comments exist)

### 3. Pattern registry (2.9) should be done first
It establishes conventions that all other work should follow. Without it, different agents will make inconsistent decisions about error handling, logging, and DB access.

### 4. The codebase architecture is solid
Confirming UF-007 from v1: strengths are structural (clean deps, good DB design, agent-first CLI). Weaknesses are gaps and inconsistencies, not design flaws. Remediation remains additive.

### 5. Cross-project coordination (5.2) has infrastructure but no aggregation layer
Coordinator DB, global comms, scope restrictions all exist. What's missing: multi-project poll, coordinator agent class, parent-dir aggregation. Network tier (API GLOBAL) is required for cross-machine use.

### 6. Network API composite key is high-effort, low-urgency
The FQN module exists (`src/minion/network/fqn.py`) but full composite key migration would break backward compat. Recommend deferring to v3 or implementing as supplementary index.

### 7. Test infrastructure is in good shape but not complete
conftest.py centralized, 39 test files exist, pytest markers partially adopted. Main gap: not all files have markers, no verification artifacts per DAG stage.

### 8. Short flags and shell completions are low-risk, high-value DX improvements
Both are mechanical to implement with existing Click infrastructure. Should be scheduled but not prioritized over correctness/reliability.

## Upstream-Affecting Findings

### UF-V2-001: 11 items should be marked as done, not decomposed
Clean requirements 1.3, 1.4, 1.8, 2.2, 2.3, 2.5, 2.8, 5.3.3, 5.3.4, 5.4.1, 5.4.3 are already implemented. They need verification tests but not implementation specs. This reduces the decomposition scope from 73 to 62 items.

### UF-V2-002: Composite agent key (part of 5.1) should be deferred to v3
The schema change is too invasive for remediation. Record as future enhancement.

## Remaining: 62 items for decomposition
- 7 correctness bugs (WS1: 1.1, 1.2, 1.5, 1.6, 1.7, 1.9, 1.10)
- 5 reliability items (WS2: 2.1, 2.4, 2.6, 2.7, 2.9)
- 3 test items (WS3: 3.1, 3.2, 3.3)
- 20 code hygiene items (WS4: all 4.1-4.5 sub-items)
- 27 feature items (WS5: most of 5.1-5.5 minus composite key and already-done items)

Approximate split: 15 high-priority (WS1+WS2), 23 medium (WS3+WS4), 24 lower (WS5).
