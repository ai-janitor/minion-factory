# SU-09: Contract and Assertion Expansion — Critical Interfaces

**Wave:** 3 (depends on wave 0 pattern registry)
**Requirements:** 2.4
**Dependencies:** SU-01 (pattern registry defines assertion convention)
**Dependents:** None

## Domain Preamble

Zero contracts or assertions in cross-cutting code (only 5 asserts in production). This spec adds precondition/postcondition assertions to critical interfaces not yet covered, following the pattern registry convention for what/where to assert. Priority: db/agents.py, crew/spawn.py, lifecycle.py. Same pattern applied across ~15 files.

## Scope

- Add precondition assertions on function entry (parameter validation)
- Add postcondition assertions on function exit (return value contracts)
- Priority files: db/agents.py, crew/spawn.py, lifecycle.py, comms/delivery.py
- Follow pattern registry convention for assertion style and exception types

## Affected Files

- ~15 files across `src/minion/` (priority: db, crew, lifecycle)

## Boundary Edges

- E-02: SU-01 → this (convention: assertion patterns from pattern registry)
