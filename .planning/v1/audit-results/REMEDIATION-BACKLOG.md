# Remediation Backlog — v1 Audit

**Date:** 2026-03-09
**Source:** CONSOLIDATED-FINDINGS.md (62 unique findings after dedup)

---

## P0: Fix Now (Critical severity, security, correctness bugs)

| # | Finding | What To Do | Effort | Dependencies |
|---|---------|------------|--------|--------------|
| R-001 | F-004-C: Halt detection bug — wrong column name | Change `read = 0` to `read_flag = 0` in daemon/runner/_db.py:180. Add logging to the except block on line 188. Add test. | S | None |
| R-002 | F-003-C: No Content-Length limit (DoS) | Add `MAX_BODY_SIZE = 10 * 1024 * 1024` check in server.py `_read_body()`. Return 413 if exceeded. | S | None |
| R-003 | F-011: Timing-unsafe token comparison | Replace `==` with `hmac.compare_digest()` in server.py:42 and network/auth.py:33. Import hmac. | S | None |
| R-004 | F-005-C: No input validation on /register | Define schema dict with field types, required flags, max lengths. Validate body against schema before INSERT. Return 400 with details on failure. | M | R-002 (body limit) |
| R-005 | F-007: No input validation on /send and other POST endpoints | Add max_length on message content (100KB). Add Content-Type validation. Validate required fields with type checks. | M | R-002 |

---

## P1: Fix Soon (Major architectural, high blast radius)

| # | Finding | What To Do | Effort | Dependencies |
|---|---------|------------|--------|--------------|
| R-006 | F-001: Three competing logging patterns | (a) Add `logging.basicConfig(level=logging.INFO, format=...)` in cli/main.py and daemon entrypoint. (b) Replace all `print(WARNING:...)` calls with `logger.warning()`. (c) Document convention: logging for library, click.echo for CLI output only. Target: 27+ files with print() calls. | L | None |
| R-007 | F-004: Two competing error patterns | (a) Document convention in .planning/patterns.md: dict-return for CLI-consumed, raise for internal validation. (b) Define `MinionError(Exception)` base class. (c) Add `Result = TypedDict(...)` for dict-return pattern. (d) Align TaskDB to use dict-return or mark as deprecated. | L | R-006 (logging first) |
| R-008 | F-006: No transaction boundaries | Wrap multi-statement mutations in `with conn:` in: tasks/create_task.py, tasks/close_task.py, tasks/update_task.py, tasks/done.py, tasks/complete_phase.py, tasks/db.py (TaskDB), comms/register.py (deregister), daemon/runner/_db.py. ~12 files, ~20 mutation sites. | M | None |
| R-009 | F-008: 27 direct sqlite3.connect() bypass get_db() | Extract `_connect(db_path, readonly=False)` in db/connection.py with WAL, busy_timeout, row_factory, foreign_keys. Update 10+ files across daemon, network, backlog, comms. | M | None |
| R-010 | F-009: Config parsing duplicated daemon/crew | Extract `_parse_agents(raw, cfg_path)` into crew/config.py. daemon/config.py calls it, adding daemon-specific overrides. ~100 lines deduped. | M | None |
| R-011 | F-010: backlog_cmds.py bypasses output funnel | Refactor 23 `click.echo(json.dumps(...))` calls to use `_output()`. Extract try/except ValueError wrapper for the 10 repeated error patterns. 1 file, focused change. | S | None |
| R-012 | F-012: AuthMixin defined but not wired | Wire `from minion.network.auth import check_token` into server.py. Delete inline `_check_token()`. Optionally make _Handler inherit AuthMixin. | S | R-003 (fix timing first) |
| R-013 | F-013: Terminal status sets in 3 places | Define TERMINAL_STATUSES once in dag.py or constants. Replace hardcoded sets in rollup.py, gates.py, flow_gates.py. Better: use flow.is_terminal() everywhere. | S | None |
| R-014 | F-002: 17 packages with zero tests | **Phase 1 (HIGH risk):** auth (10 tests for class/scope gates), providers (4 tests per provider for build_command), network handlers (15 tests for error paths). **Phase 2 (MEDIUM):** lifecycle (5), polling (5), missions (8). **Phase 3 (LOW):** output (3), monitoring (3), triggers (2), filesafety (3), intel (8). Total: ~75 new tests. | L | None (can start immediately) |
| R-015 | F-015: Network handler error paths untested | Write tests with invalid payloads: missing required fields, wrong types, oversized payloads, malformed JSON. ~15 tests across 8 handler modules. Part of R-014 Phase 1. | M | R-004/R-005 (fix validation first, then test it) |
| R-016 | F-003: No formal comment headers (181 files) | Semi-automated batch: generate PURPOSE/RESPONSIBILITIES/NOT RESPONSIBLE/DEPENDENCIES headers from existing docstrings. network/auth.py is the template. 181 files, ~2 minutes per file. | L | None (mechanical, can be parallelized) |
| R-017 | F-016: Unbounded file reads | Add MAX_DOC_SIZE (10MB) constant. Add size check to: intel/read_doc.py, intel/_frontmatter.py, war_plan.py, fs.read_content_file(), network handler file reads, prompt loaders. ~10 files. | M | None |

---

## P2: Fix Next (Moderate, localized fixes)

| # | Finding | What To Do | Effort | Dependencies |
|---|---------|------------|--------|--------------|
| R-018 | F-017: No data lifecycle management | Create db/cleanup.py with retention policies: purge messages > 7 days, archive transition_log > 30 days, cap invocation_log to 1000 entries, cap raid_log. Wire into daemon periodic maintenance. | M | None |
| R-019 | F-018: Config access scattered | Add ENV_CLUSTER_TOKEN, ENV_NETWORK_URL, ENV_NETWORK_INSECURE, ENV_COMPAT_PROJECT, ENV_TS_DAEMON_DIR to defaults.py. Replace ~13 direct os.environ reads in 10 files. | S | None |
| R-020 | F-019: No contracts or assertions | Add assertions for impossible conditions in critical paths. Document preconditions in docstrings for send(), register(), claim_file(). Rename daemon/contracts.py to contract_loader.py. | M | None |
| R-021 | F-020: 103 bare except Exception blocks | Audit each block. Narrow catches where possible (sqlite3.OperationalError, FileNotFoundError, etc.). Add logging to all silent blocks. Specifically fix the 3 marginal silent blocks in daemon/_db.py and _state.py. | M | R-006 (logging setup first) |
| R-022 | F-022: Missing timeout on daemon poll subprocess | Add `timeout=60` to subprocess.run() in _polling.py:39. | S | None |
| R-023 | F-024: No message type taxonomy | Add `message_type TEXT DEFAULT 'direct'` column to messages table via migration v14. Populate at send time. Update inbox queries to filter by type. | M | None |
| R-024 | F-025: Incomplete deregister cleanup | Add inbox directory deletion to deregister(). Document cleanup scope in function docstring. | S | None |
| R-025 | F-026: Concrete coupling crew -> daemon | Extract shared config loading into crew/config.py as a public function. crew/daemon.py imports from crew/config, not daemon/config. | S | R-010 (DRY fix first) |
| R-026 | F-027: Bidirectional coupling comms <-> crew | Move crew-context-merge from comms/register.py to crew side. Crew calls register, not the other way. | M | None |
| R-027 | F-028: No conftest.py | Create tests/conftest.py with shared fixtures (isolated_db, project_dir, db_path, runner). Move helpers to tests/helpers.py. ~150 lines deduped. | S | None |
| R-028 | F-029: Verb vocabulary inconsistencies | Document canonical verbs in CLI help. Create VERB_MAP. Add aliases for backwards compat. | S | None |
| R-029 | F-030: Exit code inconsistency | Define convention in constants. Document in root --help. Standardize on sys.exit(). | S | None |
| R-030 | F-031: Unbounded stream.jsonl | Add log rotation: rename to .jsonl.1 when > 50MB. Keep last 2 rotations. | S | None |
| R-031 | F-032: _resolve_or_404 duplicated | Extract to handlers/_common.py. Update 3+ handler modules. | S | None |
| R-032 | F-033: _append_error_log duplicated | Move to BaseProvider as static method. Update codex.py and gemini.py. | S | None |
| R-033 | F-034: No pytest markers | Add @pytest.mark.unit, @pytest.mark.integration, @pytest.mark.smoke. Register in pyproject.toml. | S | None |
| R-034 | F-037: Role prompt self-service block duplicated | Extract common blocks into roles/_common/base.md. Update load_role_prompt() to inject. | S | None |
| R-035 | F-038: db/ imports from auth (dependency violation) | Move CLASS_STALENESS_SECONDS and TRIGGER_WORDS to shared constants module. Update imports in db/agents.py, db/messages.py, auth.py. | S | None |
| R-036 | F-039: DBMixin connect pattern repeated 10 times | Extract _with_db(self, fn) context manager in daemon/runner/_db.py. | S | R-009 (centralize connections first) |
| R-037 | F-035/F-036: No formal state machines | Define enums for daemon lifecycle states and agent statuses. Validate in _write_state() and set_status(). | M | None |
| R-038 | F-040: Zero tests for missions | Write tests: load_mission() happy/error, resolve_slots(), list_missions(), suggest_party(). ~8 tests. | S | None |
| R-039 | F-021: No Big-O documentation | Add complexity comments to dag.py methods, rollup.py recursion, daemon polling. | S | None |

---

## P3: Improve Later (Minor, style, low risk)

| # | Finding | What To Do | Effort | Dependencies |
|---|---------|------------|--------|--------------|
| R-040 | F-041: CLI options lack short flags | Add -a (agent), -t (task-id), -n (name), -s (status) for top-20 most-used options. | S | None |
| R-041 | F-042: Top-level command leaks | Move deregister, rename, interrupt, resume to groups. Add hidden root aliases. | S | None |
| R-042 | F-043: No fuzzy matching | Install click-didyoumean plugin. | S | None |
| R-043 | F-044: Interactive getpass fallback | Guard with sys.stdin.isatty(). Add --token flag. | S | None |
| R-044 | F-045/F-046: Daemon WAL and row_factory inconsistency | Add WAL pragma and row_factory to daemon connection helper. | S | R-009 |
| R-045 | F-047: Task files import private _tmux | Extract tmux notification behind interface. | S | None |
| R-046 | F-048: No cycle detection at flow YAML load time | Add acyclic graph check in _validate(). | S | None |
| R-047 | F-049: TaskDB persistent connection leak | Add __enter__/__exit__ or close() to TaskDB. | S | None |
| R-048 | F-050: Bare except in intel auto-link | Change to except sqlite3.IntegrityError. Add debug logging. | S | None |
| R-049 | F-051: Provider error classifiers share pattern | Extract template method in BaseProvider. | S | R-032 |
| R-050 | F-052: Scaling endpoints unreachable | Register with 501 or remove. | S | None |
| R-051 | F-053: No shell completions | Configure Click completions. Document. | S | None |
| R-052 | F-054: Error messages lack hints | Add remediation hints to top-10 error paths. | S | None |
| R-053 | F-058: No pattern registry | Create .planning/patterns.md documenting conventions. | S | R-006, R-007 (establish patterns first) |
| R-054 | F-012 (systemic): No assumptions documented | Add ASSUMPTION comments to key files (daemon constants, HP calculations, token estimates). | S | None |

---

## Effort Summary

| Priority | Items | S | M | L |
|----------|-------|---|---|---|
| P0 | 5 | 3 | 2 | 0 |
| P1 | 12 | 4 | 4 | 4 |
| P2 | 22 | 14 | 7 | 1 |
| P3 | 15 | 15 | 0 | 0 |
| **Total** | **54** | **36** | **13** | **5** |

### Recommended Execution Order

**Week 1 — P0 (all 5 items):**
R-001 (halt bug), R-002 (body limit), R-003 (timing attack), R-004 (register validation), R-005 (send validation)

**Week 2 — P1 Foundation:**
R-011 (backlog output), R-012 (auth wiring), R-013 (terminal statuses), R-009 (centralize DB connections), R-010 (config DRY)

**Week 3 — P1 Logging/Error Patterns:**
R-006 (logging strategy), R-007 (error convention), R-008 (transactions)

**Week 4 — P1 Tests + Headers:**
R-014 Phase 1 (auth, providers, network handler tests), R-015 (handler error tests), R-027 (conftest.py)

**Ongoing — P2/P3:**
Pick from backlog based on what's being touched. R-016 (headers) can be done incrementally per-file when touching any module.
