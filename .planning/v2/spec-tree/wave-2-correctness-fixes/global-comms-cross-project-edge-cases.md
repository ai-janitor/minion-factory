# SU-04: Global Comms Cross-Project Edge Cases

**Wave:** 2 (parallel correctness cluster)
**Requirements:** 1.2
**Dependencies:** None
**Dependents:** SU-19 (cross-project coordination)

## Domain Preamble

`comms send` with `-C` targeting a foreign project fails silently when the target project's messages table doesn't exist. This spec fixes `route_cross_repo()` to handle missing tables — either auto-create the messages table on demand or error clearly with actionable messaging. Single edge case in one delivery function.

## Scope

- Fix `route_cross_repo()` to detect missing messages table in foreign project DBs
- Either create table on demand or return clear error
- Verify message schema compatibility: `(id, from_agent, to_agent, message, msg_type, timestamp)`

## Affected Files

- `src/minion/comms/delivery.py`
- `tests/test_comms*.py`

## Boundary Edges

- E-05: → SU-19 (data-shape: cross-project coordination depends on reliable cross-repo delivery)
