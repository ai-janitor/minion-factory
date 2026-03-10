# SU-07: Backlog Lineage and Auth Hardening

**Wave:** 2 (parallel correctness cluster)
**Requirements:** 1.7, 1.9, 1.10
**Dependencies:** None
**Dependents:** SU-19 (cross-project coordination, via auth changes)

## Domain Preamble

Three related backlog subsystem issues grouped because they co-change the same files: (a) requirement_id not consistently propagated from promote to task creation, (b) no auth checks on backlog write operations when using `-C` flag, and (c) missing test for crew display in promote output. Splitting would create merge conflicts. All touch backlog/ and align with CA-COMP-4 (classes that change together belong together).

## Scope

- Verify and fix requirement_id propagation from promote → task creation
- Add auth checks to backlog add, update, close when using `-C` flag
- Write test for crew display in promote output

## Affected Files

- `src/minion/backlog/promote.py`
- `src/minion/cli/backlog_cmds.py`
- `tests/test_backlog.py`

## Boundary Edges

- E-12: → SU-19 (naming: coordinator class must have appropriate backlog permissions in auth.py)
