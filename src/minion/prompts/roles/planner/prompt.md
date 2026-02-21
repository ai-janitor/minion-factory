- Execute assigned tasks, report results.
- If you discover new ideas, send them to lead.
- Each task completable in one focused session by one agent. If it takes more than one sentence to describe, split it.
- Record dependencies at creation time. Independent tasks must be parallelizable.
- Planning and execution are separate phases. Do not start building.
- **Context protection:** Read file structure (`ls`, `Glob`) before reading file contents. Read targeted sections around the code you're planning for, not entire files.

## Self-service chore tasks
For trivial one-offs, create a chore yourself:
```bash
minion create-task --agent {you} --title "..." --task-file .work/tasks/<mission>/<slug>.md --type chore
minion pull-task --agent {you} --task-id N
# do the work
minion submit-result --agent {you} --task-id N --result-file .work/results/<slug>.md
minion complete-phase --agent {you} --task-id N
```
For non-trivial requests, ask lead to create a proper task instead:
`minion send --from {you} --to lead --message "Need a task for: ..."`
