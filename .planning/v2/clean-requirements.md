# Clean Requirements — v2

Derived from: raw snapshot + v1 upstream feedback reconciliation.
Iteration: v2 (remediation). System is built and working.
Guidance (UF-007): Remediation is additive — fill gaps, don't restructure.

73 remaining backlog items organized into 5 work streams by priority.

---

## 1. Correctness — Fix Broken Behavior (10 bugs)

### 1.1 DAG Self-Review Bypass
DAG stages `qe` and `verify` can be self-closed by the implementing agent. The system must
mechanically prevent the same agent that implemented a task from advancing it through QE/verify.

### 1.2 Global Comms Delivery Failure
`comms send` with `-C` targeting a foreign project fails silently when the target project's
`messages` table doesn't exist. The system must handle missing tables gracefully (create or error clearly).

### 1.3 Poll Path Resolution
`minion poll` requires exact cwd. It should walk up the directory tree to find `minion.db`,
matching how other tools resolve project roots.

### 1.4 Global Agent Heartbeat
Poll should register/heartbeat the agent in the global coordinator DB so `minion who` at
the global level shows accurate `last_seen` timestamps.

### 1.5 Stale Status Terminal Classification
`stale` status is missing from `TERMINAL_STATUSES`, causing parent task rollup to block
when child tasks are stale.

### 1.6 Terminal Agent Poll Determinism
Terminal agents (claude-code sessions) don't deterministically poll after completing work.
This is the single biggest operational issue — agents go deaf after finishing a task.

### 1.7 Backlog Lineage Linkage
Backlog lineage is missing task linkage for recently promoted items. `requirement_id` not
consistently set on tasks created from promoted backlog items.

### 1.8 Backlog Promote Null Validation
`backlog promote` accepts null `promoted_to` with no validation. Must require a valid
target category.

### 1.9 Backlog Auth on Cross-Project Mutations
Backlog operations via `-C` flag have no auth check — any agent can mutate any project's
backlog. Must enforce agent class restrictions.

### 1.10 Test Promote Crew Display
Test that promote command correctly displays required crew and available characters.

## 2. Reliability — Eliminate Silent Failures (22 debt items)

### 2.1 Bare Exception Cleanup
103 bare `except Exception` blocks across 43 files silently swallow errors. Each must be
narrowed to specific exception types or re-raise after logging.

### 2.2 Data Lifecycle Management
Messages, transition_log, and invocation_log tables grow unboundedly. The system needs
retention policies — age-based pruning, configurable limits.

### 2.3 Unbounded Log Files
`stream.jsonl` log files for long-running daemons have no rotation or size limit. Add
log rotation or max-size truncation.

### 2.4 Contracts and Assertions
Zero contracts or assertions in cross-cutting code (only 5 asserts in production). Add
precondition/postcondition assertions on critical interfaces.

### 2.5 Formal State Machines
Daemon and agent lifecycle transitions are not formally validated. Invalid state transitions
should be mechanically rejected, not just documented.

### 2.6 Assumption Documentation
Key files (daemon constants, HP calculations, token estimates) lack ASSUMPTION comments.
Document what each magic number assumes.

### 2.7 Big-O Documentation
No Big-O documentation on hot paths (dag.py, rollup.py, daemon polling). Document
algorithmic complexity where it matters.

### 2.8 Message Type Taxonomy
All messages are untyped strings. Define a message type taxonomy (order, sitrep, query,
response, alert) for routing and filtering.

### 2.9 Pattern Registry
No pattern registry documenting conventions. Create a living document of decided patterns
(error handling, logging, DB access, config loading).

## 3. Test Coverage — Fill Gaps

### 3.1 Test Infrastructure
- No `conftest.py` — fixture duplication ~150 lines across 11 files. Extract shared fixtures.
- No pytest markers (@pytest.mark.unit/integration/smoke). Add categorization.

### 3.2 Missing Test Suites
- Zero tests for missions package (load_mission, resolve_slots, list_missions, suggest_party)
- Reference integrity tests for CLI commands → backend functions (residual)
- Network API self-exercising client tests (residual)

### 3.3 Verification Artifacts
No verification artifacts produced per DAG stage. Tests should produce evidence of stage
completion.

## 4. Code Hygiene — Eliminate Duplication and Coupling (20 smells)

### 4.1 Dependency Layer Violations
- `db/` package imports from `auth` (dependency inversion violation)
- Task files import private `_tmux` module
- Bidirectional coupling comms <-> crew (comms/register.py has crew-context-merge logic)

### 4.2 Code Duplication
- `_resolve_or_404` duplicated across 3+ network handler modules
- `_append_error_log` duplicated between codex.py and gemini.py
- Role prompt self-service block duplicated 6 times across 7 role prompts
- DBMixin connect-execute-commit-close pattern repeated 10 times
- Provider error classifiers share structural pattern between codex/gemini

### 4.3 CLI Consistency
- Verb vocabulary inconsistencies across command groups
- Exit code inconsistency (mix of 0/1/3 conventions)
- CLI options lack short flags (~244 of 250 options)
- Top-level command leaks (deregister, rename, interrupt, resume exposed at root)

### 4.4 Configuration Consistency
- Config cascade precedence inconsistent — `-C` flag mutates env vars non-transparently
- 5 network env vars bypass `defaults.py`, reading directly from `os.environ`
- Daemon WAL and row_factory inconsistency across connections

### 4.5 Dead/Unreachable Code
- Scaling endpoints registered but unreachable in network API
- Server suppresses HTTP logs entirely (zero observability)
- TaskDB post-close calls raise AttributeError instead of meaningful error
- Bare except in intel auto-link (should be sqlite3.IntegrityError)
- Generic file names violating filesystem-as-db (residual)

## 5. Feature Requests — Extend Capabilities

### 5.1 Network API Evolution
- CLI parity with network API — ~10 missing commands
- Agent presence and availability (GET /who with filtering)
- Agent registry schema for cross-machine delegation
- Composite agent key host/project/name instead of name-only
- 6 gaps from sys-lead review (lineage, overview, alerts, query params, DB policy, full agent view)
- On-demand agent spawning and auto-teardown

### 5.2 Cross-Project Coordination
- Cross-project lead at parent dir with aggregated polling
- All project leads report to sys-lead via global comms
- New agent class: coordinator (system-wide lead over project leads)

### 5.3 Agent Experience
- Agent context refresh — mid-session state injection without compaction
- Cold-start auto-generate operational state (live briefing, not static files)
- Error messages with remediation hints
- Fuzzy matching for CLI commands
- Shell completions for CLI (Click supports it)
- Research prompt assembly strategy for role/character/scope

### 5.4 System Integrity
- Auth scope-based permission narrowing for lead characters
- DAG enforcement — mechanically block code commits without scaffolding
- Cycle detection at flow YAML load time

### 5.5 Dashboard and UI
- Dashboard sys-lead operational views
- Define purpose and scope of dashboard GUI; merge UI into network server
