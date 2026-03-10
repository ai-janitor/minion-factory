# SU-17: Dead Code and Unreachable Paths — Scaling, Logging, TaskDB, Intel

**Wave:** 5 (parallel within wave)
**Requirements:** 4.5
**Dependencies:** None
**Dependents:** SU-18 (network API parity needs scaling endpoints resolved)

## Domain Preamble

Five dead/unreachable code items: scaling endpoints registered but unreachable, server suppresses HTTP logs entirely, TaskDB post-close calls raise AttributeError instead of meaningful error, bare except in intel auto-link that should be sqlite3.IntegrityError, and generic file names violating filesystem-as-db. All follow "find dead/wrong thing, fix it" — small scope per item, same audit workflow.

## Scope

- Verify scaling endpoint router registration — fix or remove
- Add HTTP request logging to network server
- Fix TaskDB post-close error messaging
- Narrow intel auto-link bare except to sqlite3.IntegrityError
- Rename remaining generic file names

## Affected Files

- `src/minion/network/handlers/scaling.py`
- `src/minion/network/server.py`
- `src/minion/tasks/*.py`
- `src/minion/intel/*.py`

## Boundary Edges

- E-09: → SU-18 (naming: scaling endpoint resolution determines what SU-18 adds to)
