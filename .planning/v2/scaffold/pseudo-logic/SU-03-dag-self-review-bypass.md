# SU-03 Pseudo-Logic: DAG Self-Review Bypass Prevention

## File: `src/minion/tasks/update_task.py` — `complete_phase()`

### Change location: after class eligibility check (~line 167), before DAG transition (~line 170)

```python
# --- SU-03: Self-review bypass prevention ---
# DECISION: Review stages are stages where eligible workers are reviewer classes
# DECISION: Lead class bypasses this check (trusted to self-review when necessary)

# Step 1: Determine if current stage is a review stage
#   - Get flow definition for this task's flow_type
#   - Get current stage from flow
#   - If stage.workers specifies only reviewer classes -> it's a review stage
#   - If not a review stage -> skip this check entirely

# Step 2: Identify the implementer
#   - Walk backward in flow to find the implementation stage (non-review predecessor)
#   - Query: SELECT agent_name FROM transition_log
#            WHERE task_id = ? AND to_status = <implementation_stage>
#            ORDER BY timestamp DESC LIMIT 1
#   - If no result -> skip check, log warning "No implementer found in transition_log"

# Step 3: Compare
#   - If agent_name == implementer AND agent_class != "lead":
#       return {"error": "BLOCKED: Agent '<name>' implemented this task and cannot self-review."}
#   - Else: proceed to existing DAG transition logic

# Edge cases:
#   - No transition_log entry: allow with warning (manual status set)
#   - Multiple implementers: most recent wins (ORDER BY timestamp DESC LIMIT 1)
#   - Lead override: skip check entirely for lead class
#   - Task with no flow: skip check (no review stages)
#   - Skipped stages: walk further back in flow past skipped stages
```

### Coordination with SU-21:
Both SU-03 and SU-21 add checks to `complete_phase()`. They are additive (AND):
- SU-03 check fires on REVIEW stages (blocking self-review)
- SU-21 check fires on SCAFFOLDING stages (blocking without stubs)
- Neither conflicts — different stage types trigger different checks
