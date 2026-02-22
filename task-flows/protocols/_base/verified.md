# Stage: verified

Review passed. Awaiting testing.

## Who acts
Tester (builder, recon, or auditor — per `workers:` in the DAG).

## What to do
1. Read the result file and review verdict
2. Run relevant tests against the changes
3. Write test results into the context file
4. Pass → `complete-phase` (advances to `closed`)
5. Fail → `complete-phase --fail` (sends back to `assigned`)

## Exit gate
Tests executed. Results documented. Pass or fail decided.
