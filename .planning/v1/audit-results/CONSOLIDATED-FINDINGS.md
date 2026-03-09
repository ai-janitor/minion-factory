# Consolidated Audit Findings — v1

**Date:** 2026-03-09
**Reconciliation agent:** AU-Reconciliation (Stage 8b)
**Input:** 11 audit reports (AU-00 through AU-10)

---

## Summary Statistics

| Metric | Count |
|--------|-------|
| **Total unique findings (after dedup)** | **62** |
| Critical | 5 |
| Major | 14 |
| Moderate | 24 |
| Minor | 14 |
| Info | 5 |
| | |
| **By classification** | |
| Systemic (entire codebase) | 12 |
| Domain-specific (one package) | 38 |
| Boundary (interface between domains) | 12 |

### Systemic Findings (the big ones that affect everything)

| ID | Title | Severity |
|----|-------|----------|
| F-001 | Three competing logging patterns, no canonical strategy | Critical |
| F-002 | 17 packages with zero behavioral tests | Critical |
| F-003 | No formal comment headers (IC-HDR) on 181 files | Major |
| F-004 | Two competing error patterns, no exception hierarchy | Major |
| F-005 | Config access scattered — env reads bypass defaults.py | Moderate |
| F-006 | No contracts or assertions in production code | Moderate |
| F-007 | 103 bare `except Exception` blocks across 43 files | Moderate |
| F-008 | No Big-O documentation anywhere | Moderate |
| F-009 | No data lifecycle management (no TTL, no purge, no archival) | Moderate |
| F-010 | Unbounded file reads across multiple packages | Moderate |
| F-011 | No formal pattern registry documenting codebase conventions | Minor |
| F-012 | No assumptions documented in code comments | Minor |

---

## Findings (sorted by severity, then blast radius)

### Critical

#### F-001: Three competing logging patterns, no canonical strategy
- **Classification:** Systemic
- **Affected domains:** All (D1-D15)
- **Found by:** AU-00 (SF-02), AU-05 (F-01), AU-06 (F-07), AU-10 (F001)
- **Rules:** CS-ERR-5, PP-APPROACH-3
- **Description:** Three competing logging patterns coexist with no strategy or configuration: `logging.getLogger` (3 files, no handler config — writes to nowhere), `print()` (27+ files, 55+ occurrences), `click.echo()` (10+ files, 45+ occurrences). No structured logging, no log levels in print() calls, no centralized config. The daemon has its own structured JSON `_log()` method but it is not reused. Logging.getLogger instances in db/migrations.py, db/coordinator.py, intel/_frontmatter.py have no configured handlers.
- **Evidence:** AU-10 counted 102+ total logging occurrences across 40+ files with no consistent pattern.
- **Remediation:** Choose canonical pattern: `logging.getLogger(__name__)` for library/business code, `click.echo` for CLI user output only, daemon `_log()` stays as-is. Add `logging.basicConfig()` in cli/main.py and daemon entrypoint. Migrate all `print()` warning/error calls to logging with appropriate levels.

#### F-002: 17 packages with zero behavioral tests
- **Classification:** Systemic
- **Affected domains:** All untested packages (auth, providers, intel, missions, lifecycle, monitoring, output, dashboard, filesafety, triggers, flow_bridge, polling, api, defaults, fs, cli_schema, prompts)
- **Found by:** AU-00 (SF-04), AU-09 (F001)
- **Rules:** TDD-CYC-1, TDD-COV-1, TDD-COV-2, TDD-COV-3
- **Description:** 17 of 27 source packages have zero behavioral tests. Test coverage concentrated in backlog (69 functions), tasks (51), requirements (44). Critical untested areas: auth (gates ALL CLI commands), providers (4 implementations with subprocess calls), network handlers (untrusted boundary with zero error-path tests). 234 tests exist but are clustered in 10 packages.
- **Evidence:** AU-09 coverage map; AU-06 F-07 specifically notes network handler error paths untested.
- **Remediation:** Prioritize by risk: (1) auth — HIGH, gates all commands; (2) providers — HIGH, 4 implementations; (3) network handlers — HIGH, untrusted boundary; (4) lifecycle/polling — MEDIUM; (5) missions — MEDIUM.

#### F-003-C: No Content-Length limit on network API request body (DoS)
- **Classification:** Domain-specific (D7-Network)
- **Affected domains:** D7 (Network API)
- **Found by:** AU-06 (F-03)
- **Rules:** CS-SEC-5
- **Description:** `_read_body()` in server.py reads exactly `Content-Length` bytes with no upper bound. An attacker can send `Content-Length: 10737418240` (10GB) and the server will attempt to allocate and read that much memory, causing DoS. This is on the untrusted network boundary.
- **Evidence:** server.py:72-74 — `length = int(self.headers.get("Content-Length", 0)); return self.rfile.read(length)`
- **Remediation:** Add maximum body size check (e.g., 10MB) before `rfile.read(length)`. Return 413 Payload Too Large if exceeded.

#### F-004-C: Halt detection bug — queries non-existent column, error silently swallowed
- **Classification:** Domain-specific (D6-Daemon)
- **Affected domains:** D6 (Daemon Runtime)
- **Found by:** AU-05 (F-10)
- **Rules:** CS-ERR-2 (silent error swallowing), correctness bug
- **Description:** `_has_pending_halt()` in daemon/runner/_db.py line 180 queries `WHERE read = 0` but the schema defines the column as `read_flag`. This query raises `sqlite3.OperationalError: no such column: read`, which is silently swallowed by `except Exception: pass` on line 188. **Halt detection during phoenix_down auto-respawn is completely broken.** The daemon will never detect a pending halt message after auto-respawn.
- **Evidence:** _db.py:180 `WHERE read = 0` vs schema column `read_flag`.
- **Remediation:** Change `read = 0` to `read_flag = 0` on line 180. Add logging to the except block. Add a test for halt detection.

#### F-005-C: No input validation on network API /register endpoint
- **Classification:** Domain-specific (D7-Network)
- **Affected domains:** D7 (Network API)
- **Found by:** AU-06 (F-04)
- **Rules:** CS-SEC-5, IC-DATA-1, IC-DATA-2
- **Description:** `/register` POST accepts 20+ fields via `body.get()` with no type checking, no length limits, no enum validation. `agent_class` is not validated against known classes. `capabilities`, `machine_specs`, `runtimes` are JSON-serialized without schema validation. Any string can be stored. Combined with F-003-C (no body size limit), this allows arbitrary data injection into the network DB.
- **Evidence:** handlers/core.py:225-316 — 20+ body.get() calls with no validation.
- **Remediation:** Define a schema (dataclass or dict with type+required+max_length). Validate before writing. Return 400 with descriptive errors on validation failure.

### Major

#### F-003: No formal comment headers on 181 files
- **Classification:** Systemic
- **Affected domains:** All (D1-D15)
- **Found by:** AU-00 (SF-01), AU-01 (F015), AU-02 (F-09), AU-03 (F-08), AU-04 (F-08), AU-05 (F-07), AU-06 (F-17), AU-07 (F-04), AU-08 (F-03), AU-10 (IC-HDR)
- **Rules:** IC-HDR-1, IC-HDR-2, IC-HDR-3, IC-HDR-4
- **Description:** Zero files use the mandated PURPOSE/RESPONSIBILITIES/NOT RESPONSIBLE FOR/DEPENDENCIES header format. 95% have module-level docstrings instead, which are informative but non-standard. Only exception: `network/auth.py` and `network/project_db.py` have formal headers — demonstrating the pattern is known. Every single auditor flagged this.
- **Evidence:** All 11 audit reports confirm zero formal headers. network/auth.py is the sole positive example.
- **Remediation:** Mechanical batch fix across all 181 files. Low complexity per file, high count. Can be semi-automated.

#### F-004: Two competing error patterns, no exception hierarchy
- **Classification:** Systemic
- **Affected domains:** All (D1-D15)
- **Found by:** AU-00 (SF-03), AU-03 (F-02), AU-04 (F-03), AU-10 (F002)
- **Rules:** CS-ERR-1, PP-CONTRACT-1
- **Description:** Two competing error patterns with no documented convention: (1) dict-return `{"error": "..."}` for business logic functions (25+ files), consumed by output.py `if "error" in data:` convention; (2) `raise ValueError/FileNotFoundError/RuntimeError` for config/loaders (20+ files). No custom exception hierarchy — zero custom Exception subclasses in entire codebase. Some files mix both patterns (backlog/promote.py, backlog/add_item.py). Within tasks/, TaskDB raises ValueError while all CRUD modules return error dicts — two APIs for the same operations.
- **Evidence:** AU-10 cataloged both patterns across 45+ files. AU-04 F-03 specifically notes TaskDB vs CRUD module divergence.
- **Remediation:** Document the convention: dict-return for CLI-consumed functions, raise for internal validation. Consider `MinionError` base exception. Add `Result` TypedDict for dict-return pattern.

#### F-006: No transaction boundaries on multi-step mutations
- **Classification:** Boundary (D3-DB, D4-Tasks, D6-Daemon)
- **Affected domains:** D3 (Database), D4 (Task Engine), D6 (Daemon)
- **Found by:** AU-00 (SF-10), AU-02 (F-02), AU-04 (F-01, F-12), AU-05 (F-05)
- **Rules:** CS-CONSIST-2
- **Description:** Zero uses of `with conn:` context manager in business logic. Multi-step mutations rely on sequential `cursor.execute()` + single `conn.commit()` without rollback on failure. Specific risks: (a) `tasks/db.py` `transition_task()` does UPDATE + INSERT transition_log — if INSERT fails, task status changed with no audit trail; (b) `comms/register.py` deregistration does 4+ DELETEs without transaction; (c) `create_task()` does INSERT + `_log_transition()` as two operations. Only migrations use explicit BEGIN/COMMIT/ROLLBACK.
- **Evidence:** AU-02 found zero `with conn:` in business code; AU-04 counted 8 CRUD files with multi-statement mutations lacking transaction boundaries.
- **Remediation:** Wrap multi-statement mutations in `with conn:` for automatic rollback. Prioritize task transitions and agent deregistration.

#### F-007: No network API input validation (beyond /register)
- **Classification:** Domain-specific (D7-Network)
- **Affected domains:** D7 (Network API)
- **Found by:** AU-00 (SF-06), AU-06 (F-05, F-10, F-11, F-12)
- **Rules:** CS-SEC-5, IC-DATA-1 through IC-DATA-5
- **Description:** Handlers use manual `body.get()` with no schema validation, no length limits, no type checking. `/send` has no message content length limit. `/api/sprint` reads entire files without size limit. `/projects/{name}/raid-log` reads entry files with no truncation. 25+ body.get/json.loads calls across handler files with zero validation. No Content-Type validation on incoming requests.
- **Evidence:** AU-06 endpoint inventory shows 28 active endpoints; none validate input beyond checking required fields are non-empty.
- **Remediation:** Define request/response schemas. Add max_length checks on message content (100KB). Add file size limits on reads. Add Content-Type validation.

#### F-008: 27 direct sqlite3.connect() calls bypass get_db()
- **Classification:** Boundary (D3-DB, D6-Daemon, D7-Network)
- **Affected domains:** D3, D6, D7, D13 (Backlog)
- **Found by:** AU-02 (F-01)
- **Rules:** PP-DRY-1
- **Description:** `get_db()` is the canonical connection factory but is widely bypassed. 27 direct `sqlite3.connect()` calls in daemon/runner/_db.py (10), network modules (7), backlog/close_item.py (1), comms (2), dashboard (1). Each reimplements connection setup with slight variations (timeout=5 vs timeout=2, missing WAL pragma, missing foreign_keys pragma, inconsistent row_factory). Daemon has justified reasons (subprocess path control) but the pattern should be standardized.
- **Evidence:** AU-02 found 27 direct calls across 10+ files outside db/connection.py.
- **Remediation:** Extract `_connect(db_path, readonly=False)` helper in db/connection.py. All modules call this instead of raw sqlite3.connect().

#### F-009: Config parsing duplicated between daemon and crew
- **Classification:** Boundary (B-07: Daemon <-> Crew)
- **Affected domains:** D6 (Daemon), D3 (Crew)
- **Found by:** AU-00 (SF-08), AU-03 (F-06), AU-05 (F-08), AU-10 (F003)
- **Rules:** PP-DRY-1, PP-DRY-2
- **Description:** `daemon/config.py:load_config()` (~135 lines) and `crew/config.py:load_config()` (~182 lines) are near-copies with ~80% code overlap. Dataclass sharing resolved (daemon imports from crew), but YAML parsing logic is duplicated. Divergence already exists: crew has `skills` and `scope` fields, daemon does not.
- **Evidence:** AU-05, AU-03, AU-10 all independently identified and measured the duplication.
- **Remediation:** Extract shared `_parse_agents(raw, cfg_path)` helper into crew/config.py. daemon/config.py calls it with domain-specific field additions.

#### F-010: backlog_cmds.py bypasses output funnel (23 times)
- **Classification:** Domain-specific (D1-CLI)
- **Affected domains:** D1 (CLI Layer)
- **Found by:** AU-01 (F014, F006), AU-10 (F008)
- **Rules:** PP-DRY-1
- **Description:** `backlog_cmds.py` has 23 direct `click.echo(json.dumps(...))` calls instead of using `_output()`. Every other CLI module uses `_output()`. The `--human` and `--compact` flags are silently ignored for all backlog commands. The error-handling pattern `try/except ValueError -> json error -> sys.exit(1)` is repeated 10 times.
- **Evidence:** AU-01 counted 23 direct echo calls and 10 repeated error patterns. AU-10 confirmed.
- **Remediation:** Refactor backlog_cmds.py to use `_output()`. Extract error-handling wrapper.

#### F-011: Token comparison uses == (timing-unsafe)
- **Classification:** Domain-specific (D7-Network)
- **Affected domains:** D7 (Network API)
- **Found by:** AU-06 (F-02)
- **Rules:** CS-SEC-2
- **Description:** Both `_check_token()` in server.py and `check_token()` in network/auth.py compare bearer tokens with `==` instead of `hmac.compare_digest()`. An attacker can use timing side-channel to extract the token byte-by-byte on the network boundary.
- **Evidence:** server.py:42, auth.py:33 — plain `==` comparison.
- **Remediation:** Replace with `hmac.compare_digest(auth, f"Bearer {expected}")` in both locations.

#### F-012: AuthMixin defined but not wired — dead code
- **Classification:** Domain-specific (D7-Network)
- **Affected domains:** D7 (Network API)
- **Found by:** AU-06 (F-01), AU-10 (F005)
- **Rules:** PP-DRY-1, SEC-2
- **Description:** `network/auth.py` exports `check_token()` and `AuthMixin` with formal scaffold headers. `server.py` defines its own `_check_token()` with identical logic. `_Handler` does NOT inherit from `AuthMixin`. Result: auth.py is dead code — defined, documented, scaffolded, but never imported by server.py. Two implementations of identical logic coexist.
- **Evidence:** AU-06 verified _Handler does not inherit AuthMixin; server.py has inline _check_token.
- **Remediation:** Wire AuthMixin into _Handler or import check_token from network/auth.py. Delete inline _check_token.

#### F-013: Terminal status sets defined in three places (drift risk)
- **Classification:** Domain-specific (D4-Task Engine)
- **Affected domains:** D4 (Task Engine)
- **Found by:** AU-04 (F-05)
- **Rules:** PP-DRY-1
- **Description:** Terminal task statuses defined in three inconsistent places: `TERMINAL_STATUSES = {"closed", "abandoned", "obsolete", "completed"}` (rollup.py), `terminal = {"closed", "abandoned", "obsolete"}` (gates.py — missing "completed"), `status NOT IN ('closed', 'abandoned', 'stale', 'obsolete')` (flow_gates — includes "stale", missing "completed"). Additionally, `update_task.py:46` has a hardcoded fallback status list. These WILL drift and cause bugs.
- **Evidence:** AU-04 identified three different terminal-status sets with existing inconsistencies.
- **Remediation:** Define `TERMINAL_STATUSES` once in dag.py or constants module. Better: always use `flow.is_terminal(status)` which queries YAML truth.

#### F-014: Non-atomic multi-tier agent registration
- **Classification:** Domain-specific (D3-Comms)
- **Affected domains:** D3 (Comms/Crew)
- **Found by:** AU-03 (F-03)
- **Rules:** CS-ERR-3
- **Description:** `register()` writes to 3 tiers sequentially: local DB, coordinator DB, network API. Each tier has `except Exception` that swallows failures. If tier 2 fails, agent is locally registered but globally invisible. No rollback, no compensation, no partial-success status returned.
- **Evidence:** comms/register.py:79-129 — sequential tier writes with bare except.
- **Remediation:** Document partial registration as accepted behavior OR implement compensation. At minimum, return partial_success status so callers know.

#### F-015: Network handler error paths completely untested
- **Classification:** Boundary (D7-Network, D9-Tests)
- **Affected domains:** D7 (Network), D9 (Tests)
- **Found by:** AU-09 (F007)
- **Rules:** TDD-COV-3
- **Description:** 8 handler modules with ~25 body.get()/json.loads() calls process untrusted input. Zero tests verify error responses for malformed requests, missing fields, or invalid data. Route integrity tests only verify routes exist and handlers are callable, not actual behavior.
- **Evidence:** AU-09 coverage map shows network has 8 structural tests only.
- **Remediation:** Add handler-level tests with invalid payloads: missing required fields, wrong types, oversized payloads, malformed JSON.

#### F-016: Unbounded file reads across multiple packages
- **Classification:** Systemic
- **Affected domains:** D5 (Intel), D7 (Network), D8 (Prompts), D10 (Cross-cutting)
- **Found by:** AU-00 (IC-SCALE-3), AU-07 (F-03), AU-06 (F-10, F-11, F-12), AU-08 (F-06), AU-10 (F007)
- **Rules:** IC-SCALE-3
- **Description:** Multiple packages use `fh.read()` with no size limits: intel/read_doc.py (user-triggered, highest risk), intel/_frontmatter.py, war_plan.py, fs.read_content_file(), network handlers reading content files, prompt loaders reading template files. A large file would cause memory exhaustion.
- **Evidence:** AU-07 found 4 unbounded reads in intel/. AU-06 found 3 in network handlers. AU-10 found 2 in cross-cutting.
- **Remediation:** Add `MAX_DOC_SIZE` constant (10MB). Read up to limit, return truncation warning if exceeded. For summary modes, read line-by-line instead of full-read-then-truncate.

### Moderate

#### F-017: No data lifecycle management
- **Classification:** Systemic
- **Affected domains:** All (D3, D4, D6)
- **Found by:** AU-00 (DATA-5), AU-02 (F-03), AU-04 (DATA-5)
- **Rules:** CS-DATA-5
- **Description:** Messages, transition_log, invocation_log, compaction_log, raid_log, and backlog items grow unbounded. No TTL, no purge, no archival. Only cleanup: stale agent pruning in coordinator.py (6-hour threshold) and manual `purge_inbox` with configurable `older_than_hours`.
- **Remediation:** Add db/cleanup.py with configurable retention policies. Run in daemon's periodic maintenance.

#### F-018: Config access scattered — 13+ env reads bypass defaults.py
- **Classification:** Systemic
- **Affected domains:** D1, D6, D7, D10
- **Found by:** AU-00 (SF-05), AU-08 (F-05), AU-10 (F004)
- **Rules:** PP-ORTH-2, PP-DECOUPLE-5
- **Description:** defaults.py covers core paths well but 5 network/cluster env vars (MINION_CLUSTER_TOKEN, MINION_NETWORK_URL, MINION_NETWORK_INSECURE, MINION_COMPAT_PROJECT, MINION_TS_DAEMON_DIR) are scattered direct reads with no canonical constants. ~13 of 33 os.environ reads bypass defaults.py.
- **Remediation:** Add ENV_CLUSTER_TOKEN, ENV_NETWORK_URL, ENV_NETWORK_INSECURE, etc. to defaults.py. Replace direct reads.

#### F-019: No contracts or assertions in production code
- **Classification:** Systemic
- **Affected domains:** All
- **Found by:** AU-00 (CONTRACT-1, CONTRACT-3), AU-03 (F-09), AU-04 (PP-CONTRACT-1), AU-05 (F-06), AU-10 (F006)
- **Rules:** PP-CONTRACT-1, PP-CONTRACT-3
- **Description:** Zero preconditions/postconditions/invariants defined. Only 5 `assert` statements in entire production codebase. daemon/contracts.py is misleadingly named (just a JSON file loader). send() has 5 implicit preconditions enforced in code but not declared.
- **Remediation:** Add assertions for impossible conditions. Document contracts in docstrings for critical functions. Consider renaming daemon/contracts.py.

#### F-020: 103 bare except Exception blocks across 43 files
- **Classification:** Systemic
- **Affected domains:** D4, D6, D7, D10
- **Found by:** AU-00 (SF-11), AU-04 (F-04), AU-05 (resilience audit), AU-06 (F-07), AU-10 (F010)
- **Rules:** CS-ERR-2
- **Description:** 103 bare `except Exception` blocks. Some are appropriate (daemon resilience — 13 of 16 are logged and intentional). Others silently swallow errors: monitoring.py (pass), overview.py (pass), core.py (pass). The halt detection bug (F-004-C) was masked by a silent except. AU-05 found 3 marginal silent blocks in daemon.
- **Remediation:** Audit each block — narrow catches where possible. At minimum, add logging to silent blocks. Specifically catch expected exceptions (sqlite3.OperationalError, etc.).

#### F-021: No Big-O documentation anywhere
- **Classification:** Systemic
- **Affected domains:** D4, D6
- **Found by:** AU-00 (SCALE-4), AU-04 (F-09), AU-05 (SCALE-4)
- **Rules:** CS-SCALE-4, PP-CRAFT-2
- **Description:** No Big-O or complexity documentation in any file. Key operations: DAG operations O(N) where N=stages (bounded), rollup.py recursive on requirement tree depth (unbounded), daemon polling O(1) per agent, task queries O(1) DB lookups.
- **Remediation:** Add complexity comments to dag.py, rollup.py, and daemon polling methods.

#### F-022: Missing Python-level timeout on daemon poll subprocess
- **Classification:** Domain-specific (D6-Daemon)
- **Affected domains:** D6 (Daemon)
- **Found by:** AU-05 (F-04)
- **Rules:** IC-SCALE-2
- **Description:** `subprocess.run()` for `_poll_inbox()` has no Python-level `timeout` parameter. If `minion poll` process hangs beyond its internal timeout, the daemon blocks indefinitely. Other subprocess calls in daemon DO have timeouts (alert, HP, check-work use timeout=10).
- **Remediation:** Add `timeout=60` to subprocess.run() in _poll_inbox().

#### F-023: No per-endpoint authorization on network API
- **Classification:** Domain-specific (D7-Network)
- **Affected domains:** D7 (Network API)
- **Found by:** AU-06 (F-06)
- **Rules:** CS-SEC-3
- **Description:** Binary authorization only — valid token grants full access to all 28 endpoints. Any authenticated caller can register agents, send messages as anyone, read all projects. No RBAC, no per-agent scoping.
- **Remediation:** Acceptable for single-team/local usage. Document as intentional. For multi-team deployment: add role-based access.

#### F-024: No message type taxonomy
- **Classification:** Domain-specific (D3-Comms)
- **Affected domains:** D3 (Comms)
- **Found by:** AU-03 (F-01), AU-00 (COMM-3)
- **Rules:** CS-COMM-3
- **Description:** Messages are untyped text blobs. No `message_type` field distinguishes commands from status reports from data payloads. Trigger words (moon_crash, stand_down) detected by string scanning, not message metadata.
- **Remediation:** Add `message_type` column to messages table. Populate at send time.

#### F-025: Incomplete deregister cleanup
- **Classification:** Domain-specific (D3-Comms)
- **Affected domains:** D3 (Comms)
- **Found by:** AU-03 (F-04)
- **Rules:** PP-CONTRACT-4
- **Description:** `deregister()` removes DB rows and roster file but does NOT: (a) delete message content files in `.work/inbox/{agent}/`, (b) remove messages in DB where agent is sender, (c) notify in-flight senders. Coordinator deregister silently swallows exceptions.
- **Remediation:** Add inbox directory cleanup to deregister(). Document what deregister does and does not clean up.

#### F-026: Concrete coupling crew -> daemon config
- **Classification:** Boundary (B-05: Crew <-> Daemon)
- **Affected domains:** D3 (Crew), D6 (Daemon)
- **Found by:** AU-03 (F-05)
- **Rules:** CA-DEP-5
- **Description:** `crew/daemon.py` imports `from minion.daemon.config import load_config` — concrete dependency on daemon's config loader. No interface boundary. If daemon config changes signature, crew breaks.
- **Remediation:** Extract shared config loading into common module or use DIP.

#### F-027: Bidirectional coupling comms <-> crew
- **Classification:** Boundary (B-05)
- **Affected domains:** D3 (Comms), D6 (Crew)
- **Found by:** AU-03 (F-07)
- **Rules:** PP-ORTH-1
- **Description:** `comms/register.py` lazy-imports from crew (spawn._find_crew_file, config.load_config). `crew/lifecycle.py` imports comms.deregister. `crew/spawn.py` imports comms.register. Package-level cycle: comms -> crew -> comms.
- **Remediation:** Extract crew-context-merge into mediator or move it to crew/ side.

#### F-028: No conftest.py — fixture duplication across 11 test files
- **Classification:** Domain-specific (D9-Tests)
- **Affected domains:** D9 (Tests)
- **Found by:** AU-09 (F002)
- **Rules:** PP-DRY-1 (test infra)
- **Description:** No shared conftest.py. `isolated_db` pattern duplicated 7 times, `_run()` CLI wrapper 5 times, `_insert_battle_plan()` 3 times, `_task_status()` 3 times. ~150 lines of unnecessary duplication.
- **Remediation:** Create tests/conftest.py with shared fixtures. Move helpers to tests/helpers.py.

#### F-029: Verb vocabulary inconsistencies in CLI
- **Classification:** Domain-specific (D1-CLI)
- **Affected domains:** D1 (CLI)
- **Found by:** AU-01 (F004)
- **Rules:** CMD-4
- **Description:** Create operations: register/create/add/spawn. Delete: deregister/kill/remove-remote. List: list/who. Completion: done/close/complete-phase. Inconsistent vocabulary makes the CLI harder to learn.
- **Remediation:** Standardize on canonical verbs. Add aliases for backwards compat.

#### F-030: Exit codes undocumented and inconsistent
- **Classification:** Domain-specific (D1-CLI)
- **Affected domains:** D1 (CLI)
- **Found by:** AU-01 (F012)
- **Rules:** AGENT-4
- **Description:** poll: 0/1/3. check-work: 0/1. output.py: always 1 for error. Both `sys.exit(1)` and `raise SystemExit(1)` used. No exit(2) for usage errors. No documented convention.
- **Remediation:** Define convention (0=success, 1=error, 2=usage, 3=signal). Document in root --help.

#### F-031: Stream log file grows unbounded in daemon
- **Classification:** Domain-specific (D6-Daemon)
- **Affected domains:** D6 (Daemon)
- **Found by:** AU-05 (F-02)
- **Rules:** CS-SCALE-5
- **Description:** `<agent>.stream.jsonl` grows indefinitely for long-running daemons. No log rotation, no max-size truncation.
- **Remediation:** Add log rotation or max-size truncation for stream.jsonl.

#### F-032: _resolve_or_404 duplicated across 3 handler modules
- **Classification:** Domain-specific (D7-Network)
- **Affected domains:** D7 (Network)
- **Found by:** AU-06 (F-08)
- **Rules:** PP-DRY-1
- **Description:** Three handler modules define their own `_resolve_or_404()` with identical logic. Backlog handler inlines the logic.
- **Remediation:** Extract to handlers/_common.py.

#### F-033: _append_error_log duplicated between codex and gemini providers
- **Classification:** Domain-specific (D5-Providers)
- **Affected domains:** D5 (Providers)
- **Found by:** AU-07 (F-01)
- **Rules:** PP-DRY-1
- **Description:** `_append_error_log()` copy-pasted verbatim (12 lines) between CodexProvider and GeminiProvider.
- **Remediation:** Move to BaseProvider as static method.

#### F-034: No pytest markers — no test subset selection
- **Classification:** Domain-specific (D9-Tests)
- **Affected domains:** D9 (Tests)
- **Found by:** AU-09 (F004)
- **Rules:** Test infrastructure
- **Description:** Only `@pytest.mark.parametrize` used. No custom markers (unit, integration, smoke, slow). No way to run test subsets.
- **Remediation:** Add markers. Register in pyproject.toml.

#### F-035: Daemon lifecycle states not formally defined
- **Classification:** Domain-specific (D6-Daemon)
- **Affected domains:** D6 (Daemon)
- **Found by:** AU-05 (lifecycle analysis)
- **Rules:** CS-COMM-3
- **Description:** 8 daemon lifecycle states (idle, working, error, phoenix_down, etc.) written to JSON state files as free-text strings. No enum, no validation, no formal state machine.
- **Remediation:** Define enum of valid states. Validate in _write_state().

#### F-036: Agent status accepts any string — no state machine
- **Classification:** Domain-specific (D3-Comms)
- **Affected domains:** D3 (Comms)
- **Found by:** AU-03 (F-10)
- **Rules:** CS-COMM-3
- **Description:** `set_status()` accepts any arbitrary string. No validation of valid transitions. The agent lifecycle is implicit — convention, not mechanism.
- **Remediation:** Define enum of valid statuses. Validate in set_status().

#### F-037: Role prompt self-service block duplicated across 6 files
- **Classification:** Domain-specific (D8-Prompts)
- **Affected domains:** D8 (Prompts)
- **Found by:** AU-08 (F-01)
- **Rules:** PP-DRY-1, PP-DRY-2
- **Description:** 6 of 7 role prompts contain identical 7-line "Self-service chore tasks" block. If chore CLI syntax changes, 6 files must be updated.
- **Remediation:** Extract common blocks into roles/_common/base.md; have load_role_prompt() inject them.

#### F-038: db/ imports from auth (higher layer — dependency violation)
- **Classification:** Boundary (D3-DB, D10-Auth)
- **Affected domains:** D3 (Database), D10 (Cross-cutting)
- **Found by:** AU-02 (F-04)
- **Rules:** CA-DEP-1
- **Description:** `db/agents.py` imports `CLASS_STALENESS_SECONDS` from auth; `db/messages.py` imports `TRIGGER_WORDS` from auth. Both use deferred imports to avoid circular deps — code smell indicating inverted dependency.
- **Remediation:** Move constants to shared constants module accessible from both auth and db.

#### F-039: Daemon DBMixin connect-execute-commit-close repeated 10 times
- **Classification:** Domain-specific (D6-Daemon)
- **Affected domains:** D6 (Daemon)
- **Found by:** AU-02 (F-05), AU-05 (resilience audit)
- **Rules:** PP-DRY-2
- **Description:** Every method in DBMixin opens a fresh connection, sets busy_timeout, executes SQL, commits, and closes — identical boilerplate 10 times.
- **Remediation:** Extract `_with_db(self, fn)` helper or context manager.

#### F-040: Zero tests for missions package
- **Classification:** Domain-specific (D8-Missions)
- **Affected domains:** D8 (Missions)
- **Found by:** AU-08 (F-04), AU-09 (F001)
- **Rules:** TDD-COV-1
- **Description:** Zero behavioral tests for missions. No test verifies YAML loading, resolver slot computation, party suggestion, or spawn flow.
- **Remediation:** Write tests for load_mission(), resolve_slots(), list_missions(), suggest_party().

### Minor

#### F-041: ~244 of ~250 CLI options lack short flags
- **Classification:** Domain-specific (D1-CLI)
- **Affected domains:** D1 (CLI)
- **Found by:** AU-01 (F003)
- **Rules:** CMD-3
- **Description:** Only 6 short flags exist (-C, -v, -p, -m, -o). High-frequency agent options like --agent, --task-id, --name have no short forms. Agents burn tokens typing full flag names.
- **Remediation:** Add short flags for top-20 most-used options.

#### F-042: Top-level command leaks (deregister, rename, interrupt, resume)
- **Classification:** Domain-specific (D1-CLI)
- **Affected domains:** D1 (CLI)
- **Found by:** AU-01 (F016)
- **Rules:** CMD-4
- **Description:** 4 commands registered at root level instead of under appropriate groups.
- **Remediation:** Move to groups, add hidden root aliases for backwards compat.

#### F-043: No fuzzy matching for unknown CLI commands
- **Classification:** Domain-specific (D1-CLI)
- **Affected domains:** D1 (CLI)
- **Found by:** AU-01 (F009)
- **Rules:** DISC-3
- **Description:** Typing `minion agnt` fails with generic error, no suggestion for `agent`.
- **Remediation:** Install click-didyoumean plugin.

#### F-044: Interactive getpass() fallback in api commands
- **Classification:** Domain-specific (D1-CLI)
- **Affected domains:** D1 (CLI)
- **Found by:** AU-01 (F011)
- **Rules:** AGENT-1
- **Description:** `api start` and `api set-remote` fall back to `getpass.getpass()` when no token provided. Breaks agents without TTY.
- **Remediation:** Guard with `sys.stdin.isatty()` check. Add --token flag.

#### F-045: Inconsistent WAL mode in daemon connections
- **Classification:** Domain-specific (D6-Daemon)
- **Affected domains:** D6 (Daemon)
- **Found by:** AU-02 (F-06)
- **Rules:** CS-CONSIST-3
- **Description:** Daemon DBMixin connections do NOT set WAL pragma. Relies on prior init_db() having set it (WAL persists per-database).
- **Remediation:** Add WAL pragma to daemon connection helper for safety.

#### F-046: Inconsistent row_factory in daemon DB operations
- **Classification:** Domain-specific (D6-Daemon)
- **Affected domains:** D6 (Daemon)
- **Found by:** AU-02 (F-07)
- **Rules:** CS-CONSIST-3
- **Description:** Only 1 of 10 DBMixin methods sets row_factory. Others use tuple-index access — fragile if column order changes.
- **Remediation:** Set row_factory on all connections.

#### F-047: Task engine imports from private _tmux module
- **Classification:** Boundary (D4-Tasks, D3-Crew)
- **Affected domains:** D4 (Tasks), D3 (Crew)
- **Found by:** AU-04 (F-10)
- **Rules:** CA-DEP-1
- **Description:** 4 task files import `from minion.crew._tmux import update_pane_task` — coupling to a private module.
- **Remediation:** Extract behind interface or shared notification module.

#### F-048: No cycle detection at YAML flow load time
- **Classification:** Domain-specific (D4-Tasks)
- **Affected domains:** D4 (Task Engine)
- **Found by:** AU-04 (F-11)
- **Rules:** Correctness
- **Description:** If a flow YAML defines A.next=B and B.next=A (no terminal), the system won't detect it at load time. Runtime methods have cycle guards, so no infinite loops, but it's a latent issue.
- **Remediation:** Add acyclic graph check in _validate().

#### F-049: TaskDB holds persistent connection — never closed
- **Classification:** Domain-specific (D4-Tasks)
- **Affected domains:** D4 (Task Engine)
- **Found by:** AU-04 (F-13)
- **Rules:** PP-CONTRACT-4
- **Description:** `TaskDB` holds `self._conn` that is never closed. Connection leaks if caller forgets. All other CRUD files use get_db() + try/finally close.
- **Remediation:** Add __enter__/__exit__ or close() method.

#### F-050: Bare except blocks in intel swallow non-integrity errors
- **Classification:** Domain-specific (D5-Intel)
- **Affected domains:** D5 (Intel)
- **Found by:** AU-07 (F-05, F-06)
- **Rules:** CS-ERR-2
- **Description:** add_doc.py uses `except Exception: pass` for auto-link insertion. Should be `except sqlite3.IntegrityError: pass` to match link_doc.py pattern. register_docs.py silently swallows file read errors.
- **Remediation:** Narrow catches; add debug logging.

#### F-051: _classify_error methods share structural pattern across providers
- **Classification:** Domain-specific (D5-Providers)
- **Affected domains:** D5 (Providers)
- **Found by:** AU-07 (F-02)
- **Rules:** PP-DRY-2
- **Description:** `_classify_codex_error()` and `_classify_gemini_error()` share structure (JSON parse -> regex -> fallback) with minor field-name variations.
- **Remediation:** Extract template method in BaseProvider.

#### F-052: Scaling endpoints registered as no-op (unreachable code)
- **Classification:** Domain-specific (D7-Network)
- **Affected domains:** D7 (Network)
- **Found by:** AU-06 (F-16)
- **Rules:** COMM-2
- **Description:** scaling.py `register()` does `pass`. handle_spawn and handle_capacity exist but are never wired. Client has capacity() method that will get 404.
- **Remediation:** Register with 501 response or remove until implemented.

#### F-053: No shell completions configured
- **Classification:** Domain-specific (D1-CLI)
- **Affected domains:** D1 (CLI)
- **Found by:** AU-01 (F013)
- **Rules:** AGENT-5
- **Description:** Click supports shell completions but they are not configured or documented.
- **Remediation:** Add completion support and document.

#### F-054: Error messages lack actionable hints
- **Classification:** Domain-specific (D1-CLI)
- **Affected domains:** D1 (CLI)
- **Found by:** AU-01 (F008)
- **Rules:** DISC-2
- **Description:** Most error messages lack remediation hints. "MINION_NETWORK_URL not set." gives no setup instructions.
- **Remediation:** Add hints to top-10 most common error paths.

### Info

#### F-055: Noun-verb CLI pattern is intentional (kubectl-style)
- **Classification:** Domain-specific (D1-CLI)
- **Affected domains:** D1 (CLI)
- **Found by:** AU-01 (F001)
- **Rules:** CMD-1
- **Description:** `minion agent register` (not `minion register agent`). Violates CLI skill letter but is consistent and intentional.
- **Remediation:** Document as intentional design decision. No change needed.

#### F-056: JSON-default CLI output is intentional (agent-first)
- **Classification:** Domain-specific (D1-CLI)
- **Affected domains:** D1 (CLI)
- **Found by:** AU-01 (F005)
- **Rules:** OUT-1
- **Description:** JSON default output inverts the skill expectation. Correct for agent-first CLI.
- **Remediation:** Document as intentional. This is a STRENGTH.

#### F-057: Network API uses stdlib http.server — AI-first API rules are aspirational
- **Classification:** Domain-specific (D7-Network)
- **Affected domains:** D7 (Network API)
- **Found by:** AU-00 (SF-09), AU-06 (full API checklist)
- **Rules:** All ROUTE-*, CONF-*, TOK-*, CLI-*, SPEC-* rules
- **Description:** Entire ai-first-api skill (37 rules) evaluated as aspirational. 26 NO ratings are expected gaps for a stdlib http.server, not defects. Migration to FastAPI would address most.
- **Remediation:** Aspirational. Consider FastAPI migration as a future project.

#### F-058: No formal pattern registry documenting codebase conventions
- **Classification:** Systemic
- **Affected domains:** All
- **Found by:** AU-10 (F009)
- **Rules:** Documentation
- **Description:** De facto patterns for logging, error handling, config, auth, output, DB access are undocumented tribal knowledge.
- **Remediation:** Create .planning/patterns.md documenting each pattern with examples.

#### F-059: Intel doc suggest loads all docs into memory
- **Classification:** Domain-specific (D5-Intel)
- **Affected domains:** D5 (Intel)
- **Found by:** AU-07 (F-08)
- **Rules:** IC-SCALE-1
- **Description:** suggest() fetchall() loads all intel_docs for keyword scoring. Fine at current scale (dozens); would be slow at 10,000+.
- **Remediation:** Document scale assumption. Consider FTS5 if doc count grows.

---

## Boundary Health Assessment

Based on boundary-dependency-map.md and findings from all audits.

### B-01: AU-00 Triage -> All Deep Dives
- **Status:** HEALTHY
- **Assessment:** Triage categories were clear. All deep dives correctly referenced systemic findings (SF-01 through SF-11) from the broad sweep. No re-scanning waste observed.

### B-02: AU-10 Cross-Cutting -> All Domain Deep Dives
- **Status:** HEALTHY
- **Assessment:** Domain deep dives correctly referenced AU-00/AU-10 systemic findings rather than re-reporting them. The resolution protocol worked: all 11 auditors flagged headers as systemic, and all referenced SF-01.

### B-03: AU-09 Tests -> All Domain Deep Dives
- **Status:** HEALTHY
- **Assessment:** Domain auditors referenced AU-09's coverage map. No redundant "no tests" findings — each domain noted its specific untested behavioral contracts.

### B-04: CLI Client <-> Network API (AU-01, AU-06)
- **Status:** HEALTHY (one mismatch)
- **Assessment:** AU-06 verified client-server contract alignment: 17/18 endpoints match perfectly. One mismatch: `capacity()` client method targets unregistered server endpoint (F-052). Client error handling is thorough. Token auth mechanism consistent on both sides.

### B-05: Crew <-> Daemon (AU-03, AU-05)
- **Status:** FRAGILE
- **Assessment:** Functional but with three concerns: (1) Config parsing duplication (F-009) — shared dataclasses but duplicated YAML parsing. (2) Concrete coupling (F-026) — crew imports daemon's load_config directly. (3) Lifecycle states are implicit — crew manages registration-level lifecycle, daemon manages process-level lifecycle. Bridge point (stand_down exit code 3) works but is undocumented as a contract. Bidirectional coupling (F-027) creates a package-level cycle.

### B-06: Task Engine <-> Database (AU-04, AU-02)
- **Status:** MOSTLY HEALTHY
- **Assessment:** tasks/ follows db/ patterns well (get_db(), parameterized queries, Row factory). One divergence: TaskDB class holds persistent connection (F-049) vs per-operation pattern. No transaction boundaries (F-006) is shared with db/ layer. Two competing task APIs exist (TaskDB class vs CRUD modules) — F-004 domain-specific.

### B-07: Daemon Config <-> Crew Config (AU-05, AU-10)
- **Status:** RESOLVED (partial)
- **Assessment:** Dataclass sharing resolved (daemon imports from crew). Parsing duplication remains (F-009). Both AU-05 and AU-10 assigned consistent severity (Major for DRY). Both recommend same fix (shared parsing function).

### Skill Overlap Consistency Check

| Overlap | Consistent? | Notes |
|---------|-------------|-------|
| S-01: IC-HDR (Comment Headers) | YES | All 11 auditors flagged, all referenced SF-01. Reported once in F-003. |
| S-02: PP-DRY-1 (Config duplication) | YES | AU-03, AU-05, AU-10 all assigned Major. Same remediation. |
| S-03: CS-ERR-1-5 (Error Handling) | YES | AU-04, AU-05, AU-06, AU-10 all identified the two-pattern duality. Consistent Major severity. |
| S-04: PP-DECOUPLE-5 (Config Externalized) | YES | AU-01, AU-08, AU-10 all identified. AU-01 noted CLI layer is clean; scatter is in business logic. |
| S-05: CA-TEST (Test Architecture) | YES | AU-09 owns test findings. Domain auditors reference coverage map without duplicating. |
