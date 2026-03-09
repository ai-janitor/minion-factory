# Test Coverage Survey

## Summary
- 20 files (19 test + 1 __init__), 4,187 lines, 224 test functions
- No conftest.py — fixtures duplicated per file
- No pytest markers — no unit/integration/smoke separation
- Flat tests/ directory — no subdirectories
- Zero use of mocks — all real DB, real filesystem, temp directories for isolation

## Packages WITH Test Coverage

| Source Package | Test File(s) | Depth |
|---|---|---|
| backlog | test_backlog.py (60 functions) | Deep |
| cli | test_cli.py, test_entrypoint.py | Surface (registration only) |
| comms | test_register_crew.py | Partial (register only) |
| crew | test_get_agent_prompt.py, test_register_crew.py | Partial |
| daemon.contracts | test_contracts.py | Deep |
| db | test_register_agent_db.py, test_flow_type.py | Moderate |
| network | test_network_api_route_integrity.py | Structural only |
| requirements | test_requirements.py + 4 others | Deep |
| tasks | test_task_done.py + 4 others | Deep |
| warroom | test_warroom.py | Moderate |

## Packages with ZERO Behavioral Test Coverage (17)

api, auth, dashboard, defaults, filesafety, flow_bridge, fs, intel, lifecycle, missions, monitoring, output, polling, prompts, providers, triggers, cli_schema

8 of these have import-smoke-only coverage in test_imports.py.

## Test Naming
- Mostly good: test_<scenario>_<expected_result> pattern
- Weak: test_all_options, test_by_file_path, test_dag_smoke (single mega-tests)

## Test Categories (inferred, no markers)
- Unit (~70): pure logic, no DB/filesystem
- Integration (~140): DB + filesystem + CLI
- Smoke/E2E (~20): full lifecycle walks

## Key Gap: No conftest.py
Common patterns (isolated_db, CliRunner setup) duplicated across 11 files.
