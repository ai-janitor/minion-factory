# Stage: decomposing

Creating implementation tasks from proven findings or itemized requirements.

## Who acts
Lead or oracle.

## What to do
1. Read `itemized-requirements.md` (and `findings.md` if investigation was done)
2. Create numbered child folders for each implementation item:
   ```
   001-<slug>/README.md
   002-<slug>/README.md
   ```
3. Each child README defines: what to change, which files, acceptance criteria
4. Create tasks in DB linked to this requirement
5. Set `flow_type` per task (bugfix, feature, hotfix, chore)
6. Set `class_required` per task

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
```

## Exit gate
All items from `itemized-requirements.md` have corresponding child folders and DB tasks.
