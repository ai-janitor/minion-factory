# SU-11: Test Markers, Fixtures, and Conftest Completion

**Wave:** 4 (parallel with waves 2-3, enables better testing for later waves)
**Requirements:** 3.1
**Dependencies:** None
**Dependents:** SU-12 (missing tests need marker infrastructure)

## Domain Preamble

Test infrastructure has gaps: no conftest.py (fixture duplication ~150 lines across 11 files), no pytest markers for categorization. This spec extracts shared fixtures into conftest.py, adds pytest markers (unit, integration, smoke) to existing test files, and registers custom markers in pyproject.toml. Infrastructure-only — no production code changes.

## Scope

- Extract shared test fixtures into `tests/conftest.py`
- Add pytest markers to ~36 test files
- Register custom markers in `pyproject.toml`
- Verify fixture coverage eliminates duplication

## Affected Files

- `tests/*.py`
- `tests/conftest.py` (new)
- `pyproject.toml`

## Boundary Edges

- E-07: → SU-12 (naming: marker names defined here must be used by SU-12's new tests)
