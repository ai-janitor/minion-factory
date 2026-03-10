# SU-14: Code Deduplication — Providers, Prompts, DB Patterns

**Wave:** 5 (depends on wave 0 pattern registry)
**Requirements:** 4.2
**Dependencies:** SU-01 (pattern registry defines canonical patterns to deduplicate toward)
**Dependents:** SU-13 (dependency fixes need to know where shared modules land)

## Domain Preamble

Multiple duplication clusters exist: _append_error_log between codex.py and gemini.py, role prompt self-service block duplicated 6 times across 7 role prompts, DBMixin connect-execute-commit-close pattern repeated 10 times, and provider error classifiers sharing structural pattern. All items follow "extract duplication into shared code" using the pattern registry as the target. Co-working prevents creating new duplication while fixing old.

## Scope

- Extract shared `_append_error_log` between codex.py and gemini.py
- Deduplicate role prompt self-service block (6 repetitions)
- Verify DBMixin dedup from v1 is complete
- Extract shared provider error classifier pattern

## Affected Files

- `src/minion/providers/codex.py`
- `src/minion/providers/gemini.py`
- `src/minion/prompts/roles/*.py`
- `src/minion/db/connection.py`

## Boundary Edges

- E-04: SU-01 → this (convention: canonical patterns from pattern registry)
- E-08: → SU-13 (naming: extracted module paths needed by dependency fixes)
