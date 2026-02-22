# Stage: findings_ready

Findings written. Root cause proven.

## Who acts
Lead or oracle.

## What to do
1. Read `findings.md`
2. Verify root cause is proven, not speculative
3. Verify findings reference specific code (file paths, line numbers)
4. If insufficient → fail back to `investigating`, create more INV- tasks
5. If proven → advance to `decomposing`

## Acceptance criteria for findings
- States root cause as observed behavior, not theory
- References specific code locations
- Test matrix exists (if applicable)
- No open questions that block implementation

## Exit gate
Lead or oracle confirms findings are sufficient to write implementation tasks.
