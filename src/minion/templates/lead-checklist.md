# Lead Checklist — <name> [0/N-0NA]

## Understanding
- Task: #<task-id> — <title>
- Files affected: <list>
- Acceptance criteria: <what must pass>

## Rules
- Spawn workers on main — do NOT use worktrees. Workers need access to .work/ and checklists.
- After completing each item, edit this file to mark it `[x]` and update the tally in the header `[done/total-NNA]`. The TUI parses this file.
- **Checklist file naming:** Use `lead-<name>-task-<task-id>.md` (e.g. `lead-napoleon-task-42.md`). The task ID scopes the checklist to this specific task and prevents stale checklists from old sessions appearing in lineage views.

## Workers
- [ ] Worker <worker-name> — items #<ids>
  - [ ] Registered (`minion agent register --name <worker-name> --class coder --model <model-id>`)
  - [ ] Task defined (`minion task define --agent <name> --title "..." --requirement <id> --flow <type>`)
  - [ ] Task assigned (`minion task assign --agent <name> --task-id <id> --assigned-to <worker-name>`)
  - [ ] Demanded CHECKLIST.md
  - [ ] Spawned with full context
  - [ ] Verified checklist written
  - [ ] Verified commits
  - [ ] Merged, tests pass
  - [ ] Task closed (`minion task done --agent <name> --task-id <id>`)
  - [ ] Deregistered (`minion agent deregister --name <worker-name>`)

## Final
- [ ] All workers merged
- [ ] All tests passing
- [ ] `uv tool install --force -e .`
- [ ] Report sent to superior
- [ ] Self deregistered
