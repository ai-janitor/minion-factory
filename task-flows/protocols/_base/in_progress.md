# Stage: in_progress

Agent actively working.

## Who acts
The assigned agent.

## What to do
1. Do the work described in the task spec
2. Write your progress into the context file (engine has stubbed it for you)
3. When done, submit your result file (`minion submit-result`)
4. Call `complete-phase` to advance to review

## If blocked
Call `complete-phase --fail` to move to `blocked`. Describe the blocker in the context file.

## Exit gate
Result file submitted. Context file filled in.
