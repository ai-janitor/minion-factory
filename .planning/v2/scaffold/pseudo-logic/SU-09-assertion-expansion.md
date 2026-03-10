# SU-09 Pseudo-Logic: Contract and Assertion Expansion

## Pattern (applied uniformly across all target files):

```python
# At function entry for every public function in target modules:

def example_function(agent_name: str, task_id: int, data: dict | None = None):
    # --- Preconditions ---
    assert agent_name, "agent_name must not be empty"
    assert isinstance(task_id, int) and task_id > 0, f"task_id must be positive int, got {task_id}"
    if data is not None:
        assert isinstance(data, dict), f"data must be dict, got {type(data)}"

    # ... existing function body ...

    # --- Postcondition (where applicable) ---
    assert result is not None, "expected non-None result"
    return result
```

## Per-file application:

### Tier 1 — db/agents.py
```
# Every public function: register_agent, deregister_agent, get_agent, update_agent, list_agents
# Precondition: assert agent_name (non-empty string) on all functions that take it
# Precondition: assert agent_class in VALID_CLASSES where applicable
```

### Tier 2 — crew/spawn.py
```
# spawn_agent: assert crew_yaml is dict, agent_name non-empty, class is valid string
# Functions taking agent specs: assert spec is dict with required keys
```

### Tier 3 — lifecycle.py
```
# cold_start: assert agent_name non-empty
# fenix_down: assert agent_name non-empty, assert context is not None
# refresh: assert agent_name non-empty
```

### Tier 4 — comms/inbox.py
```
# check_inbox: assert agent_name non-empty
# Already has assertions in send.py — verify completeness
```

### Tier 5 — tasks/create_task.py, close_task.py
```
# create: assert title non-empty, assert flow_type is valid string
# close: assert task_id is positive int
```

### NOT adding assertions to:
- CLI command handlers (Click handles validation)
- Test code
- Private helper functions (assert at the public boundary instead)
