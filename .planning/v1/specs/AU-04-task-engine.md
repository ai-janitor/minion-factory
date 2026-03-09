# AU-04: Task Engine Deep Dive

## Purpose

Line-by-line audit of the task engine — the largest package (18 files). Covers task CRUD, flow gates, DAG, rollups, and the task state machine.

## Scope

| Directory/File | Description |
|----------------|-------------|
| `src/minion/tasks/__init__.py` | Package exports |
| `src/minion/tasks/create_task.py` | Task creation |
| `src/minion/tasks/query_task.py` | Task queries |
| `src/minion/tasks/update_task.py` | Task updates |
| `src/minion/tasks/delete_task.py` | Task deletion |
| `src/minion/tasks/flow_gates_and_validation.py` | State machine gates |
| `src/minion/tasks/dag.py` | Task DAG (dependencies) |
| `src/minion/tasks/rollup.py` | Task rollup/aggregation |
| `src/minion/tasks/db.py` | Task-specific DB operations |
| `src/minion/tasks/models.py` | Task data models (if exists) |
| `src/minion/tasks/types.py` | Task types/enums (if exists) |
| Plus any other files in `src/minion/tasks/` |

Read ALL files in `src/minion/tasks/`.

## Skills to Evaluate

### CS Foundations — Consistency & State (CS-CONSIST, all 5 rules)
- **CONSIST-1:** Consistency model — task state is strong consistency (single SQLite DB)?
  - **How to check:** Verify all task operations go through one DB. Check for cross-DB task operations.
- **CONSIST-2:** Transaction boundaries — task creation with multiple inserts atomic?
  - **How to check:** Read create_task.py. Check if multi-step task creation is wrapped in a transaction.
- **CONSIST-3:** Concurrency strategy — what if two agents update the same task?
  - **How to check:** Check for optimistic locking (version column) or pessimistic locking.
- **CONSIST-4:** Idempotency — is task creation idempotent? What about duplicate task IDs?
  - **How to check:** Read create_task.py. Check for unique constraint on task ID. Check for upsert pattern.
- **CONSIST-5:** Ordering guarantees — task execution order, DAG ordering?
  - **How to check:** Read dag.py. Check topological sort. Check for ordering guarantees on task queries.

### CS Foundations — Error & Failure Modes (CS-ERR, all 5 rules)
- **ERR-1:** Failure taxonomy — what errors can occur in task operations?
  - **How to check:** Catalog all exception types and error-dict patterns in tasks/.
- **ERR-2:** Retry strategy — what if a task operation fails mid-way?
- **ERR-3:** Partial failure — what if DAG update fails but task creation succeeded?
- **ERR-4:** Degradation strategy — does task engine fail-fast or degrade?
- **ERR-5:** Observability — how are task failures logged?

### CS Foundations — Data Architecture (CS-DATA, selected rules)
- **DATA-1:** Data ownership — tasks/ owns task tables (single writer)?
- **DATA-5:** Data lifecycle — old tasks cleaned up? Archived?

### Clean Architecture (selected rules)
- **CA-DEP-1:** Dependencies inward — tasks/ should not import from cli/
- **CA-SOLID-1:** SRP — each task module has one responsibility
- **CA-COMP-1:** No cycles in task package dependency graph
- **CA-COMP-4, CA-COMP-5:** Files that change/are used together in same package

### Pragmatic Programmer (selected rules)
- **PP-CRAFT-1:** No programming by coincidence — task state transitions intentional
- **PP-CRAFT-2:** Big-O considered — DAG operations complexity
- **PP-CONTRACT-1:** Preconditions/postconditions — flow gates define contracts
- **PP-CONTRACT-2:** Crash early — invalid task state transitions fail immediately
- **PP-DRY-1:** Single authoritative representation — task states defined once

### Implementation Coding Core (selected rules)
- **IC-HDR-1 through IC-HDR-5:** File headers — reference AU-00 systemic finding
- **IC-SCALE-1:** What happens at 10x/100x/1000x tasks?
- **IC-SCALE-4:** Assumptions documented in code comments

## Audit Procedure

### Step 1: Task State Machine Analysis
1. Read `flow_gates_and_validation.py` in full
2. Map all task states and valid transitions
3. Check: are transitions validated before execution?
4. Check: what happens on invalid transition attempt?
5. Check: are states enumerated (enum/constants) or string literals?

### Step 2: DAG Analysis
1. Read `dag.py` in full
2. Check: cycle detection implemented?
3. Check: topological sort correct?
4. Check: what's the Big-O of DAG operations?
5. Check: what happens with 100, 1000, 10000 tasks in DAG?

### Step 3: CRUD Walk
1. Read create_task.py, query_task.py, update_task.py, delete_task.py
2. Check: consistent error handling pattern
3. Check: input validation on each operation
4. Check: return types consistent (dict-return with "error" key?)
5. Check: transaction boundaries on create and update

### Step 4: Task DB Pattern (Boundary B-06)
1. Read tasks/db.py in full
2. Compare with canonical db/ package patterns
3. Check: does it use get_db() from db/ or its own connection?
4. Check: parameterized queries?
5. Check: consistent Row factory usage?

### Step 5: Rollup Analysis
1. Read rollup.py
2. Check: what does rollup compute? From what data?
3. Check: performance at scale (many tasks)

### Step 6: Rule-by-Rule Evaluation

## Expected Findings from Research

1. **Task engine has deep test coverage** — TDD rules may PASS better here than other packages
2. **Flow gates are well-designed** — state machine validation is a strength
3. **CONSIST-2 risk:** Multi-step task creation may lack explicit transactions
4. **ERR-1:** Error pattern is dict-return {"error": ...} — consistent within tasks/ but no exception hierarchy
5. **IC-SCALE-1:** DAG complexity at scale not documented
6. **CONSIST-4:** Task creation likely not idempotent
7. **PP-CRAFT-2:** dag.py Big-O not documented
8. **Boundary B-06:** tasks/db.py may use own patterns instead of canonical db/

## Output Format

```markdown
# AU-04 Task Engine Audit Results

## Task State Machine
[States, transitions, validation rules]

## DAG Analysis
[Structure, cycle detection, complexity]

## Filled Checklist

### CS Foundations — Consistency & State
| Rule | Status | Evidence |
|------|--------|----------|
...

### CS Foundations — Error & Failure Modes
...

### CS Foundations — Data Architecture (subset)
...

### Clean Architecture (subset)
...

### Pragmatic Programmer (subset)
...

### Implementation Coding Core (subset)
...

## Findings

| # | Rule | Severity | Affected Files | Description | Remediation |
|---|------|----------|----------------|-------------|-------------|
...

## Strengths
...

## Boundary Check: B-06 (Tasks <-> DB)
[Pattern consistency assessment]
```
