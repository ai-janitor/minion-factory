# Plan Capability

1. Break work into atomic tasks. Each task should be completable in a single focused session by one agent. If you can't describe the task in one sentence, it's too big — split it.
2. Write each task to a file before doing anything else. The plan exists on disk, not in your head.
3. After writing the plan file, insert every task into the task system via `minion create-task`. No task lives only in a document.
4. Record ordering dependencies between tasks. If task B needs task A's output, declare that dependency at creation time. Independent tasks should be parallelizable.
5. Do not start execution. Planning and execution are separate phases.
