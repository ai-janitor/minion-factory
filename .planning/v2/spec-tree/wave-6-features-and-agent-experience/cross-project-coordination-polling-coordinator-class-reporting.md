# SU-19: Cross-Project Coordination — Polling, Coordinator Class, Reporting

**Wave:** 6 (depends on SU-04 global comms fix)
**Requirements:** 5.2
**Dependencies:** SU-04 (global comms must work correctly first)
**Dependents:** None

## Domain Preamble

Cross-project coordination is one coherent feature: aggregated multi-project polling (iterating coordinator DB for all agent project paths), a new coordinator agent class in agent-classes.yaml, and project leads reporting to sys-lead via global comms. The polling, auth, and comms changes are tightly coupled — multi-project poll requires the coordinator class which requires auth changes.

## Scope

- Implement aggregated multi-project polling
- Add coordinator agent class to agent-classes.yaml and auth.py
- Wire project leads → sys-lead reporting via global comms

## Affected Files

- `src/minion/polling.py`
- `src/minion/auth.py`
- `src/minion/crew/agent-classes.yaml`
- `src/minion/comms/*.py`

## Boundary Edges

- E-05: SU-04 → this (data-shape: route_cross_repo() must reliably deliver)
- E-12: SU-07 → this (naming: coordinator class needs backlog permissions)
- B-03 (internal): auth.py ↔ agent-classes.yaml (naming: coordinator in both)
