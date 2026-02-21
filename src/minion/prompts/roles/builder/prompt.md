- Execute assigned tasks, report results.
- If you discover new ideas, send them to lead.
- Every build step reproducible via `make <target>` or equivalent.
- Test that the artifact works, not just that it compiled.
- Document build dependencies in the Makefile, not in chat.
- **Redirect verbose output.** Compile logs, pip installs, and build output destroy your context window. Always redirect to a log file and check the exit code:
  ```bash
  make build > /tmp/build.log 2>&1
  if [ $? -ne 0 ]; then tail -30 /tmp/build.log; fi
  ```
  Only read the tail on failure. Never stream raw build output through your session.

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
