# SU-02 Pseudo-Logic: Verify Implemented Requirements

## Test-only — no production code changes

### Per-feature test logic:

**1.3 — Poll path resolution:**
```
setup: create tmp_dir/sub/deep/ with tmp_dir/.work/minion.db
test_walk_up: cd to deep/, call resolve_db_path(), assert returns tmp_dir/.work/minion.db
test_no_db: cd to /tmp/empty/, call resolve_db_path(), assert returns None
```

**1.4 — Global heartbeat:**
```
setup: create coordinator DB
test_touch: call touch_coordinator_activity("test-agent"), query coordinator DB, assert last_seen is recent
test_create: call touch without prior registration, assert agent entry created
```

**1.8 — Promote null validation:**
```
setup: create backlog item with valid file_path
test_promote: call promote(), assert result["promoted_to"] is not None/empty
test_edge_path: promote with trailing slash, nested path — assert slug is valid
```

**2.2 — Pruning:**
```
setup: insert records with timestamp > 30 days ago into messages, transition_log, invocation_log
test_prune_old: call prune_old_records(), assert old records deleted
test_keep_recent: insert records from today, prune, assert they survive
```

**2.3 — Log rotation:**
```
setup: create stream.jsonl, write data exceeding max size
test_rotate: trigger rotation, assert .1 backup exists, new file created
```

**2.5 — State machines:**
```
test_valid: validate_transition("idle", "running", "daemon") -> True
test_invalid: validate_transition("idle", "stopped", "daemon") -> raises InvalidTransition
test_reachable: all states in DAEMON_TRANSITIONS are reachable from initial state
```

**2.8 — Message types:**
```
test_valid_types: for each in VALID_MSG_TYPES, send() succeeds
test_invalid: send(msg_type="garbage") -> rejected with error
```

**5.3.3 — Remediation hints:**
```
test_hint: trigger "not registered" error, assert output contains hint text
test_no_hint: trigger unknown error, assert no crash, no hint
```

**5.3.4 — Fuzzy matching:**
```
test_fuzzy: invoke CLI with "statsu", assert output suggests "status"
```

**5.4.1 — Auth scope:**
```
test_has_scope: agent with sys scope, require_scope("sys") passes
test_lacks_scope: agent without sys scope, require_scope("sys") blocks
```

**5.4.3 — Cycle detection:**
```
test_cycle: flow YAML with A->B->A cycle, _detect_cycles() raises error
test_no_cycle: valid flow YAML, loads without error
```
