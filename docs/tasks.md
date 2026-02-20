# Tasks & DAG Flow

Tasks flow through stages defined in YAML. The DAG engine decides who works each stage and what happens on pass/fail.

## Task Lifecycle

```
create-task → assign-task → pull-task → update-task → submit-result → complete-task
                                                                          │
                                                              ┌───────────┴───────────┐
                                                              │                       │
                                                         DAG: pass              DAG: fail
                                                              │                       │
                                                         next stage            fail stage
                                                      (maybe new class)    (back to previous)
                                                              │                       │
                                                         close-task              reassign
```

## Commands

### Create (lead only)

```bash
minion create-task --agent leo --title "Fix login bug" \
  --task-file /path/to/spec.md \
  --project backend --zone auth \
  --class-required coder --type bugfix \
  --blocked-by "1,2"
```

### Assign (lead only)

```bash
minion assign-task --agent leo --task-id 5 --assigned-to alice
```

### Pull (any agent)

Atomically claims a task + reads the task_file:

```bash
minion pull-task --agent alice --task-id 5
```

Race-safe — if two agents pull simultaneously, only one wins.

### Update Progress

```bash
minion update-task --agent alice --task-id 5 \
  --status in_progress --files "src/auth.py" --progress "50%"
```

### Submit Result

Attach a result file before completing:

```bash
minion submit-result --agent alice --task-id 5 --result-file /path/result.md
```

### Complete (DAG-routed)

```bash
minion complete-task --agent alice --task-id 5         # pass path
minion complete-task --agent alice --task-id 5 --failed # fail path
```

The DAG decides:
- **Pass** → next stage (e.g., `in_progress` → `fixed`)
- **Fail** → fail stage (e.g., `verified` → `assigned` for rework)
- If next stage needs a different class → task is unassigned for a new agent to pull

### Close (lead only)

```bash
minion close-task --agent leo --task-id 5
```

### Query

```bash
minion get-tasks --status open --project backend --assigned-to alice
minion get-task --task-id 5
minion task-lineage --task-id 5   # full history + DAG visualization
```

## YAML Task Flows

Located in `task-flows/`. Each file defines a pipeline.

### Base Flow (`_base.yaml`)

```
open → assigned → in_progress → fixed → verified → closed
```

### Flow Structure

```yaml
name: bugfix
inherits: _base
description: Full pipeline with code review
stages:
  in_progress:
    next: fixed
    requires: [submit_result]    # must attach result before completing
    workers: null                # current agent continues
  fixed:
    next: verified
    fail: assigned               # review rejection → back to assigned
    workers:
      default: [oracle, recon]   # reviewer must be oracle or recon class
      coder: [oracle, recon]
  verified:
    next: closed
    workers:
      default: [lead]            # only lead can close
```

### Available Flows

```bash
minion list-flows           # list all YAML flows
minion show-flow bugfix     # show stages for a flow
minion next-status bugfix open          # what's next on pass?
minion next-status bugfix fixed --failed # what's next on fail?
```

### Built-in Flows

| Flow | Description |
|------|-------------|
| `_base` | Default full pipeline |
| `bugfix` | Code review required before close |
| `feature` | Feature development pipeline |
| `hotfix` | Fast-track to production |

### Custom Flows

Create a YAML file in `task-flows/`, inherit from `_base`:

```yaml
name: my-flow
inherits: _base
stages:
  fixed:
    next: closed       # skip verification, go straight to close
    workers:
      default: [lead]
```

Use with `--type my-flow` when creating tasks.

## Blocked Tasks

Tasks can depend on other tasks:

```bash
minion create-task --agent leo --title "Deploy" --task-file deploy.md --blocked-by "3,4"
```

Task won't be assignable until tasks 3 and 4 are closed.

## Activity Count

Every status change increments `activity_count`. If a task changes status more than 4 times, the system warns — the fight is dragging.

## DB Tables

```sql
tasks (id, title, task_file, project, zone, status, blocked_by,
       assigned_to, created_by, files, progress, class_required,
       task_type, activity_count, result_file, created_at, updated_at)

task_history (id, task_id, from_status, to_status, agent, timestamp)

transitions (id, task_id, from_status, to_status, agent, valid, created_at)
```
