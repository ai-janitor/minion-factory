# SU-18: Network API CLI Parity — Handlers and Sys-Lead Gaps

**Wave:** 6 (depends on SU-17 dead code resolution)
**Requirements:** 5.1 (minus composite key — deferred to v3)
**Dependencies:** SU-17 (scaling endpoints must be resolved first)
**Dependents:** SU-22 (dashboard depends on stable API)

## Domain Preamble

~10 CLI commands lack network API equivalents. Additionally, GET /who filtering needs verification, 6 sys-lead review gaps exist (lineage, overview, alerts, query params, DB policy, full agent view), and scaling endpoints need wiring or removal. All items extend the same HTTP API surface using the same handler pattern, router registration, and test infrastructure.

## Scope

- Identify and add handlers for ~10 CLI commands without API equivalents
- Verify GET /who filtering
- Audit and address 6 sys-lead review gaps
- Wire scaling endpoints to router or remove (coordinated with SU-17 resolution)

## Affected Files

- `src/minion/network/handlers/*.py`
- `src/minion/network/routes.py`

## Boundary Edges

- E-09: SU-17 → this (naming: scaling endpoint final state)
- E-10: → SU-22 (naming + data-shape: endpoint paths and response JSON shapes)
