# Stage: decomposing

Break a requirement into concrete, agent-executable tasks. No task should require judgment calls.

## Who acts
Lead or oracle.

## What to do

### Step 1: Research the codebase

Before creating any tasks, understand what exists:
1. Read the requirement README (backlog description, context, acceptance criteria)
2. Search the codebase for files, functions, and patterns related to the requirement
3. Identify: what already exists, what needs to change, what needs to be created
4. Write findings to `findings.md` in the requirement folder

### Step 2: Decompose into tasks

From the findings, break the work into the smallest independently-testable units:
1. Each task modifies a specific set of files for a specific behavior change
2. Each task has clear acceptance criteria (a test, a command, a visible outcome)
3. Tasks have a dependency order — which must complete before others can start
4. No task should require the implementer to make design decisions — if it does, the decomposition is too coarse

Write the decomposition to `decomposition.md` in the requirement folder:
```markdown
# Decomposition: <requirement title>

## Tasks (in dependency order)

### 1. <task title>
- **Files:** `path/to/file.py` — <what changes>
- **Behavior:** <what the code does after this task>
- **Acceptance:** <how to verify — test command, expected output>
- **Depends on:** none | task N

### 2. <task title>
...
```

Present to user. Wait for approval before creating tasks.

### Step 3: Create child requirements and tasks

After approval:
1. Create numbered child folders for each task:
   ```
   001-<slug>/README.md
   002-<slug>/README.md
   ```
2. Each child README contains: what to change, which files, acceptance criteria (copied from the approved decomposition)
3. Create a task in DB for EACH child — link to the CHILD's requirement ID, NOT the parent:
   ```bash
   minion task define --agent <name> --title "<child title>" --requirement-id <CHILD_REQ_ID> --flow <flow> --description "<description>"
   ```
4. Set `flow_type` per task (bugfix, feature, hotfix, chore)

## Child README format

```markdown
# NNN: <title>

## What to change
<Specific description of the code change>

## Files
- `path/to/file.py` — <what changes>

## Acceptance criteria
- <Testable statement>
- <Testable statement>

## Depends on
- <task N title, or "none">
```

## Exit gate
All tasks from `decomposition.md` have corresponding child folders and DB tasks.
