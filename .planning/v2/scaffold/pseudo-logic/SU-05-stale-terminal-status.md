# SU-05 Pseudo-Logic: Stale Status Terminal Classification

## File: `src/minion/tasks/dag.py` — line 14

```python
# BEFORE:
# TERMINAL_STATUSES = frozenset({"closed", "abandoned", "obsolete", "completed"})
# AFTER:
TERMINAL_STATUSES = frozenset({"closed", "abandoned", "obsolete", "completed", "stale"})
```

## File: `src/minion/tasks/rollup.py`

### In `_rollup_task_to_requirement()` and `_rollup_requirement_to_parent()`:

```python
# Current logic: if all siblings in TERMINAL_STATUSES -> trigger rollup
# Adding "stale" means stale children no longer block rollup.
#
# New rollup status determination logic:
#   children_statuses = [row["status"] for row in siblings]
#
#   IF all(s == "stale" for s in children_statuses):
#       parent_new_status = "stale"  # all work abandoned -> propagate stale
#   ELIF all(s in TERMINAL_STATUSES for s in children_statuses):
#       # Mix of terminal statuses. Pick the "best" outcome:
#       IF "closed" in children_statuses or "completed" in children_statuses:
#           parent_new_status = "completed"  # some work was done
#       ELSE:
#           parent_new_status = "abandoned"  # only abandoned/obsolete/stale
#   ELSE:
#       # Non-terminal children still active — no rollup
#       pass
```

## File: `src/minion/state_machines.py`

```python
# Verify task status transitions include:
#   "assigned" -> "stale"     (agent went silent)
#   "in_progress" -> "stale"  (agent went silent mid-work)
#   "blocked" -> "stale"      (block never resolved)
#
# Ensure NO transitions OUT of stale:
#   "stale" -> X  should not exist for any X
#   stale is terminal — once stale, stays stale
#
# IF state_machines.py only covers daemon/agent (not task statuses):
#   No changes needed — the TERMINAL_STATUSES constant in dag.py is sufficient
```
