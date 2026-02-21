- Execute assigned tasks, report results.
- If you discover new ideas, send them to lead.
- **One file, one concern.** Before writing code, check if the target file has >1 public function or >200 lines. If so, split to a package first. Every coding task starts with: does this logic belong in its own file?
- Read before you write. Understand existing patterns before adding code.
- No files outside your assigned zone without lead approval.
- **Context protection:** Run tests with `-q` or redirect verbose output to a log file. Never stream full test suites or linter output through your session. Read targeted file sections (`offset`/`limit`), not entire large files.
- **Research before coding.** For tasks involving unfamiliar APIs, libraries, or architecture changes — read code, check feasibility, and submit findings first. Don't attempt a full implementation in one invocation. Break large work into: recon → plan → implement → verify.
- **Block, don't burn.** If you hit a wall (dependency missing, build takes too long, need info from another agent) — park the task: `minion complete-phase --agent {you} --task-id N --failed --reason "why you're stuck"`. This moves it to `blocked` so you don't loop. Lead reads the reason and unblocks when ready.

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
