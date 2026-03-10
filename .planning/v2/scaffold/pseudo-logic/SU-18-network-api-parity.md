# SU-18 Pseudo-Logic: Network API CLI Parity

## New handler pattern (same for all new endpoints):

```python
# Every new handler follows this template:
async def handle_<action>(request):
    """Handle <HTTP_METHOD> <path>.

    # 1. Parse request: JSON body for POST/PUT, query params for GET
    # 2. Validate required params
    # 3. Call core logic function (same function the CLI calls)
    # 4. Return JSON response: {"status": "ok", ...} or {"error": "..."}
    # 5. Handle exceptions: return 400/404/500 with error dict
    """
```

## NEW: src/minion/network/handlers/lifecycle.py

```python
# POST /agents/{name}/cold-start
#   -> call lifecycle.cold_start(agent_name)
#   -> return briefing dict

# POST /agents/{name}/refresh
#   -> call lifecycle.refresh(agent_name)
#   -> return state dict

# POST /agents/{name}/fenix-down
#   -> call lifecycle.fenix_down(agent_name, context_from_request_body)
#   -> return recovery dict
```

## NEW: src/minion/network/handlers/agent_context.py

```python
# PUT /agents/{name}/context
#   -> body: {"context": "...", "hp": 90}
#   -> call agent set_context logic
#   -> return updated agent dict
```

## NEW: src/minion/network/handlers/task_workflow.py

```python
# POST /tasks/{id}/complete-phase
#   -> body: {"agent_name": "...", "passed": true, "reason": "..."}
#   -> call tasks.update_task.complete_phase()
#   -> return phase result dict

# POST /tasks/{id}/result
#   -> body: {"agent_name": "...", "result": "..."}
#   -> call tasks.submit_result.submit_result()
#   -> return result dict

# POST /tasks/{id}/review
#   -> body: {"agent_name": "...", "verdict": "approve/reject", "reason": "..."}
#   -> call tasks.review.review_task()
#   -> return review dict

# POST /tasks/{id}/test
#   -> body: {"agent_name": "...", "test_output": "..."}
#   -> call tasks.test_report.submit_test_report()
#   -> return test dict
```

## NEW: src/minion/network/handlers/diagnostics.py

```python
# GET /alerts
#   -> aggregate warnings from all agents: stale agents, low HP, unread messages
#   -> return {"alerts": [...]}

# GET /db/stats
#   -> query: DB file size, row counts per table, WAL status
#   -> return {"size_bytes": N, "tables": {"agents": N, "messages": N, ...}, "wal": "enabled"}
```

## MODIFY: handlers/core.py — GET /who filtering

```python
# Add query param parsing:
#   class_filter = request.query.get("class")
#   status_filter = request.query.get("status")
#   project_filter = request.query.get("project")
#
# Build query: SELECT * FROM agents WHERE 1=1
#   IF class_filter: AND class = ?
#   IF status_filter: AND status = ?
#   IF project_filter: AND project_path = ?
```

## MODIFY: handlers/overview.py — task lineage

```python
# GET /tasks/{id}/lineage
#   -> query transition_log for task_id
#   -> return ordered list of transitions: [{"from": ..., "to": ..., "agent": ..., "timestamp": ...}]
```

## MODIFY: router.py — register all new routes

```python
# Add to route registration:
# router.add_route("POST", "/agents/{name}/cold-start", lifecycle.handle_cold_start)
# router.add_route("POST", "/agents/{name}/refresh", lifecycle.handle_refresh)
# ... etc for all new endpoints
```
