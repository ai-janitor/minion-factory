# Plan Capability

1. Break work into atomic tasks. Each task should be completable in a single focused session by one agent. If you can't describe the task in one sentence, it's too big — split it.
2. Write each task to a file in the logical `.work/` location. The directory tree is the database — tasks for build go in build, tasks for auth go in auth. The plan exists on disk, not in your head.
3. After writing the task file, insert every task into the task system via `minion create-task` with the file path as reference. The task system points to the file, the file has the detail.
4. Record ordering dependencies between tasks. If task B needs task A's output, declare that dependency at creation time. Independent tasks should be parallelizable.
5. Do not start execution. Planning and execution are separate phases.
