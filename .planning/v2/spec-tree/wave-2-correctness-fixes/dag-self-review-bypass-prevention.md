# SU-03: DAG Self-Review Bypass Prevention

**Wave:** 2 (parallel correctness cluster)
**Requirements:** 1.1
**Dependencies:** None
**Dependents:** SU-21 (DAG scaffolding enforcement)

## Domain Preamble

The DAG allows implementing agents to self-close QE and verify stages, defeating the purpose of independent review. This spec adds a check in `complete_phase()` that queries transition_log for the last implementer and prevents the same agent from advancing through QE/verify. Single behavioral change in one function with targeted tests.

## Scope

- Add agent-identity check in `complete_phase()` to prevent self-review
- Query transition_log to identify the implementing agent
- Reject phase completion if requester == implementer for QE/verify stages

## Affected Files

- `src/minion/tasks/update_task.py`
- `tests/test_dag_*.py`

## Boundary Edges

- E-06: → SU-21 (state-transition: both modify `complete_phase()` validation block — checks are additive AND)
