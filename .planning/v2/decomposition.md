# Decomposition — v2 Remediation

Derived from: clean-requirements.md (73 items), research findings (8 files), upstream-feedback.md (3 items).
Guidance: Remediation is additive (UF-007). Group by affected subsystem, not requirement number.

## Scope Summary

| Category | Count | Items |
|----------|-------|-------|
| Verify-only (already implemented) | 11 | 1.3, 1.4, 1.8, 2.2, 2.3, 2.5, 2.8, 5.3.3, 5.3.4, 5.4.1, 5.4.3 |
| Deferred to v3 | 1 | 5.1 composite agent key |
| Partial implementation (completion) | 8 | 1.2, 1.6, 1.7, 1.9, 2.1, 2.4, 2.6, 2.7 |
| Full implementation | 53 | Remainder |
| **Total in scope** | **72** | (73 minus 1 deferred) |

---

## Spec Units

### Wave 0: Foundation (blocking — all other waves depend on this)

#### SU-01: Pattern Registry
- **Requirements:** 2.9
- **Scope:** Create `.work/pattern-registry.md` documenting decided conventions: error handling (raise vs return dict), DB access (get_db + cursor + try/finally), config resolution (defaults.py), logging setup, auth decoration, message delivery pattern.
- **Affected files:** `.work/pattern-registry.md` (new)
- **Dependencies:** None
- **Why one unit:** This is a documentation artifact that establishes conventions for all subsequent code work. No code changes — pure documentation. Must be done first so all agents follow consistent patterns.
- **Dependency reason:** 2.1 (bare exceptions), 2.4 (assertions), 4.2 (deduplication) all need established patterns before they can be worked.

---

### Wave 1: Verify-Only (parallel — no code changes, test-writing only)

#### SU-02: Verify Implemented Requirements
- **Requirements:** 1.3, 1.4, 1.8, 2.2, 2.3, 2.5, 2.8, 5.3.3, 5.3.4, 5.4.1, 5.4.3
- **Scope:** Write or verify tests for 11 already-implemented features. No production code changes. Each item needs at least one test proving the behavior works.
- **Affected files:** `tests/` (new test functions in existing test files or new test files)
- **Dependencies:** None (production code already exists)
- **Why one unit:** All 11 items share the same work pattern — read the existing implementation, write a test. No production code coupling between them. Can be subdivided among multiple agents if needed, but the scope is uniform enough to track as one unit.

---

### Wave 2: Correctness Fixes (parallel cluster — independent bugs)

#### SU-03: DAG Self-Review Bypass Prevention
- **Requirements:** 1.1
- **Scope:** Add check in `complete_phase()` preventing the implementing agent from advancing through qe/verify stages. Query transition_log for last implementer.
- **Affected files:** `src/minion/tasks/update_task.py`, `tests/test_dag_*.py`
- **Dependencies:** None
- **Why one unit:** Single behavioral change in one function with one test.

#### SU-04: Global Comms Cross-Project Edge Cases
- **Requirements:** 1.2
- **Scope:** Fix `route_cross_repo` to handle missing messages table in foreign project DBs. Verify or create table on demand, or error clearly.
- **Affected files:** `src/minion/comms/delivery.py`, `tests/test_comms*.py`
- **Dependencies:** None
- **Why one unit:** Single edge case in one delivery function.

#### SU-05: Stale Status Terminal Classification
- **Requirements:** 1.5
- **Scope:** Add `"stale"` to TERMINAL_STATUSES. Verify rollup.py and gates.py behavior. Coordinate with state machine validation (2.5 already implemented — verify stale transitions are valid).
- **Affected files:** `src/minion/tasks/dag.py`, `src/minion/tasks/rollup.py`, `tests/test_dag*.py`
- **Dependencies:** None
- **Why one unit:** One constant change with controlled ripple to rollup and gates.

#### SU-06: Terminal Agent Poll Determinism Hardening
- **Requirements:** 1.6
- **Scope:** Verify Stop hook installation. Harden poll-on-stop.sh. Consider mechanical poll auto-restart if hook is insufficient.
- **Affected files:** `scripts/poll-on-stop.sh`, `src/minion/polling.py`, `tests/test_polling*.py`
- **Dependencies:** None
- **Why one unit:** Single operational concern — poll reliability.

#### SU-07: Backlog Lineage and Auth Hardening
- **Requirements:** 1.7, 1.9, 1.10
- **Scope:** (a) Verify requirement_id propagation from promote to task creation. (b) Add auth checks to all backlog write operations (add, update, close) when using `-C` flag. (c) Write test for crew display in promote output.
- **Affected files:** `src/minion/backlog/promote.py`, `src/minion/cli/backlog_cmds.py`, `tests/test_backlog.py`
- **Dependencies:** None
- **Why one unit:** All three items touch the backlog subsystem. They co-change the same files. Splitting would create merge conflicts. (CA-COMP-4: classes that change together belong together.)

---

### Wave 3: Reliability and Quality (depends on Wave 0 pattern registry)

#### SU-08: Bare Exception Narrowing
- **Requirements:** 2.1
- **Scope:** Narrow 87 remaining `except Exception` blocks to specific exception types, following the pattern registry convention. Priority: daemon, polling, comms modules.
- **Affected files:** ~43 files across `src/minion/` (see research for distribution)
- **Dependencies:** SU-01 (pattern registry — defines error handling convention)
- **Why one unit:** Same mechanical change repeated across many files. Subdivide by module group for parallel execution, but track as one deliverable. Each file narrowing follows the same pattern.

#### SU-09: Contract and Assertion Expansion
- **Requirements:** 2.4
- **Scope:** Add precondition/postcondition assertions to critical interfaces not yet covered: db/agents.py, crew/spawn.py, lifecycle.py, and others. Follow pattern registry convention for what/where to assert.
- **Affected files:** ~15 files across `src/minion/` (priority: db, crew, lifecycle)
- **Dependencies:** SU-01 (pattern registry — defines assertion convention)
- **Why one unit:** Same pattern (add assertions) applied across many files. All follow the convention from pattern registry.

#### SU-10: Documentation Debt — Assumptions and Big-O
- **Requirements:** 2.6, 2.7
- **Scope:** (a) Audit files with magic numbers, add ASSUMPTION comments where missing. (b) Add Big-O documentation to remaining hot paths (rollup.py, remaining dag.py functions).
- **Affected files:** Various files across `src/minion/` — daemon constants, HP calculations, token estimates, rollup, polling
- **Dependencies:** SU-01 (pattern registry — documents what counts as a "magic number" and how to annotate)
- **Why one unit:** Both are documentation-only changes (no behavior change). Same audit+annotate workflow. Co-worked by the same type of agent.

---

### Wave 4: Test Infrastructure (parallel with Wave 2-3, enables better testing for later waves)

#### SU-11: Test Infrastructure Completion
- **Requirements:** 3.1
- **Scope:** (a) Add pytest markers to remaining ~36 test files. (b) Register custom markers in pyproject.toml. (c) Verify conftest.py fixture coverage.
- **Affected files:** `tests/*.py`, `pyproject.toml`
- **Dependencies:** None
- **Why one unit:** Infrastructure-only changes that enable test filtering. No production code. Uniform mechanical work.

#### SU-12: Missing Test Suites and Verification Artifacts
- **Requirements:** 3.2, 3.3
- **Scope:** (a) Verify coverage gaps by comparing test files to source modules — identify modules without test coverage. (b) Design verification artifact strategy — what each DAG stage produces as evidence of completion.
- **Affected files:** `tests/` (new test files for uncovered modules), `.planning/v2/verification-strategy.md` (new)
- **Dependencies:** SU-11 (test infrastructure should be clean first)
- **Why one unit:** Both address "how do we know tests are sufficient." The coverage gap analysis feeds into the verification artifact design.

---

### Wave 5: Code Hygiene (depends on Wave 0 pattern registry, parallel within wave)

#### SU-13: Dependency Layer Violation Fixes
- **Requirements:** 4.1
- **Scope:** (a) Audit and fix db/ imports from auth. (b) Verify task files don't import _tmux directly. (c) Break comms <-> crew bidirectional coupling.
- **Affected files:** `src/minion/db/*.py`, `src/minion/tasks/*.py`, `src/minion/comms/register.py`, `src/minion/crew/*.py`
- **Dependencies:** SU-14 (deduplication may create shared modules that fix dependency violations)
- **Why one unit:** All three sub-items are about import direction. Fixing one may affect where shared code lives, which affects the others. Must be coordinated.

#### SU-14: Code Deduplication
- **Requirements:** 4.2
- **Scope:** (a) Extract shared _append_error_log between codex.py and gemini.py. (b) Deduplicate role prompt self-service block (6 times across 7 role prompts). (c) Verify DBMixin dedup from v1 is complete. (d) Extract shared provider error classifier pattern.
- **Affected files:** `src/minion/providers/codex.py`, `src/minion/providers/gemini.py`, `src/minion/prompts/roles/*.py`, `src/minion/db/connection.py`
- **Dependencies:** SU-01 (pattern registry — defines the canonical pattern for each concern)
- **Why one unit:** All items are "extract duplication into shared code." The extracted patterns must be consistent (per pattern registry). Co-working prevents creating new duplication while fixing old.

#### SU-15: CLI Consistency
- **Requirements:** 4.3
- **Scope:** (a) Audit and standardize verb vocabulary across command groups. (b) Standardize exit codes (define convention: 0=success, 1=error, 2=usage). (c) Add short flags to high-frequency CLI options. (d) Move top-level command leaks (deregister, rename, interrupt, resume) into proper command groups.
- **Affected files:** `src/minion/cli/*.py`
- **Dependencies:** None (CLI surface changes, no shared code concerns)
- **Why one unit:** All sub-items are CLI surface polish. Same files, same review. Splitting would create merge conflicts in cli.py.

#### SU-16: Configuration Consistency
- **Requirements:** 4.4
- **Scope:** (a) Audit `-C` flag env var mutation for transparency. (b) Verify remaining network env vars route through defaults.py (research says 5 were fixed). (c) Verify daemon WAL consistency (research says connection.py standardizes this).
- **Affected files:** `src/minion/defaults.py`, `src/minion/cli/main.py`
- **Dependencies:** None
- **Why one unit:** Small audit scope — research indicates most items already fixed. This is primarily verification + fixing any remaining gaps.

#### SU-17: Dead Code and Unreachable Path Cleanup
- **Requirements:** 4.5
- **Scope:** (a) Verify scaling endpoint router registration — fix or remove. (b) Add HTTP request logging to network server. (c) Fix TaskDB post-close error messaging. (d) Narrow intel auto-link bare except to sqlite3.IntegrityError. (e) Rename remaining generic file names.
- **Affected files:** `src/minion/network/handlers/scaling.py`, `src/minion/network/server.py`, `src/minion/tasks/*.py`, `src/minion/intel/*.py`
- **Dependencies:** None
- **Why one unit:** All items are "find dead/wrong thing, fix it." Small scope per item, same audit workflow.

---

### Wave 6: Features — Cross-Project and Agent Experience (depends on Wave 2 correctness fixes)

#### SU-18: Network API CLI Parity and Gaps
- **Requirements:** 5.1 (minus composite key — deferred to v3)
- **Scope:** (a) Identify ~10 CLI commands without network API equivalents. Add handlers. (b) Verify GET /who filtering works. (c) Audit 6 sys-lead review gaps (lineage, overview, alerts, query params, DB policy, full agent view). (d) Wire scaling endpoints to router or remove.
- **Affected files:** `src/minion/network/handlers/*.py`, `src/minion/network/routes.py`
- **Dependencies:** SU-17 (dead code cleanup — scaling endpoints must be resolved first)
- **Why one unit:** All items extend the same HTTP API surface. Same handler pattern, same router registration, same test infrastructure.

#### SU-19: Cross-Project Coordination
- **Requirements:** 5.2
- **Scope:** (a) Implement aggregated multi-project polling (iterate coordinator DB for all agent project paths). (b) Add coordinator agent class to agent-classes.yaml. (c) Wire project leads → sys-lead reporting via global comms.
- **Affected files:** `src/minion/polling.py`, `src/minion/auth.py`, `src/minion/crew/agent-classes.yaml`, `src/minion/comms/*.py`
- **Dependencies:** SU-04 (global comms must work correctly first)
- **Why one unit:** Cross-project coordination is one coherent feature. The polling, auth, and comms changes are tightly coupled — multi-project poll requires the coordinator class which requires auth changes.

#### SU-20: Agent Experience Improvements
- **Requirements:** 5.3.1 (refresh already done — verify), 5.3.2 (cold-start live briefing), 5.3.5 (shell completions), 5.3.6 (research prompt assembly)
- **Scope:** (a) Verify refresh command works as documented. (b) Enhance cold-start to auto-generate live operational briefing. (c) Add shell completion support via Click's `_MINION_COMPLETE`. (d) Document research prompt assembly strategy.
- **Affected files:** `src/minion/lifecycle.py`, `src/minion/cli/main.py`, `src/minion/prompts/*.py`
- **Dependencies:** None
- **Why one unit:** All items improve agent DX. Independent of each other but small enough individually that separate specs would be too granular.

#### SU-21: DAG Scaffolding Enforcement
- **Requirements:** 5.4.2
- **Scope:** Add mechanical gate in DAG flow preventing code commits without scaffolding stage completion. Could be a pre-commit hook or a DAG stage check.
- **Affected files:** `src/minion/tasks/update_task.py`, `src/minion/tasks/dag.py`
- **Dependencies:** SU-03 (DAG changes must be coordinated)
- **Why one unit:** Single behavioral addition to the DAG engine.

#### SU-22: Dashboard and UI Consolidation
- **Requirements:** 5.5
- **Scope:** (a) Define dashboard purpose and scope. (b) Verify/complete dashboard merge into network server. (c) Add sys-lead operational views.
- **Affected files:** `src/minion/dashboard/*.py`, `src/minion/network/dashboard.py`
- **Dependencies:** SU-18 (network API should be stable before adding dashboard)
- **Why one unit:** Dashboard is one coherent subsystem. The merge and operational views share templates and routes.

---

## Dependency Graph

```
Wave 0:  SU-01 (pattern registry)
           |
           +------+------+------+
           |      |      |      |
Wave 1:  SU-02  (verify-only, independent)
           |
Wave 2:  SU-03  SU-04  SU-05  SU-06  SU-07  (parallel correctness)
           |      |
Wave 3:  SU-08  SU-09  SU-10  (depend on SU-01)
           |
Wave 4:  SU-11 → SU-12  (test infrastructure)
           |
Wave 5:  SU-13 ← SU-14  SU-15  SU-16  SU-17  (code hygiene, mostly parallel)
           |                             |
Wave 6:  SU-18 ←------------------------+  SU-19 ← SU-04
         SU-20  SU-21 ← SU-03  SU-22 ← SU-18
```

### Explicit Dependencies (edges)

| From | To | Reason |
|------|----|--------|
| SU-01 | SU-08 | Pattern registry defines error handling convention |
| SU-01 | SU-09 | Pattern registry defines assertion convention |
| SU-01 | SU-10 | Pattern registry defines documentation conventions |
| SU-01 | SU-14 | Pattern registry defines canonical patterns to deduplicate toward |
| SU-04 | SU-19 | Cross-project coordination requires global comms to work |
| SU-03 | SU-21 | DAG enforcement builds on DAG self-review changes |
| SU-11 | SU-12 | Test coverage analysis needs markers infrastructure |
| SU-14 | SU-13 | Deduplication may create shared modules that resolve dependency violations |
| SU-17 | SU-18 | Dead code (scaling endpoints) resolved before adding new API endpoints |
| SU-18 | SU-22 | Dashboard views depend on stable network API |

### Parallelism Summary

| Wave | Parallel Units | Sequential Gate |
|------|---------------|-----------------|
| 0 | SU-01 only | Blocks waves 3, 5 |
| 1 | SU-02 | Independent — can run parallel with Wave 0 |
| 2 | SU-03, SU-04, SU-05, SU-06, SU-07 | All independent |
| 3 | SU-08, SU-09, SU-10 | After SU-01 |
| 4 | SU-11, then SU-12 | SU-11 before SU-12 |
| 5 | SU-14 then SU-13; SU-15, SU-16, SU-17 parallel | SU-14 before SU-13 |
| 6 | SU-18 then SU-22; SU-19, SU-20, SU-21 parallel | Various deps |

---

## CS-Foundations Decomposition Review

### CS-SEP (Separation of Concerns)
- Read/write split: Not applicable (SQLite single-writer model). No CQRS needed.
- Command/query: CLI commands already separated (cli/ package). Network handlers follow REST conventions.
- Layers: Existing 3-layer architecture (CLI → core logic → DB) preserved. Specs do not cross layers.
- Bounded contexts: Spec units align with existing module boundaries (backlog, comms, tasks, network, daemon).
- API surface: Network API surface changes isolated to SU-18. CLI surface changes isolated to SU-15.

### CS-DATA (Data)
- Ownership: Each spec unit names its affected files. No shared-write conflicts between parallel units.
- State model: SU-05 (stale status) is the only state model change. Coordinated with existing state_machines.py.
- Storage: SQLite schema unchanged. No migrations needed in v2.
- Schema: No schema changes — remediation is additive behavior, not structural.
- Lifecycle: SU-02 verifies existing pruning/rotation. No new lifecycle concerns.
- Derived data: Rollup (derived from task states) affected by SU-05 only.

### CS-COMM (Communication)
- Sync/async: All comms remain synchronous (SQLite + filesystem). No async introduction.
- Integrations: SU-19 (cross-project) extends existing coordinator DB integration.
- Events: Message type taxonomy (2.8) already implemented. SU-18 may add new message-based features.
- API style: REST preserved for network API. CLI preserved for local.
- Serialization: JSON for network, dict for internal. No changes.

### CS-CONSIST (Consistency)
- Transactions: SQLite WAL mode for all connections (already standardized). No changes needed.
- Concurrency: Daemon polling is the only concurrent access point. SU-06 hardens poll determinism.
- Idempotency: SU-07 (backlog lineage) must verify idempotent promote behavior.
- Ordering: Wave dependency graph ensures consistent build order.

### CS-SCALE (Scale)
- Load: No scaling changes. System is single-machine SQLite.
- Hot path: SU-10 documents Big-O on remaining hot paths.
- Caching: No caching layer exists or is needed at current scale.
- Big-O: SU-10 explicitly addresses this.
- Resource bounds: SU-08 (bare exceptions) prevents unbounded error propagation.

### CS-SEC (Security)
- Trust boundaries: SU-07 (backlog auth) fixes missing auth checks on cross-project mutations.
- AuthN/AuthZ: SU-19 adds coordinator class. SU-07 hardens backlog auth.
- Secrets: No secret changes. Env vars routed through defaults.py.
- Input validation: SU-08 (exception narrowing) improves input handling at module boundaries.

### CS-ERR (Error Handling)
- Failure taxonomy: SU-01 (pattern registry) defines error handling convention.
- Retry: No retry logic needed (SQLite is local, network retry is out of scope).
- Partial failure: SU-04 (global comms) fixes partial failure in cross-project delivery.
- Degradation: SU-06 (poll hardening) prevents agent deafness.
- Observability: SU-17 adds HTTP request logging. SU-10 documents assumptions.

### PP-ORTH-1, PP-ORTH-3 (Orthogonality)
- Each spec unit is self-contained — changes within one unit do not require changes in another (except explicit dependencies).
- The only cross-unit ripple points are documented as dependency edges.

### PP-DRY-1 (No Duplicated Knowledge)
- SU-14 (deduplication) is explicitly dedicated to removing DRY violations.
- No two spec units cover the same requirement.

### CA-COMP-1 (No Cycles)
- Dependency graph is acyclic. Verified: no unit A depends on B depends on A.

### CA-COMP-4, CA-COMP-5 (Co-change/co-use grouping)
- SU-07 groups backlog lineage + auth + test (all touch backlog subsystem).
- SU-05 groups stale status + rollup (co-change).
- SU-13 + SU-14 grouped in sequence (dedup feeds into dependency fixes).
