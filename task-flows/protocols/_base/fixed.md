# Stage: fixed

Work complete. Awaiting code review.

## Who acts
Reviewer (oracle, recon, or auditor — per `workers:` in the DAG).

## What to do
1. Read the result file and context chain
2. Review the code changes listed in the result
3. Write your verdict into the review context file (engine has stubbed it)
4. Pass → `complete-phase` (advances to `verified`)
5. Reject → `complete-phase --fail` (sends back to `assigned`)

## Review criteria
- Does the change match the task spec?
- Are there regressions or side effects?
- Does the code follow project conventions?

## Exit gate
Review verdict written. Pass or fail decided.
