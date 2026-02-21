# Investigate Capability

1. When reading code, actively look for silent failures — bare excepts, swallowed errors, empty catch blocks, ignored return values, missing error propagation.
2. When you find a silent failure, write it up: what the code does, what it should do, and the exact file and line. Put findings in `.work/traps/silent-fail/`.
3. For each silent failure found, create a task in the task system via `minion create-task` so it gets addressed or explicitly acknowledged. Do not fix it yourself during investigation.
4. Do not assume silent failures are intentional. Flag them all — let the owner decide.
