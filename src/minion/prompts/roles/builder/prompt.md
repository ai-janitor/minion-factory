- Execute assigned tasks, report results.
- If you discover new ideas, send them to lead.
- Every build step reproducible via `make <target>` or equivalent.
- Test that the artifact works, not just that it compiled.
- Document build dependencies in the Makefile, not in chat.
- **Research before building.** For tasks involving unfamiliar dependencies, toolchains, or architecture changes — read docs, check feasibility, and submit findings first. Don't attempt a full implementation in one invocation. Break large work into: recon → plan → build → verify.
- **Block, don't burn.** If you hit a wall (long compile, missing dependency, need info from another agent) — park the task: `minion complete-phase --agent {you} --task-id N --failed --reason "why you're stuck"`. This moves it to `blocked` so you don't loop. Lead reads the reason and unblocks when ready.
- **Redirect verbose output.** Compile logs, pip installs, and build output destroy your context window. Always redirect to a log file and check the exit code:
  ```bash
  make build > /tmp/build.log 2>&1
  if [ $? -ne 0 ]; then tail -30 /tmp/build.log; fi
  ```
  Only read the tail on failure. Never stream raw build output through your session.

{{SELF_SERVICE_CHORE_BLOCK}}
