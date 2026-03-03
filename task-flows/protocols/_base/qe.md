# Stage: qe (Quality Engineering)

Automated quality gate between implementation and code review.

## Who acts
Builder, recon, or auditor — runs automated checks on the coder's output.

## What to do
1. Run the project test suite (`uv run pytest` / `npm test` / `cargo test`)
2. Run linter if configured
3. Check for anti-patterns:
   - Excessive mocking in test files (`@patch`, `MagicMock` overuse)
   - New files over 800 LOC
   - Unclaimed file modifications
4. Write results to the QE report context file
5. All checks pass → `complete-phase` (advances to `fixed` for human review)
6. Any check fails → `complete-phase --fail` (bounces back to `in_progress`)

## Quality checks
| Check | Pass condition |
|-------|---------------|
| Tests | All pass, zero failures |
| Lint | No new errors introduced |
| LOC | No new file exceeds 800 lines |
| Mocking | Test files don't over-mock internal functions |

## Exit gate
QE report written. All automated checks pass.
