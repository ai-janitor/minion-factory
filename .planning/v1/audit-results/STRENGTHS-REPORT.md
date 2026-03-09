# Strengths Report — v1 Audit

**Date:** 2026-03-09
**Source:** Consolidated strengths from all 11 audit reports (AU-00 through AU-10)

These are patterns to PRESERVE and potentially extend to weaker areas.

---

## 1. Clean Dependency Architecture

**Found by:** AU-00, AU-02, AU-04, AU-07, AU-10

- No circular imports across the entire 37-package codebase
- Dependencies point inward: cli/ -> business logic -> db/
- auth.py uses lazy import (`_agent_classes()`) to break the only potential cycle
- Cross-cutting files (defaults.py, fs.py, output.py) are stable leaf dependencies with high fan-in, low fan-out
- Intel and providers are textbook Clean Architecture: intel depends only on db/ and fs/ (inward), providers depend on nothing outside their package
- Provider abstraction (BaseProvider ABC) is the only ABC and it is properly used with DIP and factory pattern

**Extend to:** Document this architecture formally so new code maintains it. The dependency graph is the codebase's strongest structural asset.

---

## 2. Database Design and Migration System

**Found by:** AU-02, AU-04

- Three-DB architecture is well-designed: Project DB (local work), Coordinator DB (cross-project), Network DB (multi-machine) with clear lifecycle scope separation
- Migration system is production-quality: 13 versioned migrations, idempotent guards (IF NOT EXISTS, column-existence checks), per-migration transactions (BEGIN/COMMIT/ROLLBACK), version tracking, error propagation
- WAL mode + busy_timeout consistently applied on main connection paths
- Parameterized queries everywhere — zero SQL injection risk across entire codebase (even dynamic WHERE clauses use parameterized IN)
- Upsert patterns well-used: INSERT OR REPLACE, ON CONFLICT DO UPDATE for natural idempotency
- Schema uses appropriate constraints: PRIMARY KEY, AUTOINCREMENT, UNIQUE, FOREIGN KEY, NOT NULL, sensible defaults
- Network project_db.py LRU cache is well-engineered: max 10 connections, 5-min TTL, read-only, thread-safe

**Extend to:** Apply WAL pragma consistently to daemon connections. Add the `_connect()` centralized helper to preserve these patterns.

---

## 3. Agent-First CLI Design

**Found by:** AU-01, AU-00

- JSON-default output is correct for agent consumption — single funnel via output.py with JSON/human/compact modes from same data
- Non-interactive by design — zero prompts, zero confirmations (except api start getpass fallback)
- Deterministic output — same input = same JSON, no random elements
- _agent_option() helper standardizes --agent flag with heartbeat callback across 10+ modules
- Lazy imports in all CLI handlers prevent circular imports and speed startup
- Backwards-compatible aliases provide migration path without breaking existing scripts
- Rich help text with formatted sections, examples, and behavioral notes
- Auth checks at CLI boundary (require_class decorator) — fail fast before business logic

**Extend to:** Fix backlog_cmds.py to use the output funnel (the one module that doesn't follow the pattern).

---

## 4. Task Engine State Machine

**Found by:** AU-04

- YAML-driven flow definitions: new workflows added by writing YAML, not modifying Python
- Flow inheritance (`inherits: _base`) reduces duplication
- Skip chain resolution with cycle detection via `seen` set
- Gate checks are composable: file, DB, structural, task precondition gates
- Optimistic concurrency for task claiming: conditional UPDATE with WHERE status=? AND assigned_to IS NULL
- Transition audit trail: every status change logged to transition_log
- Graduated enforcement: update_task warns but allows (flexibility), complete_phase is strict (DAG-only), engine.apply_transition validates but doesn't write (pure function)
- Clean separation: 24 files with clear single responsibilities

**Extend to:** The YAML-driven approach is a model for other configuration-heavy areas (agent states, message types).

---

## 5. Daemon Resilience Architecture

**Found by:** AU-05

- Well-decomposed mixin architecture: 9 mixins with single-concern separation, informal interface contracts via typed stubs
- Correct concurrency model: single-threaded business logic with subprocess-based execution avoids lock complexity
- Robust resilience: 13 of 16 broad except blocks are intentional, logged, and correctly classified as non-critical
- Auto-respawn on context death (phoenix_down/generation loop) — sophisticated lifecycle feature
- Structured JSON logging via _log() — machine-parseable with timestamp, agent, level
- Exponential backoff with cap: configurable per-agent, alerts lead after 3 failures
- RollingBuffer bounds memory with deque-based eviction
- Standdown/wake lifecycle: stands down when no work, wakes on new work, decides resume vs fresh session

**Extend to:** The daemon's structured logging pattern (_log with JSON) should be the model for the codebase-wide logging strategy.

---

## 6. Provider Abstraction

**Found by:** AU-07, AU-05

- BaseProvider(ABC) with well-designed interface: 2 abstract methods, sensible defaults for optional methods, shared utility
- get_provider() factory + _REGISTRY dict is clean DIP
- All 4 providers fully interchangeable: config-driven selection without code changes
- Providers are fully self-contained: zero imports from minion.* namespace
- Adding a new provider requires only: new file in providers/, add to _REGISTRY dict

**Extend to:** This is the pattern to follow if other subsystems need pluggable implementations.

---

## 7. Filesystem-as-DB Naming

**Found by:** AU-00, AU-07, AU-08, AU-10

- Descriptive package names throughout: flow_gates_and_validation.py, path_resolution_and_slug.py, cli_provider_protocol.py
- `tree` output communicates the domain: "multi-agent coordination framework" is evident
- Backlog uses filesystem as source of truth: `.work/backlog/<type>/<slug>/` with DB as rebuildable index
- Prompt content separated from code: `capabilities/{name}/prompt.md`, `roles/{name}/prompt.md` — add a capability by creating a directory
- Mission templates as YAML data, not Python code
- PSEUDO comments preserved in router.py, discovery.py, project_db.py, db_schema.py — scaffold discipline where applied

**Extend to:** This naming discipline is well-maintained. Ensure new modules follow the same convention.

---

## 8. Test Quality (Where Tests Exist)

**Found by:** AU-09

- 100% pass rate, 3.95 seconds for 234 tests — no flaky or slow tests
- Behavioral testing throughout: return values, DB state, filesystem state checked. Zero mocks means no mock/production divergence
- Full DAG lifecycle coverage: test_dag_smoke walks open -> assigned -> in_progress -> qe -> fixed -> verified -> closed
- Strong backlog suite: 69 tests covering CRUD, promote, kill/defer, edge cases — model for other packages
- Descriptive test names: `test_<scenario>_<expected_result>` pattern consistently applied
- Clear AAA structure: Arrange-Act-Assert visible in all files
- Effective DB isolation: tmp_path for every test, no pollution between runs
- Contract validation tests: test_contracts.py validates JSON structure and invariants

**Extend to:** The backlog test suite (69 functions) is the quality bar. Apply similar coverage to auth, providers, network handlers (the critical untested areas).

---

## 9. Communication Model

**Found by:** AU-03

- WAL snapshot isolation awareness: check_inbox has explicit comments on read-before-write ordering
- Inbox discipline enforcement: send() blocks if sender has unread messages — mechanical enforcement of "read before write" protocol
- Three-tier routing with graceful degradation: local -> coordinator -> network -> offline queue
- Auto-CC to lead: automatic visibility without requiring senders to remember
- Atomic file writes via fs.atomic_write_file() — write to temp, then rename
- Task-protected pruning: agents with open work are protected regardless of staleness
- Broadcast deduplication: broadcast_reads table ensures exactly-once delivery per agent
- Clean transport separation: terminal.py, daemon.py, _tmux.py — adding a transport is a new file

**Extend to:** The inbox discipline and auto-CC patterns are unique strengths that should be preserved through any refactoring.

---

## 10. Auth and Security Model

**Found by:** AU-00, AU-06, AU-10

- Two-tier auth model is intentionally designed: CLI (class+scope, local trust) and network (bearer token, untrusted boundary)
- require_class/require_scope decorators enforce authorization at the CLI entry point, not deep in the stack
- TOOL_CATALOG maps 60+ commands to allowed class sets in one authoritative location
- 7 classes, 10 capabilities, scope-based narrowing — well-thought-out permission model
- Secrets in env vars only, no hardcoded tokens/passwords in source
- TLS default-on for network API, with fallback to HTTP requiring explicit opt-out
- Parameterized SQL everywhere — no SQL injection vectors despite lack of input validation

**Extend to:** Wire the already-scaffolded network/auth.py AuthMixin. The CLI auth pattern is solid — the network auth just needs integration.

---

## 11. Composition and Reuse Patterns

**Found by:** AU-08, AU-07

- Prompt builders compose from independent sub-loaders: _protocol, _rules, _boot, _inbox, _history
- Mission resolver uses clean greedy set-cover algorithm with deterministic tiebreaking
- Intel as pure functions: every module exports one function with dict return, no classes, no state
- Frontmatter parsing is defensive: never raises, validates types, returns defaults for missing fields
- Config dataclass sharing (AgentConfig, SwarmConfig as frozen dataclasses) — immutable after construction
- Clean separation: prompts/ and missions/ have zero cross-imports

**Extend to:** The "thin loader + content file" pattern in prompts/ is a model for any future template-heavy features.

---

## Summary: Codebase DNA

The minion-factory codebase has strong structural DNA:

1. **Architecture is sound** — dependency direction, bounded contexts, no circular imports
2. **Core abstractions are correct** — provider ABC, YAML-driven flows, filesystem-as-DB
3. **Where tested, tests are excellent** — behavioral, fast, descriptive, well-structured
4. **Resilience patterns exist** — daemon graceful degradation, three-tier routing, auto-respawn

The weaknesses are primarily **gaps** (missing tests, missing headers, missing validation) and **inconsistencies** (logging, error patterns, config access), not **architectural flaws**. The foundation is solid; the remediation is mostly filling in what's missing and standardizing what's inconsistent.
