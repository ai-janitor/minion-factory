# Research: WS1 Correctness — Existing Code Survey

## 1.1 DAG Self-Review Bypass
- **File:** `src/minion/tasks/update_task.py` (complete_phase function, line 128)
- **Status:** NOT IMPLEMENTED. complete_phase checks agent class eligibility for the current stage but does NOT check whether the completing agent was the one who implemented the task. No self-review prevention exists.
- **Work needed:** Add check comparing `agent_name` to the agent who worked the previous stage (query transition_log for the last implementer). Block if same agent tries to advance through qe/verify.

## 1.2 Global Comms Delivery Failure
- **File:** `src/minion/comms/delivery.py` (route_cross_repo)
- **Status:** PARTIALLY ADDRESSED. The send code checks if target exists in coordinator DB and provides clear error messages. However, the original issue about missing tables in foreign project DBs during `-C` send may still exist.
- **Work needed:** Verify that `route_cross_repo` handles missing messages table in target project DB (create on demand or error clearly).

## 1.3 Poll Path Resolution
- **File:** `src/minion/defaults.py` (resolve_db_path, line 70)
- **Status:** IMPLEMENTED. Walk-up logic exists — starts from cwd, walks up parent directories looking for `.work/minion.db`. This was added in v1 remediation.
- **Work needed:** None — verify test coverage.

## 1.4 Global Agent Heartbeat
- **File:** `src/minion/polling.py` (poll_loop, line 330)
- **Status:** IMPLEMENTED. `touch_coordinator_activity(agent)` is called on poll start and periodically (every 30 min). The coordinator DB gets heartbeats.
- **Work needed:** None — verify test coverage for heartbeat behavior.

## 1.5 Stale Status Terminal Classification
- **File:** `src/minion/tasks/dag.py` (line 14)
- **Status:** NOT FIXED. `TERMINAL_STATUSES = frozenset({"closed", "abandoned", "obsolete", "completed"})` — `stale` is NOT included.
- **Work needed:** Add `"stale"` to TERMINAL_STATUSES. Verify rollup.py and gates.py behavior after the change.

## 1.6 Terminal Agent Poll Determinism
- **File:** `src/minion/polling.py`, scripts/poll-on-stop.sh
- **Status:** PARTIALLY ADDRESSED. The Stop hook mechanism exists (documented in CLAUDE.md) — checks inbox on agent stop, blocks if messages waiting. But the core issue (agents forgetting to poll after work) still relies on prompt discipline.
- **Work needed:** Verify Stop hook is installed correctly. May need mechanical enforcement beyond the hook — e.g., poll auto-restart in the daemon runner.

## 1.7 Backlog Lineage Linkage
- **File:** `src/minion/backlog/promote.py`
- **Status:** PARTIALLY IMPLEMENTED. promote() logs to transition_log (line 203) and sets promoted_to on the backlog row. But `requirement_id` on tasks created from promoted backlog items may not be consistently set — depends on downstream task creation workflow.
- **Work needed:** Verify that when tasks are created for a promoted backlog item, they carry the requirement_id from the registered requirement.

## 1.8 Backlog Promote Null Validation
- **File:** `src/minion/backlog/promote.py`
- **Status:** IMPLEMENTED. The promote function derives promoted_to from slug and origin — it cannot be null because slug defaults to the last segment of file_path (line 171). The promoted_to is always set to `req_rel_path`.
- **Work needed:** Verify there are no other code paths that set promoted_to to null.

## 1.9 Backlog Auth on Cross-Project Mutations
- **File:** `src/minion/backlog/promote.py`, `src/minion/cli/backlog_cmds.py`
- **Status:** PARTIALLY IMPLEMENTED. promote() has auth gate checking agent class = lead (line 127-133). But other backlog mutations (add, update, close) via `-C` flag may not have similar checks.
- **Work needed:** Audit all backlog write operations for auth checks when using `-C` flag.

## 1.10 Test Promote Crew Display
- **File:** `src/minion/backlog/promote.py`, `tests/test_backlog.py`
- **Status:** IMPLEMENTED in code — promote returns `required_crew` and `available_characters`. Test coverage needs verification.
- **Work needed:** Write test verifying crew display in promote output.
