# Raw Snapshot — v2

Source: REQUIREMENTS.md (system founding), v1 audit findings, remaining backlog (73 items)

v2 is a remediation iteration. The system exists and works. v1 audited it against 218 rules
across 8 skill checklists. 62 findings were produced, 54 backlog items created from findings,
plus 45 operational items discovered during use. 50 tasks were completed. 73 backlog items remain.

## Raw Input 1: System Identity (from REQUIREMENTS.md)

Minion-factory is a unified multi-agent coordination framework. RPG raid party metaphor over SQLite.
Merged from three repos: minion-commsv2 (CLI, DB, messaging), minion-swarm (daemon, providers),
minion-tasks (DAG task flows). Single installable Python package `minion`.

Primary interface: CLI consumed by AI agents.
Secondary interface: Network API server (http.server, not FastAPI).
Data store: SQLite with WAL mode, .work/ directory per project.

## Raw Input 2: v1 Audit Upstream Feedback

See .planning/v1/upstream-feedback.md for full details. Key findings:
- UF-003: Halt detection silently broken (FIXED in v1)
- UF-004: Network API security gaps (FIXED in v1)
- UF-005: 12 systemic findings affect entire codebase (PARTIALLY FIXED — logging, errors, headers done)
- UF-007: Strengths are architectural, weaknesses are gaps and inconsistencies

## Raw Input 3: Remaining Backlog (73 items)

### Bugs (10)
1. DAG stages qe/verify can be self-closed by implementer — no mechanical enforcement
2. Global comms send DB insert fails when target project missing messages table
3. Poll command should walk up to find minion.db
4. Poll should register/heartbeat agent in global coordinator
5. Stale status missing from TERMINAL_STATUSES causing parent rollup blocks
6. Terminal agents don't deterministically poll after completing work
7. Test promote crew display
8. Backlog lineage missing task linkage for recently promoted items
9. Backlog promote accepts null promoted_to
10. Backlog operations have no auth check via -C flag

### Debt (22)
1. Daemon/crew logs unstructured prose, not JSON lines
2. No assumption documentation in key files
3. No data lifecycle management — messages/logs grow forever
4. Zero contracts or assertions in cross-cutting code
5. 103 bare except Exception blocks across 43 files
6. No Big-O documentation on hot paths
7. No message type taxonomy — all messages untyped strings
8. No conftest.py — fixture duplication ~150 lines
9. Unbounded stream.jsonl log files
10. No pytest markers for test categorization
11. No formal state machines for daemon/agent lifecycle
12. Zero tests for missions package
13. No pattern registry documenting conventions
14. Network API has no CLI exercising all endpoints
15. No reference integrity tests for CLI commands
16. UI server.js bootstrap creates wrong default DB path
17. No reference-integrity tests for route-to-handler (residual)
18. No verification artifacts per stage (residual)
19. f-001 residual: daemon/crew logs still prose
20. f-002 residual: some packages may still lack tests
21. f-003-sys residual: some files may still lack headers
22. f-015 residual: network handler error paths

### Ideas (14)
1. Agent context refresh — mid-session state injection
2. Auth scope-based permission narrowing for lead characters
3. DAG enforcement — mechanically block code commits without scaffolding
4. Dashboard sys-lead operational views
5. Fuzzy matching for CLI commands
6. Cycle detection at flow YAML load time
7. Shell completions for CLI
8. Error messages with remediation hints
9. Network API on-demand agent spawning and auto-teardown
10. New agent class: coordinator (system-wide lead)
11. All project leads report to sys-lead via global comms
12. Define purpose and scope of dashboard GUI
13. Cold-start auto-generate operational state
14. Crew YAML sys-lead character definition (residual)

### Requests (7)
1. CLI parity with network API — ~10 missing commands
2. Cross-project lead at parent dir with aggregated polling
3. Network API agent presence and availability
4. Network API agent registry schema for cross-machine delegation
5. Network API composite agent key host/project/name
6. Network API sys-lead review — 6 gaps
7. Research prompt assembly strategy for role/character/scope

### Smells (20)
1. Config cascade precedence inconsistent — -C mutates env vars
2. 5 network env vars bypass defaults.py
3. Bidirectional coupling comms <-> crew
4. Verb vocabulary inconsistencies in CLI
5. Exit code inconsistency across CLI commands
6. _resolve_or_404 duplicated across network handlers
7. _append_error_log duplicated between codex/gemini
8. Role prompt self-service block duplicated 6 times
9. db/ imports from auth (dependency layer violation)
10. DBMixin connect-execute-commit-close repeated 10 times
11. CLI options lack short flags (~244 of 250)
12. Top-level command leaks (deregister, rename, etc.)
13. Daemon WAL and row_factory inconsistency
14. Task files import private _tmux module
15. Bare except in intel auto-link
16. Provider error classifiers share structural pattern
17. Scaling endpoints unreachable in network API
18. Server suppresses HTTP logs entirely
19. TaskDB post-close calls raise AttributeError
20. Generic file names violate filesystem-as-db (residual)
