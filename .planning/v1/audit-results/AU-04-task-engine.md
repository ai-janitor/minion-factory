# AU-04 Task Engine Audit Results

**Auditor:** AU-04 (Task Engine Deep Dive)
**Date:** 2026-03-09
**Scope:** `src/minion/tasks/` — 24 Python files, ~2800 lines
**Skills:** CS Foundations (CONSIST, ERR, DATA subset), Clean Architecture (subset), Pragmatic Programmer (subset), Implementation Coding Core (subset)

---

## Task State Machine

### States

Task states are defined in YAML flow files (e.g., `bugfix.yaml`, `feature.yaml`), loaded by `loader.py` into `TaskFlow` dataclass objects. States are NOT enumerated as Python constants — they are strings loaded from YAML at runtime.

Common states across flows: `open`, `assigned`, `in_progress`, `fixed`, `verified`, `closed`, `blocked`, `abandoned`, `stale`, `obsolete`.

Terminal states are marked with `terminal: true` in YAML. The code checks terminality via `flow.is_terminal(status)`.

### Transitions

Valid transitions are determined by `TaskFlow.valid_transitions()` which unions:
- `stage.next` (happy path, resolved through skip chains)
- `stage.fail` (failure path)
- `stage.alt_next` (alternative path)
- `flow.dead_ends` (globally available dead-end states like `abandoned`)

### Validation

- **Before execution:** `update_task()` validates transitions but **warns, does not block**. Invalid transitions are logged with a `transition_warning` but still applied. This is a design choice (philosophy point 9: "Low friction first, harden gradually").
- **`complete_phase()`** is strict — uses `flow.next_status()` to determine the only valid next state based on passed/failed. No manual override possible.
- **`engine.apply_transition()`** validates against `valid_transitions()` set and rejects invalid targets. Does NOT write to DB — caller handles the UPDATE.
- **Invalid transition attempt:** Returns error dict `{"error": "..."}` — does not raise exceptions.
- **`close_task()`** checks terminal state, result file existence, and agent class before allowing close.

### Skip Chain Resolution

`TaskFlow._resolve_skip()` follows skip chains with cycle detection via `seen` set. If skip chain leads to None or loops, returns None.

---

## DAG Analysis

### Structure

`dag.py` defines `Stage` (dataclass) and `TaskFlow` (dataclass with methods). `TaskFlow.stages` is `dict[str, Stage]` — an ordered dict of stage definitions.

The DAG is a **linear chain with branches** (next/fail/alt_next), not a general directed graph. Each stage has at most one `next`, one `fail`, and one `alt_next` pointer.

### Cycle Detection

- `_resolve_skip()`: Has cycle detection via `seen` set — **PASS**.
- `render_dag()`: Has cycle detection via `visited` set — **PASS**.
- `past_gate()`: Has cycle detection via `visited` set — **PASS**.
- `valid_transitions()`: No cycle detection needed — returns immediate neighbors only.

**No general cycle detection at load time.** If a YAML file defines a cycle (A.next = B, B.next = A), the system will not detect it at validation time. `_validate()` only checks that referenced stages exist, not that the graph is acyclic.

### Big-O Complexity

| Operation | Complexity | Notes |
|-----------|------------|-------|
| `next_status()` | O(S) worst case | S = skip chain length, bounded by stage count |
| `valid_transitions()` | O(S) | One skip resolution per path |
| `workers_for()` | O(1) | Dict lookup |
| `render_dag()` | O(N) | N = total stages, visits each once |
| `past_gate()` | O(N) | Walks from gated stage forward |
| `all_required_classes()` | O(N*W) | N stages, W workers per stage |
| `_load_all_flows()` | O(F*N) | F flows, N stages per flow |
| Task queries (`get_tasks`) | O(1) DB | SQLite index on primary key |
| Rollup (`check_and_rollup`) | O(T + R) | T = sibling tasks, R = depth of requirement tree |

**At scale:** DAG operations are bounded by flow definition size (typically 5-15 stages), not by task count. This is fine. The risk is in `rollup.py` which is recursive on the requirement tree — deeply nested requirements could cause stack overflow, though practical depth is unlikely to exceed ~5.

---

## CRUD Walk Summary

### Consistent Patterns Observed

1. **Error handling:** All CRUD functions return `dict[str, object]`. Errors use `{"error": "..."}` key. No exceptions raised for business logic errors.
2. **Agent verification:** Every write operation checks agent registration first.
3. **Connection management:** `get_db()` + `try/finally conn.close()` pattern used consistently across all CRUD files.
4. **Parameterized queries:** All SQL uses `?` placeholders — **no SQL injection risk**.
5. **Transition logging:** All status changes call `_log_transition()` for audit trail.

### Inconsistencies

1. **TaskDB class (db.py)** uses a different pattern than all other CRUD files:
   - Holds `self._conn` as persistent connection (never closed)
   - Uses `conn.commit()` per-operation (no transaction grouping)
   - Returns `dict | None` vs `dict[str, object]` with error key
   - Raises `ValueError` on not-found instead of returning error dict
   - Uses `datetime('now')` SQL function instead of Python `now_iso()`
2. **Return types:** `TaskDB.get_task()` returns `dict | None`, while `query_task.get_task()` returns `dict[str, object]` with error key. Two competing APIs for the same operation.

---

## Filled Checklist

### CS Foundations — Consistency & State

| Rule | Status | Evidence |
|------|--------|----------|
| CONSIST-1 | **YES** | All task operations go through single SQLite DB via `get_db()`. No cross-DB task operations. `TaskDB` also uses `get_db()`. Strong consistency within the DB. |
| CONSIST-2 | **NO** | Zero `with conn:` transaction wrappers in tasks/. All operations use manual `conn.commit()` without rollback on failure. `create_task()` does INSERT + `_log_transition()` INSERT as two separate operations — if second fails, task exists without log entry. Same pattern in `close_task()`, `update_task()`, `complete_phase()`, `done_task()`. |
| CONSIST-3 | **YES** | `pull_task()` uses conditional UPDATE with `WHERE status = ? AND assigned_to IS NULL` — optimistic concurrency for task claiming. Race detection via `cursor.rowcount == 0`. WAL mode + `busy_timeout=5000` handle write contention at DB level. |
| CONSIST-4 | **NO** | Task creation is not idempotent. No unique constraint on title or task_file. Calling `create_task()` twice with same args creates two tasks. No upsert pattern. `define_task()` overwrites spec file without checking existence, but creates new DB row each time. |
| CONSIST-5 | **YES** | Task flow ordering enforced by DAG transitions. `get_tasks()` queries ordered by `created_at DESC`. Transition log ordered by `created_at ASC`. Skip chain resolution has ordering guarantee via `_resolve_skip`. |

### CS Foundations — Error & Failure Modes

| Rule | Status | Evidence |
|------|--------|----------|
| ERR-1 | **NO** | Two competing error patterns within tasks/ itself: (1) dict-return `{"error": "..."}` in CRUD files (create, update, close, pull, done, submit, review, test_report), (2) raise `ValueError` in `TaskDB.transition_task()` and `TaskDB.complete()`. No custom exception hierarchy. No taxonomy of error types (auth failure vs not-found vs business rule). |
| ERR-2 | **NO** | No retry strategy. If `conn.commit()` fails mid-way (e.g., disk full), partial state is left. 17 bare `except Exception` blocks in tasks/ — most swallow errors silently (return None, pass, or continue). |
| ERR-3 | **NO** | Partial failure unhandled. `create_task()`: if `_log_transition()` fails after INSERT, task exists without transition log. `define_task()`: if `create_task()` fails after writing spec file, orphan file remains. `result.py`: `complete_phase()` failure after `submit_result()` success leaves task in inconsistent state (result submitted but phase not advanced). |
| ERR-4 | **YES** | Task engine follows fail-fast pattern for business rule violations (agent not registered, task not found, invalid transition). Non-critical failures (war plan injection, intel linking, flow echo) degrade gracefully with `except Exception: pass`. Intentional and appropriate. |
| ERR-5 | **NO** | Zero logging statements (no `logging.getLogger`, no `print`, no `click.echo`) in any tasks/ file. Failures are returned as dict values but never logged. The only observability is the `transition_log` table. System finding SF-02 applies. |

### CS Foundations — Data Architecture (subset)

| Rule | Status | Evidence |
|------|--------|----------|
| DATA-1 | **YES** | `tasks/` owns all task-related writes. No other package writes to `tasks` table directly. `db/` owns schema, `tasks/` owns business logic. `TaskDB` class is an alternate facade but still goes through same DB. |
| DATA-5 | **NO** | No task archival or cleanup. Closed tasks remain in DB forever. Transition log grows unbounded. Block reports, result files, review files, test reports accumulate in `.work/` with no cleanup. System finding per AU-00. |

### Clean Architecture (subset)

| Rule | Status | Evidence |
|------|--------|----------|
| CA-DEP-1 | **YES** | tasks/ imports from: `minion.db` (infrastructure), `minion.defaults` (shared constants), `minion.crew._tmux` (side effect — UI update), `minion.intel` (lazy imports in pull_task, define). Never imports from `minion.cli`. Dependencies point inward. |
| CA-SOLID-1 | **YES** | Each module has clear single responsibility: `create_task.py` = creation, `query_task.py` = reads, `update_task.py` = status updates, `close_task.py` = lifecycle end, `dag.py` = flow graph, `loader.py` = YAML parsing, `gates.py` = preconditions, `engine.py` = transition orchestration, `rollup.py` = parent advancement. |
| CA-COMP-1 | **YES** | No import cycles. Dependency flow: CRUD files → `flow_gates_and_validation.py` → `loader.py` → `dag.py` / `_schema.py`. `engine.py` → `gates.py` + `loader.py` + `dag.py`. `rollup.py` → `engine.py`. |
| CA-COMP-4 | **YES** | Files that change together are colocated: `dag.py` + `loader.py` + `_schema.py` (flow definition), all CRUD files share `flow_gates_and_validation.py`. |
| CA-COMP-5 | **YES** | Files used together are colocated: `create_task.py` + `submit_result.py` + `result.py` + `done.py` (task lifecycle), `review.py` + `test_report.py` (verification phase). |

### Pragmatic Programmer (subset)

| Rule | Status | Evidence |
|------|--------|----------|
| PP-CRAFT-1 | **YES** | State transitions are intentional. `complete_phase()` delegates to DAG for next-status resolution — no hardcoded fallbacks. `update_task()` has explicit comments explaining why transitions warn-but-allow. `engine.apply_transition()` has numbered steps as comments. Code does what its docstrings say. |
| PP-CRAFT-2 | **NO** | No Big-O documentation anywhere in tasks/. DAG operations are efficient (bounded by stage count, not task count) but this is not documented. `rollup.py` recursive depth not bounded or documented. |
| PP-CONTRACT-1 | **NO** | No formal preconditions/postconditions defined. `gates.py` implements gate checks (a form of preconditions) but no postconditions. `close_task()` checks `result_file` not null (precondition) but this is ad-hoc, not systematic. |
| PP-CONTRACT-2 | **YES** | Invalid operations return error immediately: agent not registered → error; task not found → error; terminal status → error; invalid transition → error. `complete_phase()` returns error if agent class is ineligible. No crippled-state operations. |
| PP-DRY-1 | **NO** | Task states defined in multiple places: YAML flow files (source of truth), `TERMINAL_STATUSES` set in `rollup.py`, `status NOT IN ('closed', 'abandoned', 'stale', 'obsolete')` hardcoded in `flow_gates_and_validation.py:63`, `terminal = {"closed", "abandoned", "obsolete"}` in `gates.py:206`. Three different terminal-status sets that could drift. Additionally, `update_task()` has a hardcoded fallback status list `{"open", "assigned", "in_progress", "fixed", "verified", "closed"}` (line 46). |

### Implementation Coding Core (subset)

| Rule | Status | Evidence |
|------|--------|----------|
| IC-HDR-1 | **NO** | Zero files have formal PURPOSE header. All 24 files use module-level docstrings instead (e.g., `"""Create and assign tasks."""`). Systemic finding SF-01. |
| IC-HDR-2 | **NO** | Zero RESPONSIBILITIES headers. Some docstrings describe responsibility informally. |
| IC-HDR-3 | **NO** | Zero NOT RESPONSIBLE FOR headers. |
| IC-HDR-4 | **NO** | Zero DEPENDENCIES headers. |
| IC-HDR-5 | **YES** | Docstrings are persistent — no evidence of removal. `engine.py` has step-numbered comments that serve as pseudo-logic. |
| IC-SCALE-1 | **NO** | No documented scale analysis. Key concerns: (1) `rollup.py` recursive depth unbounded, (2) `get_tasks()` has `LIMIT ?` parameter (default 50) — good, (3) `_db_all_child_tasks_closed()` loads all child tasks into memory — could be slow with 1000+ tasks per requirement, (4) `pull_task()` inlines file contents without size limits (`_inline_file` reads entire files). |
| IC-SCALE-4 | **NO** | Only 1 assumption documented: `engine.py` comment "Does NOT write to DB — caller handles the actual UPDATE." No assumptions about file sizes, task counts, or tree depth documented. |

---

## Findings

| # | Rule | Severity | Affected Files | Description | Remediation |
|---|------|----------|----------------|-------------|-------------|
| F-01 | CONSIST-2 | **Major** | create_task.py, close_task.py, update_task.py, done.py, complete_phase, pull_task.py, comments.py, submit_result.py | No transaction boundaries. Multi-statement writes (INSERT task + INSERT transition_log + UPDATE agents) use sequential `cursor.execute()` + single `conn.commit()` without `with conn:` context manager. If any statement fails before commit, partial writes are NOT rolled back — SQLite auto-commits are off (WAL mode), so uncommitted writes are lost, but error dict is still returned as if operation succeeded in error path handling. | Wrap multi-statement mutations in `with conn:` to get automatic rollback on exception. |
| F-02 | CONSIST-4, PP-DRY-1 | **Moderate** | create_task.py, define.py | Task creation is not idempotent. No unique constraint on (title, task_file) or any dedup mechanism. `define_task()` silently overwrites spec file content but always creates a new DB row. | Add idempotency key parameter or unique constraint. |
| F-03 | ERR-1 | **Major** | db.py vs all other files | Two competing error patterns: `TaskDB` class raises `ValueError`, all other files return `{"error": "..."}` dict. Callers must know which API they're using to handle errors correctly. | Standardize on dict-return for all task operations. Deprecate or align TaskDB. |
| F-04 | ERR-2, ERR-3 | **Moderate** | All CRUD files | 17 bare `except Exception` blocks. Most silently swallow errors: `pull_task.py` (3 blocks — war plan, intel, suggest), `context.py` (3 blocks — transition_log queries), `gates.py` (2 blocks — DB schema migration), `rollup.py` (2 blocks — column availability), `query_task.py` (4 blocks — file reads, comments, inline). Some are intentional (graceful degradation for optional features), but no distinction between "schema not ready yet" and "real bug". | At minimum, log swallowed exceptions. Add specific exception types where possible (`sqlite3.OperationalError` for missing columns). |
| F-05 | PP-DRY-1 | **Major** | rollup.py:16, gates.py:206, flow_gates_and_validation.py:63 | Terminal status sets defined in three places: `TERMINAL_STATUSES = {"closed", "abandoned", "obsolete", "completed"}` (rollup), `terminal = {"closed", "abandoned", "obsolete"}` (gates — missing "completed"), `status NOT IN ('closed', 'abandoned', 'stale', 'obsolete')` (flow_gates — includes "stale", missing "completed"). These WILL drift and cause bugs. | Define `TERMINAL_STATUSES` once (in dag.py or a constants file) and import everywhere. Or better: always use `flow.is_terminal(status)` which is the YAML-defined truth. |
| F-06 | ERR-5 | **Moderate** | All files in tasks/ | Zero logging statements in entire package. No `logging.getLogger()`, no `print()`, no structured logging. Task failures are only observable through return values (which callers may not log) and the `transition_log` table (which only captures successful transitions). | Add `logger = logging.getLogger(__name__)` and log at minimum: task creation, state transitions, gate failures, and errors. |
| F-07 | IC-SCALE-1 | **Moderate** | query_task.py, pull_task.py, context.py | `_inline_file()` reads entire files without size limits. If a task_file or result_file is 100MB (e.g., large test output), this will consume memory. `context.py` `is_stub_only()` reads entire file to check if it's a stub. | Add size check before reading: skip or truncate files > 1MB. |
| F-08 | IC-HDR-1..4 | **Info** | All 24 files | No formal comment headers (PURPOSE/RESPONSIBILITIES/NOT RESPONSIBLE FOR/DEPENDENCIES). Module docstrings exist but don't follow mandated format. Systemic finding SF-01 — mechanical fix, not a design issue. | Add headers per IC skill template. |
| F-09 | PP-CRAFT-2 | **Minor** | dag.py, rollup.py | No Big-O documentation. DAG operations are O(N) where N = stages (bounded, small). Rollup is recursive but bounded by requirement tree depth. Neither is documented. | Add complexity comments to dag.py methods and rollup recursion. |
| F-10 | CA-DEP-1 | **Minor** | create_task.py:8, close_task.py:6, pull_task.py:8, update_task.py:6 | `from minion.crew._tmux import update_pane_task` — 4 files import from a private module (`_tmux`) in a sibling package. This creates coupling to tmux UI implementation. If tmux is removed, 4 task files need updating. | Extract tmux notification behind an interface or move to a shared notification module. |
| F-11 | N/A | **Minor** | loader.py | No cycle detection at YAML load time. If a flow YAML defines A.next=B and B.next=A (no terminal), the system won't detect it. Runtime methods have cycle guards (via `visited` sets), so this won't cause infinite loops, but it's a latent correctness issue. | Add acyclic graph check in `_validate()`: walk from start to terminals, verify all stages are reachable and no unresolvable cycles exist. |
| F-12 | CONSIST-2 | **Moderate** | db.py (TaskDB class) | `TaskDB.transition_task()` does UPDATE + INSERT (transition log) + commit. Two separate statements, no transaction wrapper. If INSERT fails after UPDATE, task status is changed but no audit trail. | Same as F-01 — use `with conn:` for atomic multi-statement operations. |
| F-13 | N/A | **Minor** | db.py (TaskDB class) | `TaskDB` holds a persistent connection (`self._conn`) that is never closed. If caller forgets to close, connection leaks. All other CRUD files use `get_db()` + `try/finally conn.close()` pattern. | Add `__enter__`/`__exit__` or `close()` method to `TaskDB`. Or convert to per-operation connections like the rest of the package. |
| F-14 | PP-DRY-1 | **Minor** | update_task.py:46 | Hardcoded fallback status list `{"open", "assigned", "in_progress", "fixed", "verified", "closed"}` used when no flow is loaded. This duplicates state definitions from YAML and will drift if flows change. | Remove fallback — require flow to be loaded. If flow not found, return error. |

---

## Strengths

1. **Well-designed state machine.** `TaskFlow` and `Stage` dataclasses with clear query methods (`next_status`, `valid_transitions`, `workers_for`, `is_terminal`). Skip chain resolution with cycle detection. Gate checks are composable (file, DB, structural, task precondition).

2. **YAML-driven flow definitions.** Flow types are data, not code. New workflows (bugfix, feature, investigation, chore) are added by writing YAML, not modifying Python. Inheritance (`inherits: _base`) reduces duplication across flows.

3. **Thorough YAML validation.** `loader._validate()` checks: required keys, unknown keys, stage reference integrity, spawns/protocol/context_template file existence, worker class validation against agent class registry. Errors are descriptive and fail-hard.

4. **Clean separation of concerns.** 24 files with clear single responsibilities. `engine.py` is pure (no DB writes). `dag.py` is pure data structure. CRUD files handle DB. `gates.py` handles preconditions. `rollup.py` handles parent advancement. No file does two unrelated things.

5. **Optimistic concurrency for task claiming.** `pull_task()` uses conditional UPDATE with `WHERE status = ? AND assigned_to IS NULL` — correct pattern for preventing double-claim without explicit locks.

6. **Consistent dict-return error pattern** (except TaskDB). Every CRUD function returns `{"error": "..."}` on failure — callers can handle uniformly. Error messages are descriptive and include agent names, task IDs, and valid alternatives.

7. **Transition audit trail.** Every status change logs to `transition_log` table with entity_id, from/to status, agent, and timestamp. This provides full lineage for debugging and visualization.

8. **Parameterized SQL everywhere.** Zero string interpolation in SQL queries (except one `format()` in gates.py line 130 for field name — not user-controlled). No SQL injection risk.

9. **DAG enforcement is graduated.** `update_task()` warns but allows transitions (for flexibility). `complete_phase()` is strict (DAG-only routing). `engine.apply_transition()` validates and gate-checks but doesn't write (pure function). This supports the "low friction first, harden gradually" philosophy.

10. **Context chain assembly.** `context.py` provides three-dimensional context (task history, parent history, sibling context) for pull-task. Stub detection is thorough (strips markers, placeholders, comments).

---

## Boundary Check: B-06 (Tasks <-> DB)

### Pattern Assessment

| Aspect | Canonical db/ pattern | tasks/ pattern | Match? |
|--------|-----------------------|----------------|--------|
| Connection | `get_db()` returns WAL+Row connection | `get_db()` imported from `minion.db` | **YES** |
| Close | N/A (caller responsibility) | `try/finally conn.close()` everywhere | **YES** (consistent within tasks/) |
| Row factory | `sqlite3.Row` | Used throughout via `dict(row)` conversion | **YES** |
| Timestamps | `now_iso()` from db package | Imported and used consistently | **YES** |
| Parameterized queries | Expected | All queries use `?` placeholders | **YES** |
| Transaction boundaries | `with conn:` expected | **Not used anywhere** in tasks/ | **NO** |
| Error pattern | N/A (db/ is infrastructure) | Dict-return `{"error": ...}` | **Consistent within tasks/** |

### TaskDB Divergence

`TaskDB` (db.py in tasks/) is an older API layer that predates the CRUD modules. It:
- Holds persistent connection (vs per-operation)
- Raises ValueError (vs dict-return)
- Uses SQL `datetime('now')` (vs Python `now_iso()`)
- Never closes connection
- Has its own `create_task`, `get_task`, `list_tasks`, `transition_task` that duplicate CRUD module functionality

**Recommendation:** TaskDB should be deprecated or aligned with the CRUD module patterns. It creates confusion about which API to use and has inconsistent error handling.

---

## Summary Statistics

| Category | Rules Evaluated | YES | NO | N/A |
|----------|----------------|-----|-----|-----|
| CS-CONSIST | 5 | 3 | 2 | 0 |
| CS-ERR | 5 | 1 | 4 | 0 |
| CS-DATA | 2 | 1 | 1 | 0 |
| CA (subset) | 5 | 5 | 0 | 0 |
| PP (subset) | 5 | 2 | 3 | 0 |
| IC (subset) | 7 | 1 | 6 | 0 |
| **Total** | **29** | **13** | **16** | **0** |

**Findings:** 14 (3 Major, 5 Moderate, 5 Minor, 1 Info)
**Strengths:** 10 identified
