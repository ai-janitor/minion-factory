# AU-09: Tests Deep Dive

## Purpose

Comprehensive audit of the test suite — test quality, coverage, organization, and adherence to TDD principles. This spec is the PRIMARY owner of all test architecture findings. Domain deep dives reference AU-09 for test-related findings rather than independently auditing test quality.

## Scope

| Directory/File | Description |
|----------------|-------------|
| `tests/` | All test files (20 files) |
| `tests/conftest.py` | Shared fixtures (if exists) |
| `tests/test_*.py` | All test modules |
| `setup.cfg` or `pyproject.toml` | pytest configuration |

Read ALL files in `tests/`.

**Also reference (do not audit in depth):**
- Source packages to build coverage map: `src/minion/*/` (27 packages)
- `.planning/v1/research/test-coverage.md` for existing coverage analysis

## Skills to Evaluate

### Test-Driven Development (all 19 rules — PRIMARY)

#### Cycle Discipline (CYC-1 through CYC-6)
- **CYC-1:** Failing test written BEFORE implementation code
  - **How to check:** This is a retrospective audit — can't verify temporal order. Mark N/A with note "retrospective audit, can't verify test-first". Evaluate test QUALITY as proxy.
- **CYC-2:** Test actually fails (RED confirmed)
  - Same as CYC-1 — retrospective. N/A.
- **CYC-3:** Minimum code written to pass
  - **How to check:** Check for over-engineered test setups. Are tests testing more than needed?
- **CYC-4:** Refactoring only when all tests pass
  - Retrospective. N/A.
- **CYC-5:** One test at a time
  - Retrospective. N/A.
- **CYC-6:** Tests run after every change
  - **How to check:** Check for CI configuration. Check if `pytest` is in any Makefile or script.

#### Test Quality (QUAL-1 through QUAL-5)
- **QUAL-1:** Tests verify behavior, not implementation details
  - **How to check:** Read test assertions. Do they assert on return values/behavior or on internal state/implementation?
  - **Evidence for YES:** Tests call public APIs and assert on outputs.
  - **Evidence for NO:** Tests access private attributes, mock internals, assert on call counts.
- **QUAL-2:** Test names describe scenario and expected result
  - **How to check:** Read test function names. Do they follow `test_[function]_[scenario]_[expected]` pattern?
- **QUAL-3:** Arrange-Act-Assert structure
  - **How to check:** Read 10+ representative tests. Is AAA structure clear?
- **QUAL-4:** No test duplication
  - **How to check:** Look for tests that test the same behavior with slightly different setup.
- **QUAL-5:** Tests are fast (unit tests in milliseconds)
  - **How to check:** Run `pytest --co -q` to count tests. Check for file I/O, DB operations, sleeps.

#### Coverage (COV-1 through COV-4)
- **COV-1:** Happy path covered
  - **How to check:** For each tested package, check if the normal success path is tested.
- **COV-2:** Edge cases covered
  - **How to check:** Check for boundary values, empty inputs, zero, None.
- **COV-3:** Error cases covered
  - **How to check:** Check for tests that verify error conditions (pytest.raises, assert "error" in result).
- **COV-4:** State changes tested (before/after comparisons)
  - **How to check:** Check for tests that verify state before and after an operation.

#### Bug Fix Protocol (BUG-1 through BUG-4)
- **BUG-1 through BUG-4:** Retrospective — can't verify bug-fix process. Evaluate whether test suite structure supports it. Mark N/A with note.

### Pragmatic Programmer (selected rules)
- **PP-DELIVER-3:** Code not done until all tests pass — do all tests currently pass?
  - **How to check:** Run `pytest` and report results.
- **PP-DELIVER-4:** Find bugs once — write test, never escapes again
  - Retrospective — evaluate test suite structure as proxy.
- **PP-DELIVER-5:** Test state coverage, not just code coverage
  - **How to check:** Check for tests that exercise different states of the system.
- **PP-CRAFT-4:** Test-first drives design
  - Retrospective — evaluate test quality as proxy.

### Clean Architecture — Test Architecture (all 4 rules)
- **CA-TEST-1:** Tests coupled to behavior, not implementation
  - **How to check:** Same as QUAL-1.
- **CA-TEST-2:** Tests structured by use case, not by type
  - **How to check:** Is tests/ organized by domain (test_tasks.py, test_comms.py) or by type (test_unit/, test_integration/)?
  - **Known finding:** Flat directory, not structured by use case.
- **CA-TEST-3:** Testing API exists as superset of application API
  - **How to check:** Is there a test utility layer or test helpers?
- **CA-TEST-4:** Humble objects separate testable logic from hard-to-test behavior
  - **How to check:** Are hard-to-test parts (DB, filesystem, subprocess) separated from logic?

## Audit Procedure

### Step 1: Test Infrastructure Assessment
1. Check for `conftest.py` — shared fixtures
   - **Known finding:** No conftest.py. Fixture duplication across 11 files.
2. Check for pytest configuration in setup.cfg or pyproject.toml
3. Check for pytest markers (unit, integration, smoke)
   - **Known finding:** No markers.
4. Run `pytest --co -q` — count tests and list them

### Step 2: Coverage Map
1. Build package-to-test map:

| Package | Test File | Function Count |
|---------|-----------|----------------|
| tasks/ | test_tasks.py | ? |
| backlog/ | test_backlog.py | ? |
| ... | ... | ... |
| daemon/ | (none?) | 0 |
| providers/ | (none?) | 0 |

2. Identify the 17 packages with ZERO behavioral tests
3. For tested packages, count test functions per module

### Step 3: Test Quality Walk
1. Read ALL 20 test files
2. For each test file:
   a. Test naming convention (descriptive or generic?)
   b. AAA structure (arrange-act-assert)?
   c. Behavior vs implementation testing?
   d. Happy path covered?
   e. Edge cases covered?
   f. Error cases covered?
   g. Fixture usage (shared or duplicated?)
   h. Mock usage (any? zero mocks found in research)

### Step 4: Fixture Duplication Analysis
1. Search for common setup patterns across test files
2. Identify: what's being duplicated? (DB setup, test data, cleanup)
3. Quantify: how many files duplicate the same fixture?

### Step 5: Test Execution
1. Run `pytest -v` — all tests must pass
2. Note: test execution time
3. Note: any warnings or deprecations

### Step 6: Rule-by-Rule Evaluation

## Expected Findings from Research

1. **No conftest.py** — fixture duplication across 11 files. Finding.
2. **No pytest markers** — no unit/integration/smoke separation. Finding.
3. **Flat directory** — not structured by use case (CA-TEST-2 FAIL).
4. **Zero mocks** — all tests use real DB/filesystem. Strength (real behavior) and finding (no isolation).
5. **17 packages with zero behavioral tests** — the biggest gap. List them all.
6. **224 test functions exist** but concentrated in backlog, requirements, tasks.
7. **QUAL-1 likely PASS:** Tests that exist are behavioral (per research observation).
8. **CYC-1 through CYC-5:** Retrospective — N/A.
9. **BUG-1 through BUG-4:** Retrospective — N/A.

## Output Format

```markdown
# AU-09 Tests Audit Results

## Test Infrastructure
[conftest, markers, configuration, execution results]

## Coverage Map
| Package | Test File | Functions | Happy | Edge | Error |
|---------|-----------|-----------|-------|------|-------|
...

## Untested Packages (17)
1. ...
...

## Filled Checklist

### Test-Driven Development
| Rule | Status | Evidence |
|------|--------|----------|
| CYC-1 | N/A | Retrospective audit, cannot verify test-first |
...

### Pragmatic Programmer (test-related subset)
...

### Clean Architecture — Test Architecture
...

## Findings

| # | Rule | Severity | Affected Files | Description | Remediation |
|---|------|----------|----------------|-------------|-------------|
| F001 | COV-1 | Critical | tests/ | 17 packages with zero behavioral tests | Add test files for each |
...

## Strengths
- [what the test suite gets right]
```
