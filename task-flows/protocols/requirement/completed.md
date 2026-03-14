# Stage: completed

All implementation tasks closed. Requirement is done. Terminal state.

## Who acts
Lead.

## What to do
1. Verify the full context chain is complete across all tasks
2. If this requirement has a parent, the engine handles rollup automatically
3. Close the originating backlog item:
   ```bash
   minion backlog update --id <backlog-id> --status closed
   ```
4. Deregister all workers, then deregister yourself
5. Report completion to your superior:
   ```bash
   minion comms send local --from <your-name> --to <superior-name> --message "Backlog #<id> complete. All tasks closed, tests pass."
   ```

## No exit
Terminal stage. No further transitions.
