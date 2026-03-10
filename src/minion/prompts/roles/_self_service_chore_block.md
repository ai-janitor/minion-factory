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
`minion send-local --from {you} --to lead --message "Need a task for: ..."`