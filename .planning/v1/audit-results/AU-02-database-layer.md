# AU-02 Database Layer Audit Results

**Auditor:** AU-02 (Database Layer Deep Dive)
**Date:** 2026-03-09
**Scope:** `src/minion/db/` (7 files), boundary checks on `tasks/db.py`, `network/project_db.py`, `network/db_schema.py`, `daemon/runner/_db.py`

---

## Schema Summary

### Project DB (`src/minion/db/schema.py` — 3 schema groups)

| # | Table | Columns | PK | Owner (Writer) |
|---|-------|---------|----|----|
| 1 | agents | 22+ cols (name, class, model, hp_*, transport, scope_mode, ...) | name TEXT | comms/register.py, daemon/runner/_db.py, daemon/watcher.py |
| 2 | messages | 7 cols (id, from_agent, to_agent, content_file, timestamp, read_flag, is_cc) | id AUTOINCREMENT | comms/send.py, comms/delivery.py |
| 3 | broadcast_reads | 2 cols (agent_name, message_id) | composite (agent_name, message_id) | comms/inbox.py, polling.py, daemon/watcher.py |
| 4 | battle_plan | 6 cols | id AUTOINCREMENT | warroom.py |
| 5 | raid_log | 5 cols | id AUTOINCREMENT | warroom.py |
| 6 | file_claims | 3 cols (file_path, agent_name, claimed_at) | file_path TEXT | filesafety.py |
| 7 | file_waitlist | 4 cols | id AUTOINCREMENT | filesafety.py |
| 8 | fenix_down_records | 6 cols | id AUTOINCREMENT | lifecycle.py |
| 9 | flags | 4 cols (key, value, set_by, set_at) | key TEXT | crew/lifecycle.py, comms/send.py |
| 10 | agent_retire | 3 cols | agent_name TEXT | crew/lifecycle.py |
| 11 | invocation_log | 13 cols | id AUTOINCREMENT | daemon/runner/_db.py |
| 12 | compaction_log | 10 cols | id AUTOINCREMENT | daemon/runner/_db.py |
| 13 | agent_interrupt | 3 cols | agent_name TEXT | crew/lifecycle.py |
| 14 | projects | 4 cols (id, description, created_at, status) | id TEXT | tasks/create_task.py, tasks/db.py |
| 15 | tasks | 18+ cols | id AUTOINCREMENT | tasks/create_task.py, tasks/db.py |
| 16 | requirements | 8 cols | id INTEGER | requirements/crud.py |
| 17 | schema_version | 3 cols | version INTEGER | db/migrations.py |

**Via migrations (v4-v13):**

| # | Table | Created In | Owner |
|---|-------|-----------|-------|
| 18 | transition_log | v4 | tasks/db.py, tasks/done.py |
| 19 | backlog | v8 | backlog/*.py |
| 20 | task_comments | v9 | tasks/comments.py |
| 21 | intel_docs | v11 | intel/add_doc.py, intel/reindex.py |
| 22 | intel_links | v11 | intel/add_doc.py, intel/reindex.py |

### Coordinator DB (`~/.minion/coordinator.db`)

| # | Table | Columns | PK | Owner |
|---|-------|---------|----|----|
| 1 | agents | 11 cols (name, agent_class, model, project_path, ...) | name TEXT | db/coordinator.py, comms/register.py, comms/routing.py |

### Network DB (per-server)

| # | Table | Columns | PK | Owner |
|---|-------|---------|----|----|
| 1 | agents | 22 cols (identity, capability, environment, trust, routing) | composite (machine_id, project_path, name) | network/handlers/core.py |
| 2 | messages | 6 cols | id AUTOINCREMENT | network/handlers (messages) |

---

## Filled Checklist

### CS Foundations — Data Architecture

| Rule | Status | Evidence |
|------|--------|----------|
| DATA-1 | **PARTIAL** | Three separate DBs (project, coordinator, network) with mostly clear ownership. However, the `agents` table in project DB has **multiple writers**: comms/register.py does INSERT, daemon/runner/_db.py writes pid/rss/session_id/invocation data, daemon/watcher.py writes HP token metrics, monitoring.py writes HP data, crew/spawn.py writes flags. This is pragmatic (different facets of the same agent row) but violates single-writer. All other tables have clear single-writer ownership. |
| DATA-2 | **YES** | Current-state snapshot model throughout. `agents` stores current state. `transition_log` (v4) provides an event log for task state changes — hybrid model appropriate for the use case. Audit columns present: `created_at` on most tables, `updated_at` on tasks/backlog/requirements/intel_docs. |
| DATA-3 | **YES** | SQLite is justified for a local-first CLI tool with 1-50 agents. Three separate DBs for three different lifecycle scopes (project, coordinator, network). JSON columns used for flexible sub-documents (capabilities, machine_specs in network schema; files, tags in project schema). No exotic storage needs. |
| DATA-4 | **YES** | Schema-on-write with explicit CREATE TABLE statements. 22+ tables across 3 DBs with typed columns, NOT NULL constraints, defaults, and UNIQUE constraints. JSON columns (files, tags, capabilities) provide schema-on-read flexibility where appropriate. |
| DATA-5 | **NO** | **No archival or deletion strategy.** Messages accumulate indefinitely — no TTL, no purge. The only deletion is: (a) stale agent pruning in coordinator.py (6-hour threshold, good), (b) agent deregistration cleans up claims/waitlist/agent row. No message archival. No transition_log rotation. No invocation_log cleanup. No backlog lifecycle past "closed" status. |
| DATA-6 | **YES** | Derived data computed on-read: `hp_summary()` computes HP percentage from raw token counts, `enrich_agent_row()` computes staleness from timestamps, `last_seen_mins_ago` computed at query time. No materialized views or precomputed aggregations stored. |

### CS Foundations — Consistency & State

| Rule | Status | Evidence |
|------|--------|----------|
| CONSIST-1 | **YES** | Strong consistency within each SQLite DB. Per-aggregate consistency across the three DBs (project, coordinator, network). No cross-DB transactions attempted. Coordinator updates are best-effort (wrapped in `except Exception: pass`), which is appropriate for a secondary index. |
| CONSIST-2 | **PARTIAL** | **Explicit transactions only in migrations** (`conn.execute("BEGIN")` / `conn.execute("COMMIT")` in `_run_migrations`). Zero uses of `with conn:` context manager anywhere. Most multi-step operations rely on SQLite's autocommit per statement + explicit `conn.commit()`. Two specific risks: (a) `tasks/db.py` `transition_task()` does UPDATE tasks + INSERT transition_log + commit — if the INSERT fails, the UPDATE is already applied. (b) `comms/register.py` does multiple DELETEs during deregistration without wrapping in a transaction. **However**, `_run_migrations` correctly uses BEGIN/COMMIT/ROLLBACK per migration, which is the highest-risk area. |
| CONSIST-3 | **YES** | WAL mode enabled on all connections (`PRAGMA journal_mode=WAL`). `PRAGMA busy_timeout=5000` on all connections. `threading.Lock` used in `network/project_db.py` for the connection cache. No version columns (optimistic concurrency not needed at this scale). The daemon's `DBMixin` opens a fresh connection per operation, avoiding lock contention. |
| CONSIST-4 | **PARTIAL** | Migrations: idempotent via `IF NOT EXISTS`, column-existence checks, and try/except for ALTER TABLE. Schema creation: all `CREATE TABLE IF NOT EXISTS`. Agent registration: `INSERT OR REPLACE` / `ON CONFLICT DO UPDATE` (idempotent). **But**: task creation (`INSERT INTO tasks`) is not idempotent — duplicate create would fail on autoincrement but isn't guarded. Message send is not idempotent — no dedup key. These are acceptable for a CLI tool where retries are manual. |
| CONSIST-5 | **YES** | Message ordering via AUTOINCREMENT id + timestamp column. Transition ordering via `created_at` + id in transition_log (`ORDER BY created_at, id`). Migration ordering via version number (sorted ascending). Task query ordering not enforced by default (caller specifies). |

### Clean Architecture (DB-applicable subset)

| Rule | Status | Evidence |
|------|--------|----------|
| CA-DEP-1 | **PARTIAL** | `db/connection.py` imports from `minion.defaults` (same layer, OK). `db/messages.py` imports from `minion.defaults` (OK) and lazily from `minion.auth` (higher layer — **violation**). `db/agents.py` lazily imports from `minion.auth` (higher layer — **violation**, but uses deferred import to avoid circular deps). `db/coordinator.py` imports only from `db/` siblings (OK). `db/schema.py` — zero imports (OK). `db/migrations.py` imports from `db/` sibling only (OK). **Two files violate the dependency rule by importing from auth (a policy module).** |
| CA-DEP-2 | **N/A** | No formal entity objects — data is `sqlite3.Row` objects and dicts. Row is stdlib, not a framework. |
| CA-BOUND-3 | **YES** | DB functions return simple structures: `sqlite3.Row` objects (dict-like), plain dicts via `dict(row)`, tuples, and primitive types (str, int, bool). No domain objects cross the boundary. `tasks/db.py` returns `dict` from all methods. |

### Pragmatic Programmer (DB-applicable subset)

| Rule | Status | Evidence |
|------|--------|----------|
| PP-DRY-1 | **NO** | `get_db()` is the canonical connection factory, but it is **widely bypassed**. Found **27 direct `sqlite3.connect()` calls** outside `db/connection.py`: daemon/runner/_db.py (10 calls), daemon/watcher.py (1), dashboard/loop.py (1), network/project_db.py (1), network/db_schema.py (3), network/server.py (1), network/discovery.py (1), network/fqn.py (1), backlog/close_item.py (1), comms/routing.py (1), comms/delivery.py (1). Each reimplements connection setup (timeout, busy_timeout) with slight variations. |
| PP-DRY-2 | **PARTIAL** | The daemon's `DBMixin` completely reimplements connection management (open-per-operation, manual close) rather than using `get_db()`. This is partly justified — the daemon runs in a subprocess and needs direct path control via `self.config.comms_db`. But the pattern (connect, set busy_timeout, execute, commit, close) is duplicated 10 times in `_db.py` alone. Network modules similarly reimplment their own connection patterns. |
| PP-ORTH-1 | **YES** | The `db/` package is well-decomposed into 7 files by concern: connection, schema, migrations, agents, coordinator, messages, timestamp/registry. Each file has a clear single purpose documented in its docstring. |
| PP-CRAFT-5 | **YES** | Table names reveal domain intent: `battle_plan`, `raid_log`, `fenix_down_records`, `file_claims`, `transition_log`, `intel_docs`. Function names are descriptive: `enrich_agent_row`, `staleness_check`, `touch_coordinator_activity`, `_prune_local_stale_agents`. Column names are clear: `hp_input_tokens`, `context_updated_at`, `autonomous_delegation`. |

### Implementation Coding Core (DB-applicable subset)

| Rule | Status | Evidence |
|------|--------|----------|
| IC-HDR-1 | **NO** | No formal PURPOSE header in mandated format. All 7 db/ files use module-level docstrings instead. Docstrings are informative (e.g., `connection.py`: "Database connection management — path resolution, WAL-mode connections") but don't follow the mandated template. **Systemic finding SF-01 applies.** |
| IC-HDR-2 | **NO** | No formal RESPONSIBILITIES header. Docstrings partially cover this. **Systemic finding SF-01 applies.** |
| IC-HDR-3 | **NO** | No formal NOT RESPONSIBLE FOR header. **Systemic finding SF-01 applies.** |
| IC-HDR-4 | **NO** | No formal DEPENDENCIES header. **Systemic finding SF-01 applies.** Exception: `network/project_db.py` has a full formal header with Purpose, Rationale, Responsibility, Organization, Thread safety, Implementation order. |
| IC-HDR-5 | **YES** | Existing docstrings are persistent — no evidence of removal. PSEUDO comments preserved in `network/project_db.py` and `network/db_schema.py`. |

---

## Findings

| # | Rule | Severity | Affected Files | Description | Remediation |
|---|------|----------|----------------|-------------|-------------|
| F-01 | PP-DRY-1 | **Major** | 10+ files across daemon, network, backlog, comms, dashboard | **27 direct `sqlite3.connect()` calls bypass `get_db()`**, each reimplementing connection setup with slight variations (timeout=5 vs timeout=2, missing WAL pragma, missing foreign_keys pragma, inconsistent row_factory). The daemon has justified reasons (subprocess path control) but the pattern should be standardized. | Extract a `_connect(db_path, readonly=False)` helper in `db/connection.py` that encapsulates WAL, busy_timeout, row_factory, foreign_keys. All modules should call this instead of raw `sqlite3.connect()`. Daemon can use a path-parameterized variant. |
| F-02 | CONSIST-2 | **Moderate** | tasks/db.py, comms/register.py, crew/spawn.py | **Multi-step mutations lack explicit transaction boundaries.** `TaskDB.transition_task()` does UPDATE + INSERT + commit — if INSERT fails, UPDATE is already applied (SQLite autocommit). `comms/register.py` deregistration does 4+ DELETEs without transaction. `crew/spawn.py` does DELETE flags + DELETE agent_retire in sequence. | Wrap multi-step mutations in `conn.execute("BEGIN") ... conn.execute("COMMIT")` with ROLLBACK on exception, or use `with conn:` context manager. |
| F-03 | DATA-5 | **Moderate** | All tables | **No data lifecycle management.** Messages, transition_log, invocation_log, compaction_log, and raid_log grow unbounded. No TTL, no purge, no archival. Over weeks of active use, the DB will grow significantly. The only cleanup is stale agent pruning (coordinator.py, 6-hour threshold). | Add a `db/cleanup.py` module with configurable retention policies: e.g., purge messages older than 7 days, archive transition_log older than 30 days, cap invocation_log to last 1000 entries. Run cleanup in daemon's periodic maintenance cycle. |
| F-04 | CA-DEP-1 | **Minor** | db/agents.py, db/messages.py | **db/ imports from minion.auth (a policy/higher layer).** `agents.py` imports `CLASS_STALENESS_SECONDS` from auth; `messages.py` imports `TRIGGER_WORDS` from auth. Both use deferred imports to avoid circular deps, which is a code smell indicating the dependency is inverted. | Move `CLASS_STALENESS_SECONDS` and `TRIGGER_WORDS` to a shared constants module (e.g., `minion/constants.py` or `minion/auth_constants.py`) that both `auth` and `db` can import from without violating the dependency rule. |
| F-05 | PP-DRY-2 | **Moderate** | daemon/runner/_db.py | **10 repetitions of connect-execute-commit-close pattern.** Every method in `DBMixin` opens a fresh connection, sets busy_timeout, executes SQL, commits, and closes — with identical try/except/warning boilerplate. | Extract a `_with_db(self, fn)` helper that handles connection lifecycle, or use a context manager. Alternatively, maintain a single connection per runner instance with reconnect-on-error. |
| F-06 | CONSIST-3 | **Minor** | daemon/runner/_db.py | **Inconsistent WAL mode.** Daemon `DBMixin` connections do NOT set `PRAGMA journal_mode=WAL` — they only set `busy_timeout`. The main `get_db()` sets WAL, but daemon bypasses `get_db()`. WAL mode is set per-database (persists), so this works if `init_db()` ran first, but if the daemon accesses a DB that was never initialized via `get_db()`, it runs without WAL. | Add `PRAGMA journal_mode=WAL` to the daemon's connection helper, or centralize all connection creation through `db/connection.py`. |
| F-07 | CONSIST-3 | **Minor** | daemon/runner/_db.py | **Inconsistent row_factory.** Only `_fetch_fenix_records` (1 of 10 methods) sets `conn.row_factory = sqlite3.Row`. All other methods access rows by index (`row[0]`) or don't need it. This works but creates a fragile pattern — if a query changes column order, index-based access breaks silently. | Set `row_factory = sqlite3.Row` on all connections for consistency, or document explicitly why index access is used. |
| F-08 | DATA-1 | **Minor** | agents table | **agents table has 5+ writers across packages.** comms/register.py (INSERT/UPDATE full row), daemon/runner/_db.py (UPDATE pid, rss, session_id, invocations), daemon/watcher.py (UPDATE HP tokens), monitoring.py (UPDATE HP), crew/spawn.py (UPDATE flags). Each writes different columns, so there's no actual conflict, but the table lacks clear column ownership documentation. | Document column ownership in schema.py comments: e.g., "hp_* columns owned by daemon/watcher, pid/rss by daemon/runner, status/context by comms". |
| F-09 | IC-HDR-1-4 | **Info** | All 7 db/ files | **No formal IC headers (systemic).** All files use docstrings. `network/project_db.py` and `network/db_schema.py` are exceptions that DO have formal headers — showing the pattern is known but not applied to the core db/ package. Refer to systemic finding SF-01 from AU-00. | Apply formal headers to db/ files. Low priority — docstrings are adequate. |

---

## Strengths

1. **Three-DB architecture is well-designed.** Project DB (local work state), Coordinator DB (cross-project registry), Network DB (multi-machine discovery). Clear separation of lifecycle and ownership scope. Each DB has its own connection factory (`get_db()`, `get_coordinator_db()`, network `init_db()`).

2. **Migration system is production-quality.** 13 versioned migrations with: idempotency guards (IF NOT EXISTS, column-existence checks, try/except for ALTER TABLE), per-migration transactions (BEGIN/COMMIT/ROLLBACK), version tracking via schema_version table, ordered application, and error propagation that halts on failure. The `_migrate()` function handles legacy column additions separately from versioned migrations — belt and suspenders.

3. **WAL mode + busy_timeout consistently applied.** `get_db()` and `get_coordinator_db()` both set `PRAGMA journal_mode=WAL` and `PRAGMA busy_timeout=5000`. Foreign keys enabled on project DB (`PRAGMA foreign_keys=ON`). This prevents most locking issues at the current scale.

4. **Connection lifecycle is clean in db/ package.** `get_db()` creates per-operation connections (no pooling). `init_db()` opens, creates tables, migrates, closes. `register_agent_db()` uses try/finally for close. The `network/project_db.py` module goes further with a proper LRU cache (max 10 connections, 5-min TTL, thread-safe) for read-only connections — well-engineered.

5. **Parameterized queries everywhere.** All SQL uses `?` placeholders — zero string formatting with user data. Even dynamically-built WHERE clauses in `tasks/db.py` use parameterized queries. The one exception is `f"DELETE FROM agents WHERE name IN ({','.join('?' * len(names))})"` which safely builds a parameterized IN clause.

6. **Upsert patterns well-used.** `INSERT OR REPLACE`, `INSERT OR IGNORE`, and `ON CONFLICT DO UPDATE` used appropriately: agent registration (upsert), broadcast_reads (dedup), flags (last-writer-wins), coordinator activity (heartbeat). These provide natural idempotency where it matters most.

7. **Schema uses appropriate constraints.** PRIMARY KEY on all tables, AUTOINCREMENT for append-only logs, UNIQUE constraints on file_claims and waitlist, FOREIGN KEY references (requirements → tasks, intel_links → intel_docs, task_comments → tasks), NOT NULL on required fields, sensible defaults.

8. **Lazy path resolution prevents import-time side effects.** `_db_path` is `None` until first `_get_db_path()` call, which resolves from env vars and cwd at runtime. `reset_db_path()` allows re-resolution (useful for tests and cross-project commands). Module-level `__getattr__` provides `DB_PATH` and `RUNTIME_DIR` lazily.

9. **TaskDB class provides a clean repository pattern** for tasks/projects/transitions with consistent dict return types, parameterized queries, and DAG validation integrated into transitions. This is the closest thing to a repository abstraction in the codebase.

10. **Coordinator auto-pruning is well-implemented.** 6-hour stale threshold, checked at most once per 10 minutes (rate-limited via monotonic clock), skips agents with active tasks, removes both DB rows and filesystem roster files. Best-effort (never raises) — appropriate for background maintenance.

---

## Boundary Check: B-06 (Task Engine DB)

**File:** `src/minion/tasks/db.py`

| Check | Status | Evidence |
|-------|--------|----------|
| Imports from db/ | **YES** | `from minion.db import get_db` — uses canonical factory |
| Same connection pattern | **PARTIAL** | Uses `get_db()` (good) but holds the connection for the lifetime of the `TaskDB` instance (`self._conn = get_db()` in `__init__`). This means a long-lived TaskDB instance holds an open connection indefinitely. No `close()` method. |
| Same Row factory | **YES** | Inherits Row factory from `get_db()`. Returns `dict(row)` consistently. |
| Parameterized queries | **YES** | All queries use `?` placeholders. Dynamic WHERE built safely. |
| Transaction safety | **NO** | `transition_task()` and `complete()` both do UPDATE + INSERT + commit without explicit transaction boundary. If the transition_log INSERT fails after the status UPDATE succeeds, the DB is in an inconsistent state (status changed but no audit record). |
| Pattern divergence | **MINOR** | `TaskDB` is a class-based repository pattern (unique in the codebase). All other DB access is function-based. This is a TaskDB-inherited pattern (minion-tasks library), not a db/ pattern. Acceptable. |

**Verdict:** TaskDB follows db/ patterns well. The connection-lifetime issue is the main concern — if TaskDB is used in a long-running process, the connection stays open. In CLI context (short-lived), this is fine.

---

## Boundary Check: Network DB Modules

### `network/project_db.py` — LRU Connection Cache

| Check | Status | Evidence |
|-------|--------|----------|
| Connection pattern | **DIVERGENT** (justified) | Does NOT use `get_db()`. Opens read-only connections (`?mode=ro`) with LRU caching (max 10, 5-min TTL, thread-safe). This is intentional — network server needs to read multiple project DBs concurrently without write access. |
| Row factory | **YES** | Sets `conn.row_factory = sqlite3.Row` on all cached connections. |
| WAL/busy_timeout | **PARTIAL** | Sets `busy_timeout=3000` (vs 5000 in get_db()) but does NOT explicitly set WAL mode. Read-only connections benefit from WAL but don't need to set it (WAL persists per-database). Timeout difference is intentional (lower for read-only). |
| Formal headers | **YES** | Has full PURPOSE/Rationale/Responsibility/Organization/Thread safety headers. Best-documented file in the DB layer. |

### `network/db_schema.py` — Network Schema & Migration

| Check | Status | Evidence |
|-------|--------|----------|
| Connection pattern | **DIVERGENT** (justified) | Manages its own separate DB schema (network coordinator, not project DB). Has `init_db(db_path)` and `migrate_db(db_path)` taking explicit paths. Sets WAL + busy_timeout. |
| Migration quality | **YES** | Idempotent: CREATE TABLE IF NOT EXISTS, try/except for ALTER TABLE ADD COLUMN, `_has_composite_pk()` check before PK migration, INSERT OR IGNORE during copy. |
| PSEUDO comments | **YES** | Extensive PSEUDO comments showing planned logic before implementation. |

### `daemon/runner/_db.py` — Daemon DB Operations

| Check | Status | Evidence |
|-------|--------|----------|
| Connection pattern | **DIVERGENT** | Does NOT use `get_db()`. Opens fresh `sqlite3.connect(str(self.config.comms_db), timeout=5)` per operation (10 times). Justified by subprocess isolation — daemon runs in separate process with explicit DB path from config. |
| Row factory | **INCONSISTENT** | Only 1 of 10 methods sets `row_factory = sqlite3.Row`. Others use tuple-index access. |
| WAL mode | **NOT SET** | No `PRAGMA journal_mode=WAL` on daemon connections. Relies on WAL being set by prior `init_db()` call (WAL persists). |
| Transaction safety | **NO EXPLICIT** | Each method does single-statement-then-commit. Multi-step operations (e.g., `_check_interrupt`: SELECT + DELETE + commit) lack explicit transaction boundaries. |
| Error handling | **GOOD** | Every method wrapped in try/except with warning log. Daemon DB ops are best-effort — appropriate for non-critical observability data. |

---

## Summary Statistics

| Category | YES/PASS | NO/FAIL | PARTIAL | N/A |
|----------|----------|---------|---------|-----|
| CS-DATA (6 rules) | 4 | 1 | 1 | 0 |
| CS-CONSIST (5 rules) | 3 | 0 | 2 | 0 |
| CA (3 rules) | 1 | 0 | 1 | 1 |
| PP (4 rules) | 2 | 1 | 1 | 0 |
| IC-HDR (5 rules) | 1 | 4 | 0 | 0 |
| **Total (23 rules)** | **11** | **6** | **5** | **1** |

**Findings:** 9 total (1 Major, 4 Moderate, 3 Minor, 1 Info)
**Strengths:** 10 identified
