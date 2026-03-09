# CS Foundations Checklist — minion-factory Codebase Audit

Evaluated against existing codebase. This is both the Stage 4 gate AND part of the audit (since we are auditing an existing system, not planning a new one).

Evidence sources: research findings, codebase-structure.md, test-coverage.md, cli-and-api-interfaces.md, cross-cutting-concerns.md, direct file survey.

---

## Separation of Concerns

### SEP-1: Read path and write path identified — same model or separate (CQRS)?

**YES** — Same model (no CQRS). Read and write paths use the same SQLite tables and inline SQL. Queries and mutations share get_db() connections. Appropriate for the scale (local CLI tool, not distributed). Example: tasks/query_task.py (reads) and tasks/create_task.py (writes) both use tasks/db.py with same Row objects.

### SEP-2: Command/query split — do operations that change state return data?

**YES (partial)** — CLI commands that mutate generally return the created/modified object as JSON (e.g., `minion task create` returns the new task). This is a pragmatic choice for agent consumers who need the created resource immediately. Not a strict CQS violation — the mutation side-effect is intentional and documented.

### SEP-3: Layers identified — what is policy, what is detail, what is glue?

**YES** — Clear layering observed:
- **Policy:** tasks/ (flow gates, DAG, validation), auth.py (class/scope enforcement), daemon/contracts.py
- **Detail:** db/ (SQLite), network/ (HTTP), providers/ (Claude/Codex/Gemini/OpenCode adapters)
- **Glue:** cli/ (Click commands → business logic), crew/ (orchestration), comms/ (routing)

### SEP-4: Bounded contexts identified — where does one domain end and another begin?

**YES** — Package boundaries serve as bounded contexts. 27 packages, each with clear responsibility. Key boundaries: tasks (work items), comms (messaging), crew (agent lifecycle), intel (knowledge), backlog (prioritization). No circular imports (auth→tasks uses lazy import to break the one potential cycle).

### SEP-5: Public API surface vs internal API — what crosses the boundary?

**YES (partial)** — Two public surfaces:
- CLI (`minion` command) — well-defined, 18 command modules
- Network API (HTTP server on port 8377) — 15+ endpoints

Internal APIs are package-level imports. `__init__.py` files exist but not all explicitly control exports. Some packages expose implementation details (e.g., tasks/db.py is imported by other packages).

---

## Data Architecture

### DATA-1: Data ownership — which component owns which data (single writer)?

**YES** — Clear ownership:
- **db/ package** owns schema and migrations (14 tables, v1-v13)
- **tasks/** owns task state (creates, updates, transitions via gates)
- **comms/** owns message routing
- **intel/** owns document registry
- **backlog/** owns backlog items
- **network/project_db.py** owns network-level aggregation

Single-writer pattern mostly followed. Exception: daemon/config.py re-implements YAML parsing that crew/config.py owns.

### DATA-2: State model — current-state snapshot, event log, or hybrid?

**YES** — Current-state snapshot. SQLite tables store latest state. No event sourcing, no audit log of state transitions. Task flow has a state machine (flow_gates_and_validation.py) but transitions overwrite current state, they don't append to a log.

### DATA-3: Storage choice justified — relational, document, key-value, graph, file?

**YES** — SQLite (relational) for structured data. Filesystem for documents (intel docs, mission templates, prompt files). Justified: local-first tool, no network DB needed, WAL mode handles concurrent reads. Three DB files (project, coordinator, network) partition by scope.

### DATA-4: Schema strategy — schema-on-write (strict) or schema-on-read (flexible)?

**YES** — Schema-on-write. db/schema.py defines 14 tables with explicit CREATE TABLE statements. Migrations (v1-v13) alter schema incrementally. JSON columns used for flexible sub-documents (e.g., task metadata) — hybrid approach.

### DATA-5: Data lifecycle — creation, mutation rules, archival, deletion?

**YES (partial)** — Creation and mutation well-defined (task create → flow gates → done). No archival strategy. No explicit deletion/cleanup of old tasks, messages, or agent records. No TTL on messages in inbox.

### DATA-6: Derived data identified — what is computed from other data vs stored directly?

**YES** — Derived data includes: task rollups (tasks/rollup.py), war plans (intel/war_plan.py), dashboard queries (dashboard/queries.py), network overview/alerts endpoints. All computed on-read, not pre-materialized. Appropriate for scale.

---

## Communication & Integration

### COMM-1: Communication style — sync (request/response) or async (events/queues)?

**YES** — Primarily sync (request/response). CLI invokes functions directly. Network API is HTTP request/response. Daemon polling is sync (poll, sleep, poll). One async pattern: daemon watcher uses filesystem events. No message queues.

### COMM-2: Integration points — what external systems, what contracts, what failure modes?

**YES** — External integrations:
- **Provider CLIs** (claude, codex, gemini, opencode) — subprocess calls, failure = process exit code
- **tmux** — crew/spawn.py uses tmux for agent sessions, failure = subprocess error
- **Network peers** — network/discovery.py, client.py for multi-host, failure = connection error/timeout
- **Filesystem** — extensive use for docs, configs, prompts

Contracts are informal (no schema validation on provider responses). Failure modes handled per-call, no centralized strategy.

### COMM-3: Event taxonomy — if events exist, named and versioned?

**YES (partial)** — Daemon has trigger events (daemon/triggers.py) but they are function calls, not formal named/versioned events. Task flow states serve as implicit events (OPEN→IN_PROGRESS→DONE) but are state machine transitions, not published events. No event bus, no event versioning.

### COMM-4: API style chosen — REST, RPC, GraphQL, message-passing, CLI?

**YES** — Two API styles:
- **CLI**: Click-based command hierarchy, noun-verb pattern (`minion agent register`), JSON output default
- **Network API**: REST-like HTTP with custom router, {param} path matching, JSON responses

### COMM-5: Serialization format — JSON, protobuf, msgpack, plain text?

**YES** — JSON everywhere. CLI output is JSON default. Network API request/response is JSON. Config files are YAML. Prompts are markdown. No binary serialization.

---

## Consistency & State

### CONSIST-1: Consistency model — strong, eventual, or per-aggregate?

**YES** — Strong consistency within each SQLite database (ACID transactions). Per-aggregate across the three databases (project DB, coordinator DB, network DB are independent — no cross-DB transactions). Network peers have eventual consistency (polling-based sync).

### CONSIST-2: Transaction boundaries — what must succeed or fail atomically?

**YES (partial)** — Migrations are transactional (each migration in a transaction). Some business operations lack explicit transactions: task creation with multiple inserts, agent registration with comms registration. get_db() returns per-operation connections but callers don't always use `with conn:` for transactions.

### CONSIST-3: Concurrency strategy — locks, optimistic concurrency, actors, channels, none?

**YES** — WAL mode for SQLite read concurrency. Network server uses threading.Lock for write serialization. Daemon runner uses threading for background tasks. No optimistic concurrency (no version columns). No actors or channels. Adequate for scale but Lock granularity is coarse.

### CONSIST-4: Idempotency — which operations must be safely retriable?

**NO** — Not explicitly addressed. Migrations have IF NOT EXISTS (idempotent). But core operations (task create, comms send, agent register) are not explicitly idempotent. Agent register checks for duplicates but send does not. Daemon poll operations are implicitly idempotent (re-reading inbox is safe).

### CONSIST-5: Ordering guarantees — does message/event order matter? How enforced?

**YES (partial)** — Message ordering matters for comms (inbox). Enforced by SQLite rowid/timestamp ordering. Task flow ordering enforced by gate validation (can't skip states). No explicit sequence numbers on messages.

---

## Scale & Performance

### SCALE-1: Expected load — orders of magnitude (10 users? 10K? 10M?)

**YES** — Designed for 1-50 agents on a single host or small cluster. CLI is single-user. Network API handles a handful of concurrent agents. Not designed for high scale — appropriate for the use case.

### SCALE-2: Hot path identified — what runs most frequently, what must be fast?

**YES (implicit)** — Hot paths: daemon polling loop (every few seconds), CLI command invocations, task status queries. Polling is the most frequent — poll inbox, check tasks, heartbeat. All are simple SQLite reads (fast at this scale).

### SCALE-3: Caching strategy — what is cached, where, invalidation policy?

**YES** — Minimal caching. No explicit cache layer. SQLite page cache provides implicit caching. Provider registry is an in-memory dict (loaded once). No invalidation needed at current scale.

### SCALE-4: Algorithmic complexity — Big-O of critical paths acknowledged?

**NO** — Not documented. Most operations are O(1) or O(n) where n is small (number of tasks, agents). DAG operations in tasks/dag.py may have higher complexity but not analyzed. No Big-O annotations in code.

### SCALE-5: Resource bounds — memory, disk, network, connection pool limits?

**NO** — Not explicitly bounded. No connection pooling (per-operation connections). No disk quota for SQLite growth. No memory limits on daemon. File reads in intel/read_doc.py don't limit file size. At current scale these are non-issues, but undocumented.

---

## Security Boundaries

### SEC-1: Trust boundaries — where does trusted meet untrusted?

**YES** — Two trust boundaries:
- **CLI**: Trusted (local user with filesystem access). Class-based authorization gates operations.
- **Network API**: Untrusted (remote callers). Bearer token required (MINION_CLUSTER_TOKEN). Trust boundary is at HTTP handler level.

### SEC-2: Authentication — who is the caller, how verified?

**YES** — Two auth mechanisms:
- **CLI**: MINION_CLASS env var + MINION_AGENT_NAME. No cryptographic verification (trusted local context).
- **Network**: Bearer token comparison. No token = all requests pass (dev mode, documented).

### SEC-3: Authorization — what can the caller do, how enforced?

**YES** — CLI: require_class and require_scope decorators (auth.py). Five classes (coder, builder, recon, auditor, lead) with scope-based access control. Network: currently binary (has token or not) — no per-endpoint authorization.

### SEC-4: Secrets management — where stored, how accessed, how rotated?

**YES (partial)** — Secrets in environment variables (MINION_CLUSTER_TOKEN). No secrets in code or config files. No rotation mechanism. No secrets vault integration. Adequate for local/dev use.

### SEC-5: Input validation — where does untrusted data enter, how sanitized?

**NO** — Network API does manual body.get() with no validation. No input length limits. No sanitization of user-provided strings before SQL (parameterized queries protect against injection, but no semantic validation). CLI input validated only by Click type annotations.

---

## Error & Failure Modes

### ERR-1: Failure taxonomy — what kinds of failures can occur (network, data, logic)?

**NO** — No formal failure taxonomy. Two competing error patterns:
1. Dict-return `{"error": "..."}` for CLI/tasks — output.py detects "error" key → sys.exit(1)
2. Raise stdlib exceptions (ValueError, FileNotFoundError, RuntimeError) for config/loaders

No custom exception hierarchy. No categorization of transient vs permanent failures.

### ERR-2: Retry strategy — what is retried, what is not, backoff policy?

**NO** — No formal retry strategy. Daemon polling loop retries implicitly (poll again on next cycle). Network client has no retry/backoff. Provider subprocess calls have no retry. Some broad `except Exception: pass` in daemon (catch-all resilience).

### ERR-3: Partial failure — what happens when one component fails but others succeed?

**YES (partial)** — Daemon is designed for resilience (broad except blocks, continue running). CLI fails fast (sys.exit(1) on any error). Network API returns error JSON but continues serving. No saga/compensation patterns. No partial rollback.

### ERR-4: Degradation strategy — graceful degradation or fail-fast?

**YES** — Mixed by design:
- **CLI**: Fail-fast (appropriate — user sees error immediately)
- **Daemon**: Graceful degradation (broad except, log and continue — appropriate for long-running)
- **Network API**: Fail-fast per request, graceful for server lifecycle

### ERR-5: Observability — how are failures detected (logs, metrics, alerts)?

**NO** — Weakest area. Three logging patterns (logging.getLogger: 3 files, print: 23 files, click.echo: 9 files). No metrics. Network server has one structured JSON log line (server.py log_message). Daemon has monitoring.py but it's a basic status check, not observability. No alerting beyond daemon/triggers.py threshold checks.

---

## Summary

| Section | YES | NO | N/A | Partial |
|---------|-----|-----|-----|---------|
| SEP (5) | 4 | 0 | 0 | 1 (SEP-5) |
| DATA (6) | 5 | 0 | 0 | 1 (DATA-5) |
| COMM (5) | 4 | 0 | 0 | 1 (COMM-3) |
| CONSIST (5) | 2 | 1 | 0 | 2 (CONSIST-2, CONSIST-5) |
| SCALE (5) | 2 | 2 | 0 | 1 (implicit SCALE-2) |
| SEC (5) | 3 | 1 | 0 | 1 (SEC-4) |
| ERR (5) | 1 | 3 | 0 | 1 (ERR-3) |
| **Total (37)** | **21** | **7** | **0** | **7 (counted as partial YES)** |

## NO Items Requiring Resolution

| Rule | Finding | Severity | Affected Domains |
|------|---------|----------|------------------|
| CONSIST-4 | No explicit idempotency design | Minor | D3, D4, D6 |
| SCALE-4 | No Big-O documentation | Minor | D4, D6 |
| SCALE-5 | No resource bounds documented | Minor | D6, D8 |
| SEC-5 | No network input validation | Major | D7 |
| ERR-1 | No failure taxonomy, two competing patterns | Major | All |
| ERR-2 | No retry strategy | Minor | D6, D7 |
| ERR-5 | No observability strategy, 3 logging patterns | Critical | All |

These NOs feed directly into the audit deep dives. ERR-5 (observability/logging) is the most critical finding — it affects every domain and has no single owner.
