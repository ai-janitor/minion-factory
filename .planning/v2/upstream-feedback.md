# Upstream Feedback — v2

Accumulated findings that affect upstream artifacts (clean requirements, DAG definition).

## Stage 3 (Research) Findings

### UF-V2-001: 11 clean requirements already fully implemented
- **Layer wrong:** Clean requirements listed these as remaining work; research shows they are done.
- **Items:** 1.3, 1.4, 1.8, 2.2, 2.3, 2.5, 2.8, 5.3.3, 5.3.4, 5.4.1, 5.4.3
- **Impact:** Decomposition scope reduces from 73 to 62 items. These 11 need verification tests only, not implementation.
- **Resolution:** Mark as "verify-only" at decomposition. Create lightweight test-only specs rather than full implementation specs.

### UF-V2-002: Composite agent key (5.1 sub-item) should defer to v3
- **Layer wrong:** Clean requirements included composite agent key as part of WS5.1 network API evolution.
- **What happened:** Research shows the schema change (name-only primary key to host/project/name composite) breaks backward compat across every agent-referencing query. FQN module exists but is supplementary, not primary key.
- **Impact:** This sub-item is too invasive for a remediation iteration. It requires a migration strategy, not a quick fix.
- **Resolution:** Remove from v2 decomposition scope. Record in v3 backlog.

### UF-V2-003: Pattern registry (2.9) is a prerequisite for most other work
- **Layer wrong:** Clean requirements listed pattern registry as just another reliability item. Research shows it's a dependency for WS2.1 (bare exceptions), WS2.4 (assertions), and WS4.2 (deduplication).
- **Impact:** Should be sequenced as the first item in the decomposition, not parallel with other work.
- **Resolution:** Elevate 2.9 to blocking dependency at decomposition. All code-touching items depend on established patterns.
