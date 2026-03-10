# SU-13: Dependency Layer Violation Fixes — db/auth, comms/crew

**Wave:** 5 (depends on SU-14 completing first)
**Requirements:** 4.1
**Dependencies:** SU-14 (deduplication may create shared modules that resolve violations)
**Dependents:** None

## Domain Preamble

Three dependency layer violations exist: db/ package imports from auth (dependency inversion), task files import private _tmux module, and bidirectional coupling between comms and crew (comms/register.py has crew-context-merge logic). All three are about import direction — fixing one may affect where shared code lives, which affects the others. Must coordinate with SU-14's deduplication output since extracted shared modules may resolve some violations naturally.

## Scope

- Audit and fix db/ imports from auth
- Verify task files don't import _tmux directly
- Break comms <-> crew bidirectional coupling
- Coordinate with SU-14's extracted shared modules

## Affected Files

- `src/minion/db/*.py`
- `src/minion/tasks/*.py`
- `src/minion/comms/register.py`
- `src/minion/crew/*.py`

## Boundary Edges

- E-08: SU-14 → this (naming: must know where SU-14's extracted modules land)
