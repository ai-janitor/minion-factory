# SU-22: Dashboard UI Consolidation — Merge and Sys-Lead Views

**Wave:** 6 (depends on SU-18 network API stability)
**Requirements:** 5.5
**Dependencies:** SU-18 (network API should be stable before adding dashboard)
**Dependents:** None

## Domain Preamble

Dashboard exists as a separate subsystem that needs consolidation: define its purpose and scope, verify/complete the merge into the network server, and add sys-lead operational views. The merge and operational views share templates and routes. Must wait for SU-18 to stabilize the network API endpoints that dashboard views will call.

## Scope

- Define dashboard purpose and scope
- Verify/complete dashboard merge into network server
- Add sys-lead operational views (agent status, task pipeline, health overview)

## Affected Files

- `src/minion/dashboard/*.py`
- `src/minion/network/dashboard.py`

## Boundary Edges

- E-10: SU-18 → this (naming + data-shape: endpoint paths and response JSON shapes)
