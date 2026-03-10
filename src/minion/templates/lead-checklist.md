# Lead Checklist — <name> [0/N-0NA]

## Understanding
- Task: #<task-id> — <title>
- Files affected: <list>
- Acceptance criteria: <what must pass>

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
