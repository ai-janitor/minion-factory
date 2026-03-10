# SU-16: Configuration Consistency — -C Flag, Env Vars, WAL

**Wave:** 5 (parallel within wave)
**Requirements:** 4.4
**Dependencies:** None
**Dependents:** None

## Domain Preamble

Configuration has three consistency gaps: the `-C` flag mutates env vars non-transparently, 5 network env vars bypass defaults.py reading directly from os.environ, and daemon WAL/row_factory settings vary across connections. Research indicates most items were already fixed — this is primarily verification with remaining gap closure. Small audit scope.

## Scope

- Audit `-C` flag env var mutation for transparency
- Verify remaining network env vars route through defaults.py
- Verify daemon WAL consistency (research says connection.py standardizes this)

## Affected Files

- `src/minion/defaults.py`
- `src/minion/cli/main.py`

## Boundary Edges

- None
