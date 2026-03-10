# Worker Checklist — <name> [0/N-0NA]

## Minion Access From Worktrees
Use `-C <project-root>` to reach the source project DB:
```
minion -C <project-root> agent register --name <name> --class coder --model <model-id>
minion -C <project-root> set-context --agent <name> --context "working on X" --hp 90
minion -C <project-root> comms send local --from <name> --to <lead> --message "checklist written"
```
The `--model` flag is MANDATORY on registration — without it the TUI MODEL column is blank.

## FIRST ACTION — before reading any code or making any changes:
Write CHECKLIST.md in your working directory. For each item, list:
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
