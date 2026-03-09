# AU-09 Tests Audit Results

**Auditor:** AU-09 (Tests Deep Dive)
**Date:** 2026-03-09
**Codebase:** minion-factory (`tests/`)
**Stats:** 20 test files, 234 test functions, 3.95s execution time, 100% pass rate

---

## Test Infrastructure

### conftest.py
**Status: ABSENT** — No shared conftest.py exists. Fixture patterns (`isolated_db`, `project_dir`, `db_path`, `runner`) are duplicated across 11 files.

### Pytest Configuration
Located in `pyproject.toml`:
```
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--junitxml=.work/test-reports/junit.xml -q"
```
JUnit XML output configured. No coverage plugin configured.

### Pytest Markers
**Status: NONE** — Only `@pytest.mark.parametrize` used (2 instances in test_contracts.py). No custom markers (unit, integration, smoke, slow).

### Test Execution
- **234 tests collected, 234 passed, 0 failed**
- **Execution time: 3.95 seconds** (all tests fast)
- **No warnings or deprecations**
- Python 3.13.12, pytest 9.0.2

### Mocking
**Zero mock/patch usage for test isolation.** All tests use real SQLite databases in temp directories. The word "mock" appears in test files only in variable/module names related to monkeypatch (which patches env vars and module attributes, not mocking objects). `monkeypatch.setattr` used in 4 files for config/path patching only.

---

## Coverage Map

| Package | Test File(s) | Functions | Happy | Edge | Error |
|---------|-------------|-----------|-------|------|-------|
| backlog | test_backlog.py | 69 | YES | YES | YES |
| tasks | test_task_done.py, test_task_result.py, test_dag_smoke.py, test_skip_stage.py, test_flow_type.py, test_multi_agent_smoke.py, test_lite_flow.py | 51 | YES | YES | YES |
| requirements | test_requirements.py, test_req_decompose_inline.py, test_lite_flow.py | 44 | YES | YES | YES |
| daemon.contracts | test_contracts.py | 24 | YES | YES | YES |
| cli (surface) | test_cli.py, test_entrypoint.py | 21 | YES | NO | NO |
| imports (smoke) | test_imports.py | 17 | YES | NO | NO |
| network (structural) | test_network_api_route_integrity.py | 8 | YES | NO | NO |
| warroom | test_warroom.py | 6 | YES | YES | NO |
| db | test_register_agent_db.py | 5 | YES | NO | YES |
| crew | test_get_agent_prompt.py, test_register_crew.py | 7 | YES | YES | YES |
| comms (partial) | test_register_crew.py | 3 | YES | NO | YES |

**Total tested: 10 packages (with varying depth)**

---

## Untested Packages (17)

These source packages have ZERO behavioral tests (some have import-only smoke coverage via test_imports.py):

| # | Package | Import Smoke? | Risk |
|---|---------|--------------|------|
| 1 | auth | YES (test_imports.py) | HIGH — gates all CLI commands via class permissions |
| 2 | providers | YES (test_imports.py) | HIGH — 4 provider implementations (claude, codex, gemini, opencode) |
| 3 | intel | NO | MEDIUM — document reading, intel storage |
| 4 | missions | NO | MEDIUM — mission resolver, loader, party spawning |
| 5 | lifecycle | YES (test_imports.py) | MEDIUM — cold-start, fenix-down, agent lifecycle |
| 6 | monitoring | YES (test_imports.py) | LOW — HP tracking |
| 7 | output | NO | LOW — JSON/human/compact formatting |
| 8 | dashboard | NO | LOW — aggregation/display |
| 9 | filesafety | YES (test_imports.py) | LOW — file claiming |
| 10 | triggers | YES (test_imports.py) | LOW — trigger word detection |
| 11 | flow_bridge | NO | LOW — bridge between task flows |
| 12 | polling | YES (test_imports.py) | MEDIUM — daemon polling loop |
| 13 | api | NO | MEDIUM — CLI commands for API management |
| 14 | defaults | NO | LOW — path resolution (indirectly tested) |
| 15 | fs | NO | LOW — filesystem helpers (indirectly tested) |
| 16 | cli_schema | NO | LOW — schema generation |
| 17 | prompts | NO | LOW — prompt template loading |

---

## Fixture Duplication Analysis

### Pattern 1: `isolated_db` fixture (6 files)
Files: test_dag_smoke.py, test_multi_agent_smoke.py, test_register_agent_db.py, test_register_crew.py, test_req_decompose_inline.py, test_skip_stage.py, test_warroom.py

All implement the same pattern:
1. Create `tmp_path / ".work"` directory
2. Set `MINION_DB_PATH` env var via monkeypatch
3. Call `reset_db_path()` + `init_db()`
4. `monkeypatch.chdir(tmp_path)`
5. Yield, then `reset_db_path()` on teardown

### Pattern 2: `project_dir` / `db_path` / `runner` fixtures (5 files)
Files: test_backlog.py, test_flow_type.py, test_lite_flow.py, test_requirements.py, test_task_done.py

All create a temp project dir with `.work/` and return paths. CliRunner instances created identically.

### Pattern 3: Helper functions duplicated across files
- `_insert_battle_plan()` — 3 nearly identical implementations (test_dag_smoke.py, test_flow_type.py, test_multi_agent_smoke.py)
- `_task_status()` — 3 identical implementations (test_dag_smoke.py, test_multi_agent_smoke.py, test_task_result.py)
- `_run()` CLI wrapper — 5 identical implementations
- `_insert_agent()` / `_insert_lead()` / `_insert_coder()` — various DB insertion helpers duplicated in test_task_done.py, test_task_result.py

### Quantification
- **7 files** duplicate the `isolated_db` fixture pattern
- **5 files** duplicate the `project_dir`/`db_path`/`runner` pattern
- **3 files** duplicate `_insert_battle_plan()`
- **3 files** duplicate `_task_status()`
- **5 files** duplicate the `_run()` CLI wrapper
- **Estimated conftest.py savings:** ~150 lines of deduplicated fixtures/helpers

---

## Filled Checklist

### Test-Driven Development (19 rules — PRIMARY)

#### Cycle Discipline

| Rule | Status | Evidence |
|------|--------|----------|
| CYC-1 | N/A | Retrospective audit — cannot verify test-first. Proxy: test quality is high for existing tests, suggesting deliberate design |
| CYC-2 | N/A | Retrospective audit — cannot verify RED phase confirmation |
| CYC-3 | N/A | Retrospective audit — cannot verify minimum code discipline. Proxy: test setups are appropriately scoped, not over-engineered |
| CYC-4 | N/A | Retrospective audit — cannot verify refactoring discipline |
| CYC-5 | N/A | Retrospective audit — cannot verify one-test-at-a-time |
| CYC-6 | YES | `pyproject.toml` configures pytest testpaths and JUnit XML output. CLAUDE.md documents `uv run pytest` as the test command. All 234 tests pass in under 4 seconds, indicating routine execution |

#### Test Quality

| Rule | Status | Evidence |
|------|--------|----------|
| QUAL-1 | YES | Tests consistently verify behavior via public APIs: `add()`, `list_items()`, `done_task()`, `create_result()`, `pull_task()`, etc. Assertions check return values, DB state, and filesystem state — not internal implementation details. No tests access private attributes or assert on call counts. Example: `test_open_task_closes_successfully` calls `done_task()` and asserts on `result["status"]`, not how the closure was implemented |
| QUAL-2 | YES | Majority follow `test_<scenario>_<expected_result>` pattern: `test_kill_sets_status_killed`, `test_skip_non_lead_agent_rejected`, `test_already_closed_returns_error`, `test_spaces_become_hyphens`. Minor exceptions: `test_all_options` (3 instances), `test_dag_smoke` (single mega-test — name could be more specific) |
| QUAL-3 | YES | AAA structure clearly visible across all test files. Example from test_task_done.py: Arrange (insert lead + task), Act (`done_task("atlas", task_id)`), Assert (`assert result["status"] == "closed"`). Some tests use setup helpers that blur Arrange, but the structure is consistent |
| QUAL-4 | YES | No observed test duplication. 234 test functions cover unique scenarios. Backlog tests (69 functions) cover distinct CRUD paths, CLI paths, promote paths, and kill/defer paths without overlap |
| QUAL-5 | YES | All 234 tests complete in 3.95 seconds. No network calls, no sleep(), no subprocess waits. SQLite in temp directories provides fast isolation. Average ~17ms per test |

#### Coverage

| Rule | Status | Evidence |
|------|--------|----------|
| COV-1 | NO | Happy path covered for 10 of 27 source packages. **17 packages have zero behavioral tests.** Critical gaps: auth (gates all commands), providers (4 implementations), lifecycle (cold-start/fenix-down), polling (daemon loop) |
| COV-2 | NO | Edge case coverage exists only in well-tested packages. backlog has strong edge coverage (69 tests including slug truncation, boundary values, duplicate detection). But 17 packages have zero edge case tests. Even tested packages like cli/ only test surface registration, not edge cases |
| COV-3 | NO | Error case coverage limited to backlog, tasks, and crew packages. backlog: invalid type, invalid priority, duplicate slug, double promote, kill non-open. tasks: already closed, nonexistent task, wrong agent class, unregistered agent. 17 packages have zero error tests. Network handlers (untrusted boundary) have zero error tests |
| COV-4 | YES | State change tests exist and are well-implemented: `test_register_agent_db_row_visible` (before/after DB state), `test_close_sets_status_in_db`, `test_promoted_status_set`, `test_kill_sets_status_killed`, DAG smoke test walks full state machine (open → assigned → in_progress → qe → fixed → verified → closed). Multi-agent smoke test verifies blocked_by dependency resolution |

#### Bug Fix Protocol

| Rule | Status | Evidence |
|------|--------|----------|
| BUG-1 | N/A | Retrospective — cannot verify bug-first-test protocol. Proxy: test_req_decompose_inline.py contains `test_decompose_sets_requirement_id_on_tasks` with comment "bug #34", suggesting at least one bug-first test exists |
| BUG-2 | N/A | Retrospective — cannot verify bug confirmation |
| BUG-3 | N/A | Retrospective — cannot verify fix verification |
| BUG-4 | N/A | Retrospective — cannot verify full suite after fix |

### Pragmatic Programmer (test-related subset)

| Rule | Status | Evidence |
|------|--------|----------|
| PP-DELIVER-3 | YES | All 234 tests pass. `uv run pytest` documented as standard command. JUnit XML output configured for CI consumption |
| PP-DELIVER-4 | N/A | Retrospective — cannot verify bug-then-test protocol. Test suite structure supports it: fast execution (3.95s), organized by domain, easy to add regression tests |
| PP-DELIVER-5 | YES (partial) | Tests exercise different states: open → assigned → in_progress → closed (full DAG walk in test_dag_smoke.py). Blocked/unblocked states tested in test_multi_agent_smoke.py. Skip stage behavior tested. However, state coverage only exists for well-tested packages |
| PP-CRAFT-4 | NO | 17 packages with zero tests indicates tests were not written first for most of the codebase. Well-tested packages (backlog: 69 tests, tasks: 51 tests) show signs of test-driven design with comprehensive coverage |

### Clean Architecture — Test Architecture

| Rule | Status | Evidence |
|------|--------|----------|
| CA-TEST-1 | YES | Tests coupled to behavior, not implementation. All assertions check public API return values, DB state via direct queries, and filesystem state. Zero mocks means tests verify real behavior. No tests inspect private attributes or internal call chains |
| CA-TEST-2 | NO | Tests in flat `tests/` directory with `test_*.py` naming. Not structured by use case (no `tests/tasks/`, `tests/comms/`, `tests/backlog/` directories). Files are named by domain (test_backlog.py, test_task_done.py) which is a partial step toward use-case organization, but physical directory structure is flat |
| CA-TEST-3 | NO | No explicit testing API layer. Tests use the same functions as production code directly (`from minion.backlog import add`, `from minion.tasks import done_task`). No test utility module providing a superset of the application API. Some test helpers exist inline (`_insert_battle_plan`, `_task_status`) but are duplicated, not centralized |
| CA-TEST-4 | NO | No explicit humble object pattern. Tests interact with real SQLite databases and real filesystem. This is a strength for behavioral testing (no mock/real divergence) but means hard-to-test components (subprocess calls in providers, network server in handlers) remain untested rather than being separated into testable logic + humble infrastructure |

---

## Findings

| # | Rule(s) | Severity | Affected | Description | Remediation |
|---|---------|----------|----------|-------------|-------------|
| F001 | COV-1, COV-2, COV-3 | **Critical** | 17 packages | 17 of 27 source packages have zero behavioral tests. auth, providers, intel, missions, lifecycle, monitoring, output, dashboard, filesafety, triggers, flow_bridge, polling, api, defaults, fs, cli_schema, prompts | Prioritize by risk: auth (HIGH), providers (HIGH), lifecycle (MEDIUM), polling (MEDIUM), missions (MEDIUM). Add at minimum happy-path tests for each |
| F002 | QUAL-4 (infra) | **Major** | 11 test files | No conftest.py — fixture duplication across 11 files. `isolated_db` pattern duplicated 7 times, `_run()` CLI wrapper duplicated 5 times, `_insert_battle_plan()` duplicated 3 times, `_task_status()` duplicated 3 times. ~150 lines of unnecessary duplication | Create `tests/conftest.py` with shared fixtures: `isolated_db`, `project_dir`, `db_path`, `runner`, `_run()`. Move common DB helpers (`_insert_battle_plan`, `_task_status`, `_insert_agent`) to `tests/helpers.py` |
| F003 | CA-TEST-2 | **Moderate** | tests/ | Flat test directory — no use-case organization. All 20 test files in single `tests/` directory. Makes it hard to run domain-specific test subsets or understand test coverage by looking at directory structure | Consider restructuring to `tests/backlog/`, `tests/tasks/`, `tests/requirements/`, `tests/network/`, etc. Low priority compared to coverage gaps |
| F004 | N/A (infra) | **Moderate** | tests/ | No pytest markers — no way to run unit tests separately from integration tests, no way to skip slow tests, no smoke test subset | Add markers: `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.smoke`. Register in pyproject.toml. Enable `--run-slow` pattern for future slow tests |
| F005 | CA-TEST-3 | **Minor** | tests/ | No centralized test utility layer. Test helpers (_insert_battle_plan, _task_status, _insert_agent, _run) are copy-pasted across files instead of being a shared testing API | Consolidate into `tests/helpers.py` or `tests/conftest.py`. Can be addressed together with F002 |
| F006 | CA-TEST-4 | **Minor** | providers/, network/ | No humble object separation for hard-to-test components. Provider subprocess calls and network HTTP server are not separated into testable-logic vs infrastructure. This is why these components have zero tests | When adding provider/network tests, consider extracting testable logic (command construction, response parsing) from infrastructure (subprocess.run, socket handling) |
| F007 | COV-3 | **Major** | network/handlers/ | Network handler error paths completely untested. 8 handler modules with ~25 body.get()/json.loads() calls process untrusted input. Zero tests verify error responses for malformed requests, missing fields, or invalid data | Add handler-level tests with invalid payloads. Cross-reference: AU-05 (Network API Security) |

---

## Strengths

1. **100% pass rate, fast execution** — All 234 tests pass in 3.95 seconds. No flaky tests, no timing-dependent tests, no network-dependent tests. This is excellent for CI and developer workflow.

2. **Behavioral testing throughout** — Tests verify behavior, not implementation. Return values, DB state, and filesystem state are checked. Zero mocks means no mock/production divergence risk. When tests pass, the real system works.

3. **Full DAG lifecycle coverage** — test_dag_smoke.py and test_multi_agent_smoke.py walk the complete task lifecycle (open → assigned → in_progress → qe → fixed → verified → closed) and multi-agent coordination (blocked_by dependency resolution). These are high-value integration tests.

4. **Strong backlog test suite** — 69 test functions covering unit tests (slugify, parse), CRUD integration (add, list, get, update), promote lifecycle, kill/defer/reopen, and CLI surface. This is a model for other packages to follow.

5. **Descriptive test names** — Majority of tests follow `test_<scenario>_<expected_result>` naming. A reader can understand what's being tested without reading the test body.

6. **Clear AAA structure** — Arrange-Act-Assert is consistently applied across all test files. Tests are readable and maintainable.

7. **Good error case coverage where tests exist** — Tested packages include error paths: invalid input, duplicate detection, wrong agent class, nonexistent entities, already-closed tasks, gate failures.

8. **Effective DB isolation** — Every test file uses tmp_path for SQLite databases. No test pollution between runs. No global state leakage (reset_db_path() in teardown).

9. **Contract validation tests** — test_contracts.py validates JSON contract structure and invariants. This is a test-as-documentation pattern that ensures contracts stay valid.

10. **State machine tests** — test_skip_stage.py, test_lite_flow.py, and test_requirements.py verify DAG state transitions including valid paths, invalid skips, fail-back paths, and gate blocking. This exercises the core domain logic thoroughly.
