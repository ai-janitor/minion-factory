# SU-20: Agent Experience — Refresh, Cold-Start, Completions, Research Prompts

**Wave:** 6 (parallel within wave)
**Requirements:** 5.3.1, 5.3.2, 5.3.5, 5.3.6
**Dependencies:** None
**Dependents:** None

## Domain Preamble

Four agent experience improvements grouped because each is small individually: (a) verify refresh command works as documented (5.3.1 — already done), (b) enhance cold-start to auto-generate live operational briefing (5.3.2), (c) add shell completion support via Click's `_MINION_COMPLETE` (5.3.5), (d) document research prompt assembly strategy for role/character/scope (5.3.6). All improve agent DX without production logic coupling.

## Scope

- Verify refresh command functionality
- Enhance cold-start with live operational briefing generation
- Add shell completion support
- Document research prompt assembly strategy

## Affected Files

- `src/minion/lifecycle.py`
- `src/minion/cli/main.py`
- `src/minion/prompts/*.py`

## Boundary Edges

- None
