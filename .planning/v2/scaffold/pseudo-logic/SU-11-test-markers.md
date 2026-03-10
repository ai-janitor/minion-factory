# SU-11 Pseudo-Logic: Test Markers, Fixtures, Conftest

## File: `pyproject.toml`

```toml
# Add under [tool.pytest.ini_options]:
markers = [
    "unit: Fast isolated tests with no external dependencies",
    "integration: Tests that use real DB, filesystem, or subprocess",
    "smoke: End-to-end multi-agent scenario tests",
]
```

## All test files (~36):

```python
# Classification logic for each file:
#
# IF file tests pure logic (data transforms, string operations, no DB/fs):
#     pytestmark = pytest.mark.unit
#     Example: test_contracts.py, test_imports.py, test_exceptions_behavioral.py
#
# IF file uses DB, filesystem, subprocess, or CLI runner:
#     pytestmark = pytest.mark.integration
#     Example: test_backlog.py, test_comms_behavioral.py, test_dag_smoke.py
#
# IF file runs multi-agent scenarios or end-to-end workflows:
#     pytestmark = pytest.mark.smoke
#     Example: test_multi_agent_smoke.py
#
# IF file has MIXED test types:
#     Use per-function decorators instead of module-level:
#     @pytest.mark.unit
#     def test_pure_logic(): ...
#     @pytest.mark.integration
#     def test_with_db(): ...
```

### Classification of existing test files:

| File | Category |
|------|----------|
| test_auth_behavioral.py | integration (checks env vars, class loading) |
| test_backlog.py | integration (DB operations) |
| test_cli.py | integration (CLI runner) |
| test_comms_behavioral.py | integration (DB + filesystem) |
| test_contracts.py | unit (assertions only) |
| test_dag_smoke.py | integration (DB + flow loading) |
| test_data_lifecycle_prune_and_stream_rotation.py | integration (DB + filesystem) |
| test_defaults_behavioral.py | unit (env var logic) |
| test_entrypoint.py | integration (subprocess) |
| test_exceptions_behavioral.py | unit (exception classes) |
| test_filesafety_behavioral.py | integration (filesystem) |
| test_flow_type.py | unit (data structures) |
| test_fs_behavioral.py | integration (filesystem) |
| test_get_agent_prompt.py | integration (reads files) |
| test_imports.py | unit (import checks) |
| test_intel_behavioral.py | integration (DB + filesystem) |
| test_lifecycle_behavioral.py | integration (DB) |
| test_lite_flow.py | unit (flow logic) |
| test_message_type_taxonomy.py | unit (constant checks) |
| test_missions_behavioral.py | integration (YAML loading) |
| test_missions_loader_resolver_party.py | integration (YAML + DB) |
| test_monitoring_behavioral.py | unit (HP calculations) |
| test_multi_agent_smoke.py | smoke (multi-agent) |
| test_network_api_route_integrity.py | integration (HTTP) |
| test_network_handler_error_paths.py | integration (HTTP) |
| test_network_handlers_behavioral.py | integration (HTTP) |
| test_output_behavioral.py | unit (formatting) |
| test_polling_behavioral.py | integration (DB + PID files) |
| test_providers_behavioral.py | unit (mock providers) |
| test_register_agent_db.py | integration (DB) |
| test_register_crew.py | integration (DB + YAML) |
| test_req_decompose_inline.py | integration (DB) |
| test_requirements.py | integration (DB) |
| test_skip_stage.py | integration (DB + flow) |
| test_state_machines_daemon_and_agent.py | unit (state logic) |
| test_task_done.py | integration (DB) |
| test_task_result.py | integration (DB) |
| test_triggers_behavioral.py | unit (trigger matching) |
| test_warroom.py | integration (filesystem) |

## conftest.py verification:

```
# For each test file: check if it creates its own DB connection
# grep for "sqlite3.connect" or "get_db()" in test files
# If found outside conftest.py: refactor to use isolated_db fixture
# If fixture doesn't cover the case: extend conftest.py
```
