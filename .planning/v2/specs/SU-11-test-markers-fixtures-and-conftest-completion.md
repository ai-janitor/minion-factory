# SU-11: Test Markers, Fixtures, and Conftest Completion

**Wave:** 4 (parallel with waves 2-3)
**Requirements:** 3.1
**Dependencies:** None
**Dependents:** SU-12

---

## Purpose

Complete test infrastructure: add pytest markers to all test files, register custom markers in pyproject.toml, and verify conftest.py fixture coverage eliminates duplication. Infrastructure-only — no production code changes.

## Requirements Traceability

- **3.1 (Test Infrastructure):** "No pytest markers. Add categorization. Verify conftest.py fixture coverage."

## Dependencies

None.

## Behavior

### Marker Categories

| Marker | Meaning | Files |
|--------|---------|-------|
| `@pytest.mark.unit` | Isolated, no external deps, fast | Pure logic tests, data transforms |
| `@pytest.mark.integration` | Uses real DB, filesystem, or subprocess | CLI runner tests, DB operation tests |
| `@pytest.mark.smoke` | End-to-end scenario, multi-agent | Workflow tests, multi-agent smoke |

### Marker Registration in pyproject.toml

Add to `[tool.pytest.ini_options]`:
```toml
markers = [
    "unit: Fast isolated tests with no external dependencies",
    "integration: Tests that use real DB, filesystem, or subprocess",
    "smoke: End-to-end multi-agent scenario tests",
]
```

### Marker Application

For each of ~36 test files without markers:
1. Read the test file to determine category
2. Add `import pytest` if not present
3. Add `@pytest.mark.<category>` decorator to each test class or as module-level `pytestmark = pytest.mark.<category>`

**Module-level marker is preferred** when all tests in a file are the same category:
```python
pytestmark = pytest.mark.integration
```

### Conftest.py Verification

Current conftest.py provides:
- `isolated_db` — creates temp DB with schema
- `isolated_db_with_requirements` — DB with requirement records
- `isolated_db_with_coordinator` — DB with coordinator setup
- CLI runner helpers
- Agent registration helpers

**Verify:**
- No test file creates its own DB connection setup (should use `isolated_db`)
- No test file duplicates agent registration logic (should use helpers)
- If duplication found: refactor the test file to use conftest fixtures

### Inputs/Outputs
- Modified: `pyproject.toml` (marker registration)
- Modified: `tests/*.py` (marker decorators)
- Modified: `tests/conftest.py` (if new shared fixtures needed)

## Constraints

- No production code changes
- Markers must be consistent across the test suite
- Existing tests must continue passing after marker addition
- `uv run pytest -m unit` must select only unit tests

## Edge Cases

1. **Mixed test file:** A file with both unit and integration tests. Use per-function markers instead of module-level.
2. **Already marked files:** test_contracts.py, test_imports.py already have `pytest.mark.unit`. Don't double-mark.
3. **Conftest fixture not applicable:** Some tests genuinely need custom setup. That's fine — just verify it's not duplicating conftest.
4. **Marker typo:** Unregistered markers cause pytest warnings. Registration in pyproject.toml prevents this.

## Current State

- conftest.py exists with shared fixtures
- ~3 files have markers, ~36 do not
- pyproject.toml exists but markers may not be registered

## Test Contract

- **Test 1:** `uv run pytest --co -m unit` returns only unit-marked tests (>0 results).
- **Test 2:** `uv run pytest --co -m integration` returns only integration-marked tests (>0 results).
- **Test 3:** `uv run pytest -W error::pytest.PytestUnknownMarkWarning` passes with no unknown marker warnings.
- **Test 4:** No test file creates a DB connection directly (all use conftest fixtures).
