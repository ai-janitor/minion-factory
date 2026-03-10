# Stage 7 — File Map: Spec Units to Source Files

Each section maps a spec unit to the files that need modification (MODIFY) or creation (NEW).
Corrections from specs: `routes.py` is actually `router.py`, `agent-classes.yaml` does not exist (agent classes are in `src/minion/tasks/agent_classes.py`), role prompts are `.md` files in subdirs not `.py` files.

---

## Wave 0: Foundation

### SU-01: Pattern Registry — Conventions and Enforcement

| Action | File | Change Summary |
|--------|------|----------------|
| NEW | `.work/pattern-registry.md` | Create document with 9 sections: error handling, DB access, config resolution, logging, auth decoration, message delivery, contracts/assertions, documentation conventions, provider error classification. Each section has canonical pattern, code example from existing codebase, rationale, deviation guidance. |

No production code changes. Pure documentation artifact.

---

## Wave 1: Verify-Only

### SU-02: Verify Implemented Requirements — 11 Features

| Action | File | Change Summary |
|--------|------|----------------|
| NEW | `tests/test_verify_implemented_poll_path_resolution.py` | Tests for 1.3: `resolve_db_path()` walk-up from nested dirs, missing DB case |
| NEW | `tests/test_verify_implemented_heartbeat_and_pruning.py` | Tests for 1.4 (heartbeat) + 2.2 (pruning): coordinator `last_seen`, `prune_old_records()` old/recent |
| NEW | `tests/test_verify_implemented_promote_and_state.py` | Tests for 1.8 (promote null validation), 2.5 (state machines), 2.8 (message types) |
| NEW | `tests/test_verify_implemented_log_rotation.py` | Test for 2.3: stream.jsonl rotation on size threshold |
| NEW | `tests/test_verify_implemented_dx_features.py` | Tests for 5.3.3 (remediation hints), 5.3.4 (fuzzy match), 5.4.1 (auth scope), 5.4.3 (cycle detection) |

Alternative: all tests could go in a single file `tests/test_verify_implemented_11_features.py`. The split above groups by subsystem for readability. Implementer's choice.

No production code changes. Test-only.

---

## Wave 2: Correctness Fixes

### SU-03: DAG Self-Review Bypass Prevention

| Action | File | Change Summary |
|--------|------|----------------|
| MODIFY | `src/minion/tasks/update_task.py` | In `complete_phase()`: after class eligibility check, add self-review bypass validation. Query `transition_log` for last implementer. If `agent_name == implementer` on review stages, return BLOCKED error dict. Lead class bypasses check. |
| MODIFY | `tests/test_dag_smoke.py` | Add 5 tests: self-review blocked, different reviewer succeeds, no transition_log entry, lead bypass, re-implementation by different agent |

### SU-04: Global Comms Cross-Project Edge Cases

| Action | File | Change Summary |
|--------|------|----------------|
| MODIFY | `src/minion/comms/delivery.py` | In `route_cross_repo()`: (1) narrow `except Exception` on coordinator lookup to `except sqlite3.OperationalError`, (2) add `PRAGMA table_info(messages)` schema compatibility check, (3) return error dicts for common failures instead of None |
| MODIFY | `tests/test_comms_behavioral.py` | Add 5 tests: valid delivery, agent not found, stale project path, locked DB, old-schema table |

### SU-05: Stale Status Terminal Classification

| Action | File | Change Summary |
|--------|------|----------------|
| MODIFY | `src/minion/tasks/dag.py` | Add `"stale"` to `TERMINAL_STATUSES` frozenset (line 14) |
| MODIFY | `src/minion/tasks/rollup.py` | Verify rollup behavior with stale children. Add logic: if ALL children stale, parent becomes stale; if mix of stale+completed/closed, parent becomes completed/closed |
| MODIFY | `src/minion/state_machines.py` | Verify/add valid transitions INTO stale (from assigned, in_progress, blocked). Ensure NO transitions OUT of stale (terminal). |
| MODIFY | `tests/test_dag_smoke.py` | Add 5 tests: stale in TERMINAL_STATUSES, rollup with stale+closed children, no rollup with stale+in_progress, all-stale rollup, is_terminal("stale") |

### SU-06: Terminal Agent Poll Determinism Hardening

| Action | File | Change Summary |
|--------|------|----------------|
| MODIFY | `scripts/poll-on-stop.sh` | Add edge case guards: check MINION_AGENT_NAME is set, check `minion` is in PATH, 5-second timeout on inbox check, verify stop_hook_active marker resets between sessions |
| MODIFY | `src/minion/polling.py` | Add `poll_status(agent_name)` function: check PID file, PID alive, last poll heartbeat, hook installed |
| MODIFY | `src/minion/tasks/update_task.py` | After successful `complete_phase()`, include `"poll_reminder"` field in result dict |
| MODIFY | `src/minion/cli/agent_cmds.py` | Add `poll-status` CLI command wiring to `polling.poll_status()` |
| MODIFY | `src/minion/lifecycle.py` | Verify `install_hooks()` is idempotent — running twice produces same settings.json |
| MODIFY | `tests/test_polling_behavioral.py` | Add 5 tests: install-hooks idempotency, poll-on-stop with unset env, poll-on-stop with messages, poll-on-stop with missing CLI, complete_phase poll_reminder |

### SU-07: Backlog Lineage and Auth Hardening

| Action | File | Change Summary |
|--------|------|----------------|
| MODIFY | `src/minion/backlog/promote.py` | Verify `requirement_id` in return dict. If missing, add it from `register()` return value. |
| MODIFY | `src/minion/cli/backlog_cmds.py` | Add auth checks to `backlog add`, `backlog update`, `backlog close` when `-C` flag is active. Check if MINION_PROJECT_DIR differs from cwd; if so, require lead class. |
| MODIFY | `src/minion/auth.py` | Add helper function `is_cross_project() -> bool` that checks if -C flag is active |
| MODIFY | `tests/test_backlog.py` | Add 6 tests: promote returns requirement_id, task gets requirement_id, cross-project add blocked for non-lead, cross-project add succeeds for lead, promote shows crew, local add without auth |

---

## Wave 3: Reliability and Quality

### SU-08: Bare Exception Narrowing

| Action | File | Change Summary |
|--------|------|----------------|
| MODIFY | `src/minion/daemon/runner/_execution.py` | Narrow `except Exception` blocks to specific types (subprocess.SubprocessError, OSError, json.JSONDecodeError). Keep top-level loop broad catch with logging. |
| MODIFY | `src/minion/daemon/runner/_polling.py` | Narrow to sqlite3.OperationalError, OSError, KeyError |
| MODIFY | `src/minion/daemon/runner/_state.py` | Narrow to sqlite3.OperationalError, ValueError |
| MODIFY | `src/minion/daemon/runner/_stream.py` | Narrow to OSError, json.JSONDecodeError |
| MODIFY | `src/minion/daemon/runner/_alerting.py` | Narrow to sqlite3.OperationalError, OSError |
| MODIFY | `src/minion/daemon/runner/_hp.py` | Narrow to sqlite3.OperationalError, ValueError |
| MODIFY | `src/minion/daemon/runner/_db.py` | Narrow to sqlite3.OperationalError, sqlite3.IntegrityError |
| MODIFY | `src/minion/daemon/runner/_prompts.py` | Narrow to OSError, KeyError |
| MODIFY | `src/minion/daemon/runner/_watcher_mode.py` | Narrow to sqlite3.OperationalError, OSError |
| MODIFY | `src/minion/polling.py` | Narrow to sqlite3.OperationalError, OSError, KeyError, ValueError |
| MODIFY | `src/minion/comms/delivery.py` | Narrow to sqlite3.*, OSError, PermissionError |
| MODIFY | `src/minion/comms/send.py` | Narrow to sqlite3.OperationalError, OSError |
| MODIFY | `src/minion/comms/inbox.py` | Narrow to sqlite3.OperationalError, OSError |
| MODIFY | `src/minion/comms/routing.py` | Narrow to sqlite3.OperationalError |
| MODIFY | ~29 other files across `src/minion/` | Same mechanical narrowing per pattern registry. Full list determined by `grep -r "except Exception" src/minion/` at implementation time. |
| MODIFY | `tests/test_exceptions_behavioral.py` | Add tests: grep count near zero, existing tests pass, inject unexpected exception in daemon/polling/comms — verify propagation, daemon loop continues on expected exception |

### SU-09: Contract and Assertion Expansion

| Action | File | Change Summary |
|--------|------|----------------|
| MODIFY | `src/minion/db/agents.py` | Add `assert agent_name` preconditions on all public functions |
| MODIFY | `src/minion/db/connection.py` | Assert path non-empty in `connect()`, assert conn not None in `get_db()` |
| MODIFY | `src/minion/crew/spawn.py` | Assert crew YAML is dict, agent_name non-empty, class is valid |
| MODIFY | `src/minion/crew/lifecycle.py` | Assert agent_name non-empty in stand_down, retire |
| MODIFY | `src/minion/lifecycle.py` | Assert agent_name non-empty in cold_start, fenix_down, refresh |
| MODIFY | `src/minion/comms/inbox.py` | Assert agent_name non-empty in check_inbox |
| MODIFY | `src/minion/tasks/create_task.py` | Assert title non-empty, flow_type valid |
| MODIFY | `src/minion/tasks/close_task.py` | Assert task_id positive int |
| MODIFY | ~7 other files across db/, comms/, tasks/ | Same assertion pattern per pattern registry |
| MODIFY | `tests/test_contracts.py` | Add tests: empty agent_name raises AssertionError for Tier 1-5 functions, valid inputs still pass, assert count >= 80 |

### SU-10: Documentation Debt — Assumptions and Big-O

| Action | File | Change Summary |
|--------|------|----------------|
| MODIFY | `src/minion/daemon/runner/_constants.py` | Add ASSUMPTION comments to all timeout/retry/buffer constants |
| MODIFY | `src/minion/monitoring.py` | Add ASSUMPTION comments to HP thresholds, warning levels |
| MODIFY | `src/minion/polling.py` | Add ASSUMPTION comments to poll intervals, heartbeat frequency. Add Big-O to `poll_loop()`, `_collect_messages()` |
| MODIFY | `src/minion/defaults.py` | Add ASSUMPTION comments to MAX_DOC_SIZE, default paths, port numbers |
| MODIFY | `src/minion/crew/spawn.py` | Add ASSUMPTION comments to tmux pane sizes, startup delays |
| MODIFY | `src/minion/db/prune.py` | Add ASSUMPTION to max_age_days default. Verify Big-O annotation. |
| MODIFY | `src/minion/tasks/rollup.py` | Add Big-O to `_rollup_task_to_requirement()`, `_rollup_requirement_to_parent()` |
| MODIFY | `src/minion/tasks/dag.py` | Verify existing Big-O on `_resolve_skip()`, add to `valid_transitions()` |
| MODIFY | `src/minion/comms/send.py` | Add Big-O annotation to `send()` |
| MODIFY | `src/minion/tasks/gates.py` | Add Big-O to gate checking functions |

No behavior changes. Comments and docstrings only.

---

## Wave 4: Test Infrastructure

### SU-11: Test Markers, Fixtures, and Conftest Completion

| Action | File | Change Summary |
|--------|------|----------------|
| MODIFY | `pyproject.toml` | Add `[tool.pytest.ini_options] markers` section with unit, integration, smoke |
| MODIFY | `tests/conftest.py` | Verify fixture coverage. Add shared fixtures if duplication found in test files. |
| MODIFY | ALL `tests/test_*.py` (~36 files) | Add `pytestmark = pytest.mark.<category>` module-level marker. Mixed files get per-function markers. |

### SU-12: Missing Test Suites and Verification Artifacts

| Action | File | Change Summary |
|--------|------|----------------|
| NEW | `tests/test_fs_behavioral.py` | Tests for `src/minion/fs.py` public API (already exists — verify coverage or extend) |
| NEW | `tests/test_warroom.py` | Tests for `src/minion/warroom.py` (already exists — verify coverage or extend) |
| NEW | `tests/test_triggers_behavioral.py` | Tests for `src/minion/triggers.py` (already exists — verify coverage or extend) |
| NEW | `tests/test_intel_add_and_find.py` | Tests for intel/ package: add_doc, find_docs, read_doc |
| NEW | `tests/test_dashboard_render_and_queries.py` | Tests for dashboard/: render, queries |
| NEW | `tests/test_providers_error_log_and_classify.py` | Tests for providers/: shared error log, error classification |
| NEW | `.planning/v2/verification-strategy.md` | Document artifact strategy: what each DAG stage produces as evidence |

Note: several of these test files already exist (test_fs_behavioral.py, test_warroom.py, test_triggers_behavioral.py). The implementer should verify their coverage and extend rather than duplicate.

---

## Wave 5: Code Hygiene

### SU-13: Dependency Layer Violation Fixes

| Action | File | Change Summary |
|--------|------|----------------|
| MODIFY | `src/minion/db/agents.py` (or other db/*.py) | Remove any `from minion.auth import ...`. Move shared constants to defaults.py or pass as params. |
| MODIFY | `src/minion/tasks/update_task.py` (or other tasks/*.py) | If _tmux is imported directly, change to import through crew/__init__.py public API |
| MODIFY | `src/minion/comms/register.py` | Extract crew-context-merge logic to neutral location (`src/minion/lifecycle.py` or new `src/minion/agent_context.py`) |
| MODIFY | `src/minion/crew/__init__.py` | Ensure public API exports needed functions for tasks/ to import |
| POSSIBLY NEW | `src/minion/agent_context.py` | If crew-context-merge logic needs a new home outside both comms/ and crew/ |

### SU-14: Code Deduplication

| Action | File | Change Summary |
|--------|------|----------------|
| NEW | `src/minion/providers/_shared_error_log.py` | Extract `_append_error_log()` from codex.py and gemini.py into shared function |
| NEW | `src/minion/providers/_shared_error_classifier.py` | Extract error classification logic: `classify_error(status_code, error_body) -> str` |
| MODIFY | `src/minion/providers/codex.py` | Replace inline `_append_error_log()` and error classification with imports from shared modules |
| MODIFY | `src/minion/providers/gemini.py` | Same as codex.py — import shared functions |
| NEW | `src/minion/prompts/roles/_shared_self_service_block.py` | Extract common self-service block from role prompts into single function |
| MODIFY | `src/minion/prompts/roles/coder/prompt.md` | Reference shared block (or: self-service block extraction may be a Python loader change in `src/minion/prompts/roles/__init__.py` rather than .md file edits) |
| MODIFY | `src/minion/prompts/roles/__init__.py` | Load shared self-service block and inject into all role prompts at assembly time |
| MODIFY | `src/minion/db/connection.py` | Verify DBMixin dedup is complete — all DB access goes through connect()/get_db() |
| NEW | `tests/test_providers_shared_modules.py` | Tests for _shared_error_log and _shared_error_classifier |

Note: role prompts are `.md` files loaded by Python code. The dedup may involve changing the Python loader (roles/__init__.py) to inject the shared block, rather than editing each .md file.

### SU-15: CLI Consistency

| Action | File | Change Summary |
|--------|------|----------------|
| MODIFY | `src/minion/cli/main.py` | Add verb aliases (hidden) for backward compat; move root-level leaks (deregister, rename, interrupt, resume) to agent group |
| MODIFY | `src/minion/cli/agent_cmds.py` | Add `deregister`, `rename`, `interrupt`, `resume` commands in the agent group |
| MODIFY | `src/minion/cli/comms_cmds.py` | Add short flags: `-f` for --from, `-t` for --to, `-m` for --message |
| MODIFY | `src/minion/cli/task_cmds.py` | Add short flags: `-s` for --status, `-r` for --reason |
| MODIFY | `src/minion/cli/global_cmds.py` | Add short flags: `-a` for --agent, `-n` for --name, `-c` for --class |
| MODIFY | `src/minion/cli/top_level.py` | Convert root-level commands to hidden aliases with deprecation warnings |
| MODIFY | `src/minion/cli/aliases.py` | Register backward-compat aliases for moved commands |
| MODIFY | ALL `src/minion/cli/*.py` | Audit and standardize exit codes: 0=success, 1=error, 2=usage |

### SU-16: Configuration Consistency

| Action | File | Change Summary |
|--------|------|----------------|
| MODIFY | `src/minion/cli/main.py` | Update -C flag help text to mention MINION_PROJECT_DIR; add DEBUG log for env var mutation |
| MODIFY | `src/minion/defaults.py` | Verify all MINION_NETWORK_*, MINION_CLUSTER_* vars route through here. Fix any remaining direct os.environ reads. |
| MODIFY | `src/minion/db/connection.py` | Verify all sqlite3.connect calls are in connection.py only |

Primarily audit/verification. Minimal code changes expected.

### SU-17: Dead Code and Unreachable Paths

| Action | File | Change Summary |
|--------|------|----------------|
| MODIFY or DELETE | `src/minion/network/handlers/scaling.py` | Either wire to router or remove entirely. Decision documented for E-09. |
| MODIFY | `src/minion/network/router.py` | If scaling wired: register routes. If removed: remove any scaling references. |
| MODIFY | `src/minion/network/server.py` | Enable HTTP access logging at INFO level: `"<method> <path> <status_code> <duration_ms>"` |
| MODIFY | `src/minion/db/connection.py` | Add closed-connection guard: raise clear error instead of AttributeError on post-close operations |
| MODIFY | `src/minion/intel/link_doc.py` (or relevant intel/*.py) | Narrow bare `except Exception` to `except sqlite3.IntegrityError` in auto-link logic |
| AUDIT | `src/minion/` | Grep for files named utils.py, helpers.py, misc.py, common.py. Rename if found. |

---

## Wave 6: Features

### SU-18: Network API CLI Parity and Gaps

| Action | File | Change Summary |
|--------|------|----------------|
| NEW | `src/minion/network/handlers/lifecycle.py` | Handlers for cold-start, refresh, fenix-down: `POST /agents/{name}/cold-start`, `POST /agents/{name}/refresh`, `POST /agents/{name}/fenix-down` |
| NEW | `src/minion/network/handlers/agent_context.py` | Handler for set-context: `PUT /agents/{name}/context` |
| NEW | `src/minion/network/handlers/task_workflow.py` | Handlers for complete-phase, result, review, test: `POST /tasks/{id}/complete-phase`, etc. |
| NEW | `src/minion/network/handlers/diagnostics.py` | Handlers for alerts, DB stats: `GET /alerts`, `GET /db/stats` |
| MODIFY | `src/minion/network/handlers/core.py` | Add query params to `GET /who`: `?class=`, `?status=`, `?project=` filtering. Add `GET /agents/{name}/full` composite view. |
| MODIFY | `src/minion/network/handlers/overview.py` | Verify completeness. Add `GET /tasks/{id}/lineage` for DAG history. |
| MODIFY | `src/minion/network/router.py` | Register all new routes |
| MODIFY | `tests/test_network_api_route_integrity.py` | Add route integrity tests for all new endpoints |
| MODIFY | `tests/test_network_handlers_behavioral.py` | Add behavioral tests for new handlers |

### SU-19: Cross-Project Coordination

| Action | File | Change Summary |
|--------|------|----------------|
| MODIFY | `src/minion/polling.py` | Add `multi_project_poll(agent_name, project_paths) -> dict`: iterate coordinator DB, poll each project's DB, return aggregated results |
| MODIFY | `src/minion/auth.py` | Add "coordinator" to valid classes. Grant coordinator: all lead perms + cross-project capabilities. Exempt coordinator from -C backlog auth block. |
| MODIFY | `src/minion/tasks/agent_classes.py` | Add coordinator class definition with capabilities [manage, monitor, investigate, plan] and models |
| MODIFY | `src/minion/comms/send.py` | Add `sitrep_global(from_agent, to_agent, summary) -> dict`: formalized project-lead-to-sys-lead reporting via global comms |
| MODIFY | `src/minion/cli/comms_cmds.py` | Add `minion sitrep --to <lead> --scope global` CLI command |
| MODIFY | `src/minion/defaults.py` | Add `MINION_PROJECTS` env var support for fallback project path discovery |

### SU-20: Agent Experience Improvements

| Action | File | Change Summary |
|--------|------|----------------|
| MODIFY | `src/minion/lifecycle.py` | Enhance `cold_start()`: generate live briefing with current assignment, unread count, team composition, battle plan, recent raid log, HP, file claims |
| MODIFY | `src/minion/cli/main.py` | Add `completions` command group with `install` and `show` subcommands using Click's `_MINION_COMPLETE` |
| NEW | `src/minion/cli/completion_cmds.py` | Shell completion install/show commands: detect shell, generate script, append to rc file idempotently |
| NEW | `.planning/research-prompt-strategy.md` | Document prompt assembly order: role → character → scope → context injection |

### SU-21: DAG Scaffolding Enforcement

| Action | File | Change Summary |
|--------|------|----------------|
| MODIFY | `src/minion/tasks/update_task.py` | In `complete_phase()`: after SU-03's self-review check, add scaffolding gate. When current stage has `gate: "scaffolding"`, verify all listed files exist on disk. Return BLOCKED error if missing. Lead bypass. |
| MODIFY | `src/minion/tasks/dag.py` | Verify `Stage` dataclass has `gate` field (it does: `gate: str | None = None`). Document the "scaffolding" gate value. |
| MODIFY | Flow YAML files (e.g., `src/minion/tasks/*.yaml` or wherever flows are defined) | Add `gate: scaffolding` to the scaffolding stage in feature/bugfix flow definitions |
| MODIFY | `tests/test_dag_smoke.py` | Add 5 tests: scaffolding blocked without files, succeeds with files, empty files field, no scaffolding stage, lead bypass |

### SU-22: Dashboard UI Consolidation

| Action | File | Change Summary |
|--------|------|----------------|
| NEW | `src/minion/network/templates/dashboard/base.html` | Base HTML template with minimal CSS, responsive layout, auto-refresh meta tag |
| NEW | `src/minion/network/templates/dashboard/agents.html` | Agent health table: name, class, status, HP, last_seen, current task, color coding |
| NEW | `src/minion/network/templates/dashboard/tasks.html` | Kanban-style task pipeline by status with filter controls |
| NEW | `src/minion/network/templates/dashboard/health.html` | System health: DB stats, agent stats, message stats |
| NEW | `src/minion/network/templates/dashboard/messages.html` | Recent messages table with filters |
| MODIFY | `src/minion/network/dashboard.py` | Wire dashboard views to Jinja2 template rendering. Route handlers for /dashboard/* |
| MODIFY | `src/minion/dashboard/queries.py` | Add queries for agent health, task pipeline, system stats, message flow |
| MODIFY | `src/minion/dashboard/render.py` | Replace old rendering with Jinja2 template calls |
| MODIFY | `src/minion/network/router.py` | Register dashboard routes: /dashboard/, /dashboard/agents, /dashboard/tasks, /dashboard/health, /dashboard/messages |
| MODIFY | `pyproject.toml` | Add `jinja2` dependency if not already present |

---

## Summary Statistics

| Category | Count |
|----------|-------|
| Files to MODIFY | ~95 (many are the ~43 files for SU-08 bare exception narrowing) |
| Files to CREATE (new) | ~20 |
| Files to DELETE | 0-1 (scaling.py if removed) |
| Test files to CREATE | ~8 |
| Test files to MODIFY | ~40 (36 for markers + 4 for new tests) |
| Documentation artifacts | 3 (pattern-registry.md, verification-strategy.md, research-prompt-strategy.md) |
