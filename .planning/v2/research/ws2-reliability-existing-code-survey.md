# Research: WS2 Reliability — Existing Code Survey

## 2.1 Bare Exception Cleanup
- **Current state:** 87 `except Exception` blocks across the codebase (down from 103 in v1 audit). Some narrowing has occurred during v1 remediation.
- **Work needed:** Continue narrowing each to specific exception types. Priority: daemon, polling, comms modules.

## 2.2 Data Lifecycle Management
- **File:** `src/minion/db/prune.py`
- **Status:** IMPLEMENTED. `prune_old_records()` handles messages, transition_log, invocation_log, compaction_log, and broadcast_reads. CLI command `minion db prune` exists. Configurable max_age_days with default 30.
- **Work needed:** None for basic pruning. Consider auto-prune at startup or on schedule for long-running sessions.

## 2.3 Unbounded Log Files
- **File:** `src/minion/daemon/runner/_execution.py` (line 32-43)
- **Status:** IMPLEMENTED. Stream.jsonl rotation exists — rotates when file exceeds max size, renames to `.stream.jsonl.1`.
- **Work needed:** Verify rotation is triggered correctly. Check if `.log` files (not just `.jsonl`) are also rotated.

## 2.4 Contracts and Assertions
- **Current state:** 45 assertions in production code (up from 5 in v1 audit). Added during v1 remediation in polling.py, comms/send.py, tasks/update_task.py, db/prune.py, state_machines.py.
- **Work needed:** Continue adding precondition/postcondition assertions to remaining critical interfaces (db/agents.py, crew/spawn.py, lifecycle.py).

## 2.5 Formal State Machines
- **File:** `src/minion/state_machines.py`
- **Status:** IMPLEMENTED. DAEMON_TRANSITIONS and AGENT_STATUS_TRANSITIONS defined with validate_transition() and transition() functions. InvalidTransition exception class exists.
- **Work needed:** Verify these are wired into all state-changing code paths (daemon runner, agent registration, status updates).

## 2.6 Assumption Documentation
- **Status:** PARTIALLY DONE. Some files now have ASSUMPTION comments (daemon constants, HP calculations). Not systematic.
- **Work needed:** Audit files with magic numbers and add ASSUMPTION comments where missing.

## 2.7 Big-O Documentation
- **Status:** PARTIALLY DONE. dag.py, polling.py, gates.py have Big-O comments on key methods. rollup.py needs verification.
- **Work needed:** Add Big-O to remaining hot paths.

## 2.8 Message Type Taxonomy
- **File:** `src/minion/comms/send.py` (line 32)
- **Status:** IMPLEMENTED. VALID_MSG_TYPES = {"order", "sitrep", "query", "response", "alert", "system"}. Both send() and the DB schema support msg_type. CLI exposes --msg-type option.
- **Work needed:** None for taxonomy definition. Could add filtering by msg_type in check-inbox and list-history.

## 2.9 Pattern Registry
- **Status:** NOT IMPLEMENTED. No pattern-registry.md or equivalent exists.
- **Work needed:** Create `.work/pattern-registry.md` documenting conventions for error handling, logging, DB access, config loading.
