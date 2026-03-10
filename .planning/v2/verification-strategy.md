# Verification Strategy — v2

## Per-DAG-Stage Artifacts

Each DAG stage produces evidence that work was done correctly. These artifacts are
checkable by automated gates (SU-21) and audit tools.

| Stage | Artifact | Verification |
|-------|----------|-------------|
| open | `spec.md` in task dir | File exists, non-empty |
| assigned | `file_claims` table entries | Agent claimed files for this task |
| scaffolding | Listed files exist on disk | SU-21 enforces: all stub files present |
| in_progress | Git diff shows changes | Claimed files modified since assignment |
| fixed | `result.md` in task dir | Result file submitted |
| qe | `test-report.md` in task dir | QE wrote findings |
| verify | `review.md` in task dir | Reviewer wrote verdict |
| closed | `transition_log` complete | All stage transitions recorded |

## Test Coverage Strategy

| Source Module Group | Test File | Coverage Level |
|---------------------|-----------|---------------|
| db/ (connection, agents, prune, migrations) | test_register_agent_db, test_data_lifecycle | Good |
| comms/ (send, inbox, register, delivery, routing) | test_comms_behavioral | Good |
| tasks/ (create, update, close, pull, dag, rollup, gates) | test_dag_smoke, test_task_done, test_task_result, test_skip_stage | Good |
| lifecycle (cold_start, refresh, fenix_down) | test_lifecycle_behavioral | Good |
| polling | test_polling_behavioral | Good |
| auth | test_auth_behavioral | Good |
| backlog/ | test_backlog | Good |
| requirements/ | test_requirements, test_req_decompose_inline | Good |
| intel/ | test_intel_behavioral | Partial — add_doc/find_doc tested |
| network/ | test_network_api_route_integrity, test_network_handlers_behavioral | Good |
| providers/ | test_providers_behavioral | Partial — error classification untested |
| dashboard/ | (none dedicated) | Gap — needs test_dashboard |
| warroom | test_warroom | Good |
| triggers | test_triggers_behavioral | Good |
| fs | test_fs_behavioral | Good |
| filesafety | test_filesafety_behavioral | Good |
| state_machines | test_state_machines_daemon_and_agent | Good |
| missions/ | test_missions_behavioral, test_missions_loader_resolver_party | Good |

## Gaps Addressed

- SU-02 added 18 verification tests for 11 implemented features
- SU-12 adds coverage for providers error classification and dashboard queries
- All new test files use markers (SU-11)
