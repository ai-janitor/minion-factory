# SU-08: Bare Exception Narrowing — 87 Blocks Across 43 Files

**Wave:** 3 (depends on wave 0 pattern registry)
**Requirements:** 2.1
**Dependencies:** SU-01 (pattern registry defines error handling convention)
**Dependents:** None

## Domain Preamble

87 remaining `except Exception` blocks across 43 files silently swallow errors. Each must be narrowed to specific exception types or re-raise after logging, following the convention established in the pattern registry (SU-01). Priority modules: daemon, polling, comms. Same mechanical change repeated across many files — subdivide by module group for parallel execution but track as one deliverable.

## Scope

- Narrow all 87 bare `except Exception` blocks to specific exception types
- Follow pattern registry convention for error handling
- Priority order: daemon → polling → comms → remaining modules
- Each narrowing: identify the specific exceptions that can occur, catch those, re-raise or log unexpected

## Affected Files

- ~43 files across `src/minion/` (see research for distribution)

## Boundary Edges

- E-01: SU-01 → this (convention: error handling patterns from pattern registry)
