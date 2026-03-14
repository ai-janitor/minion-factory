# Worker Checklist — <name> [0/N-0NA]

## Rules
- After completing each item, edit this file to mark it `[x]` and update the tally in the header `[done/total-NNA]`. The TUI parses this file.

## Minion CLI
```
minion -C <project-root> agent register --name <name> --class coder --model <model-id>
minion -C <project-root> set-context --agent <name> --context "working on X" --hp 90
minion -C <project-root> comms send local --from <name> --to <lead> --message "checklist written"
```
The `--model` flag is MANDATORY on registration — without it the TUI MODEL column is blank.

## FIRST ACTION — before reading any code or making any changes:
Write your checklist to `.work/checklists/<name>-task-<task-id>.md` (e.g. `coder-napoleon-task-42.md`). The task ID in the filename scopes this checklist to the current task — preventing stale checklists from old sessions appearing in lineage views. For each item, list:
1. What the problem is (in your own words)
2. Which files you will modify
3. What the fix looks like (approach, not code)
4. How you will verify it works

Use three states: `[ ]` (pending), `[x]` (done), `[NA]` (not applicable, with justification).

## Item: <title> (#<task-id>)
- **Problem:** <one sentence>
- **Files:** <list of specific files>
- **Approach:** <what you will do>
- **Verify:** <how you confirm it works>
- [ ] Implemented
- [ ] Tested

## Final
- [ ] All items implemented
- [ ] `uv run pytest` passes
- [ ] Changes committed
