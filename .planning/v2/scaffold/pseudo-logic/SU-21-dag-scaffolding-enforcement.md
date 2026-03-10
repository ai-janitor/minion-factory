# SU-21 Pseudo-Logic: DAG Scaffolding Enforcement

## MODIFY: src/minion/tasks/update_task.py — in `complete_phase()`

### Location: after SU-03's self-review check, before DAG transition

```python
# --- SU-21: Scaffolding gate enforcement ---

# Step 1: Check if current stage has gate: "scaffolding"
#   flow = _get_flow(task_row["flow_type"])
#   current_stage = flow.stage(task_row["status"])
#   IF current_stage is None OR current_stage.gate != "scaffolding":
#       SKIP this check entirely

# Step 2: Get task's file list
#   files_field = task_row.get("files", "")
#   IF not files_field or files_field.strip() == "":
#       ALLOW with warning: {"warning": "No files listed — scaffolding check skipped"}
#       PROCEED to DAG transition

# Step 3: Parse file list
#   file_paths = [f.strip() for f in files_field.split(",") if f.strip()]
#   project_root = defaults.get_project_dir()

# Step 4: Verify each file exists
#   missing = []
#   FOR path in file_paths:
#       abs_path = os.path.join(project_root, path) if not os.path.isabs(path) else path
#       IF not os.path.exists(abs_path):
#           missing.append(path)

# Step 5: Gate decision
#   IF missing AND agent_class != "lead":
#       return {"error": f"BLOCKED: Scaffolding incomplete. Missing files: {missing}"}
#   IF missing AND agent_class == "lead":
#       ALLOW with warning (lead bypass)
#   IF not missing:
#       PROCEED to DAG transition

# Optional Step 6: Comment header check
#   FOR each existing file:
#       Read first 10 lines
#       IF no comment line (starting with #, //, """, <!--):
#           Add to "missing headers" warning list
#   This is advisory, not blocking
```

## MODIFY: src/minion/tasks/dag.py

```python
# Stage dataclass already has: gate: str | None = None
# No changes needed to the dataclass.
# Document: gate="scaffolding" triggers file existence check in complete_phase()
```

## MODIFY: Flow YAML files

```yaml
# In feature flow (and any other flow with scaffolding stage):
# Add gate attribute:
scaffolding:
  description: "Create file stubs with comment headers"
  next: in_progress
  gate: scaffolding
  workers: [coder]
```

## Coordination note:
# SU-03 (self-review) and SU-21 (scaffolding) both add checks to complete_phase()
# Order in code:
#   1. Existing class eligibility check
#   2. SU-03: self-review bypass check (fires on REVIEW stages)
#   3. SU-21: scaffolding gate check (fires on SCAFFOLDING stages)
#   4. Existing DAG transition logic
# They never fire on the same stage type — no conflict.
