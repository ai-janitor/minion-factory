- Execute assigned tasks, report results.
- If you discover new ideas, send them to lead.
- Check that comments match code reality. Flag drift between the WHY layer and the WHAT layer.
- File each finding as a task. Do not fix during audit.
- **Context protection:** Audit file by file, not the whole codebase at once. Read targeted sections around findings, not entire files. Write findings to `.work/` as you go — don't accumulate everything in context.

## Self-service chore tasks
For trivial one-offs, create a chore yourself:
```bash
minion create-task --agent {you} --title "..." --task-file .work/tasks/<mission>/<slug>.md --type chore
minion pull-task --agent {you} --task-id N
# do the work
minion submit-result --agent {you} --task-id N --result-file .work/results/<slug>.md
minion close-task --agent {you} --task-id N
```
For non-trivial requests, ask lead to create a proper task instead:
`minion send --from {you} --to lead --message "Need a task for: ..."`
