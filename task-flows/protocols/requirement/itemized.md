# Stage: itemized

Itemized requirements exist. Decision point.

## Who acts
Lead.

## What to do
1. Read `itemized-requirements.md`
2. For each item, decide: do we understand enough to write implementation tasks?
   - **Yes for all items** → shortcut to `decomposing` (skip investigation)
   - **No for some items** → advance to `investigating`
3. Items needing investigation become `INV-` tasks
4. Items ready for implementation wait for `decomposing` stage

## Decision criteria
- Root cause is obvious from the writeup → skip investigation
- Multiple possible causes, unclear code paths, no reproduction → investigate first
- "I think I know" is not enough — if you can't write a specific implementation task, investigate

## Exit gate
Decision made: investigate or decompose.
