# Stage: in_progress

Implementation tasks are being worked.

## Who acts
Lead monitors. Agents execute tasks through their own DAGs.

## What to do
1. Assign tasks to eligible agents
2. Monitor progress via `sitrep`
3. Handle blocked tasks — read blocker context, resolve, reassign
4. Track completion percentage (closed tasks / total tasks)
5. When all tasks close, engine rolls up to `completed`

## Exit gate
All linked implementation tasks are in `closed` status.
