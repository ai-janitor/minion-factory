# SU-10: Documentation Debt — Assumptions and Big-O Annotations

**Wave:** 3 (depends on wave 0 pattern registry)
**Requirements:** 2.6, 2.7
**Dependencies:** SU-01 (pattern registry defines documentation conventions)
**Dependents:** None

## Domain Preamble

Key files lack ASSUMPTION comments for magic numbers (daemon constants, HP calculations, token estimates) and Big-O documentation on hot paths (dag.py, rollup.py, daemon polling). Both are documentation-only changes with no behavior modification. The pattern registry defines what counts as a "magic number" and the annotation format. Same audit+annotate workflow for both concerns.

## Scope

- Audit files with magic numbers, add ASSUMPTION comments where missing
- Add Big-O documentation to remaining hot paths (rollup.py, dag.py functions)
- Follow pattern registry convention for annotation format

## Affected Files

- Various files across `src/minion/`: daemon constants, HP calculations, token estimates, rollup, polling

## Boundary Edges

- E-03: SU-01 → this (convention: documentation format from pattern registry)
