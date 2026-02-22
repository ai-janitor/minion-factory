# Stage: investigating

Investigation tasks created and in progress.

## Who acts
Lead creates INV- tasks. Investigation agents execute them.

## What to do
1. Read `itemized-requirements.md` — identify items needing investigation
2. Create `INV-` prefixed folders for each:
   ```
   INV-001-<slug>/README.md
   INV-002-<slug>/README.md
   ```
3. Each `INV-` README defines: objective, questions to answer, deliverable
4. Create tasks in DB linked to this requirement
5. Assign investigation agents (recon class)
6. Agents write findings to `findings.md` in the parent requirement folder

## INV- task README format

```markdown
# INV-NNN: <title>

## Objective
<What we need to understand>

## Questions to answer
1. <Specific question>
2. <Specific question>

## Deliverable
Write findings to `../findings.md`
```

## Exit gate
All `INV-` tasks closed. `findings.md` exists with proven root cause.
