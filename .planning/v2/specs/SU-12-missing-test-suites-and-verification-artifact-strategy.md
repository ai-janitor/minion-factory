# SU-12: Missing Test Suites and Verification Artifact Strategy

**Wave:** 4 (after SU-11)
**Requirements:** 3.2, 3.3
**Dependencies:** SU-11
**Dependents:** None

---

## Purpose

Identify coverage gaps by comparing test files to source modules, write tests for uncovered modules, and design the verification artifact strategy (what evidence each DAG stage produces on completion).

## Requirements Traceability

- **3.2 (Missing Test Suites):** "Identify modules without test coverage."
- **3.3 (Verification Artifacts):** "No verification artifacts produced per DAG stage."

## Dependencies

- **SU-11 (Test Infrastructure):** Marker infrastructure must be in place so new tests use proper markers.

## Behavior

### 3.2 — Coverage Gap Analysis

**Method:** Compare `src/minion/**/*.py` modules to `tests/test_*.py` files. For each source module, check if a corresponding test file exists.

**Known existing coverage (from research):**
- Missions: test_missions_behavioral.py, test_missions_loader_resolver_party.py
- Network: test_network_api_route_integrity.py, test_network_handlers_behavioral.py, test_network_handler_error_paths.py
- Comms: test_comms*.py
- Auth: test_auth*.py
- Lifecycle: test_lifecycle*.py
- State machines: test_state_machines*.py
- Polling: test_polling*.py
- DAG/Tasks: test_dag*.py, test_task*.py
- Backlog: test_backlog.py

**Expected gaps (modules likely without tests):**
- `src/minion/fs.py` — filesystem helpers (atomic_write_file, etc.)
- `src/minion/warroom.py` — battle plans, raid log
- `src/minion/triggers.py` — trigger word processing
- `src/minion/intel/` — intel gathering modules
- `src/minion/dashboard/` — dashboard render, queries, loop
- `src/minion/providers/` — provider-specific logic (codex, gemini, claude)
- `src/minion/defaults.py` — config resolution functions
- `src/minion/output.py` — output formatting

**For each uncovered module:** Write at least one behavioral test exercising the public API. Use SU-11 markers.

### 3.3 — Verification Artifact Strategy

Design what each DAG stage produces as evidence of completion:

| DAG Stage | Artifact | Location | Content |
|-----------|----------|----------|---------|
| `open` | Task spec file | `.work/tasks/<id>/spec.md` | Requirements, acceptance criteria |
| `assigned` | Claim records | DB `file_claims` table | Agent claimed files |
| `scaffolding` | Stub files | Working tree | Empty files with headers |
| `in_progress` | Code changes | Working tree + git diff | Implementation |
| `fixed` | Result file | `.work/tasks/<id>/result.md` | What was done, files changed |
| `qe` | Test report | `.work/tasks/<id>/test-report.md` | Test pass/fail, coverage delta |
| `verify` | Review verdict | `.work/tasks/<id>/review.md` | Approve/reject with rationale |
| `closed` | Transition log | DB `transition_log` table | Complete stage history |

**Artifact production:** Each `complete_phase()` call should verify the expected artifact exists before allowing phase advancement. This is a design document — implementation is in SU-21 (DAG enforcement) or future work.

**Output:** Write `.planning/v2/verification-strategy.md` documenting the artifact strategy.

## Constraints

- New tests must use SU-11 marker infrastructure
- Verification strategy is a design document, not implementation
- Coverage analysis should be systematic (script or manual audit), not ad-hoc

## Edge Cases

1. **Module with no public API:** Some modules are internal helpers (e.g., `_helpers.py`). These are tested indirectly through their callers. Note as "covered indirectly" in the analysis.
2. **Provider tests need mocking:** Provider modules call external APIs. Tests must mock HTTP calls, not make real requests.
3. **Dashboard tests need Flask/HTTP setup:** Dashboard render functions may need a test client. Create minimal fixture if needed.
4. **Artifact strategy vs enforcement:** This spec designs the strategy. SU-21 implements the enforcement gate. Do not implement gates here.

## Current State

- ~39 test files exist
- conftest.py provides shared fixtures
- Missions, network, comms all have test coverage
- Gaps: fs.py, warroom.py, triggers.py, intel/, dashboard/, providers/, defaults.py

## Test Contract

- **Test 1:** Coverage analysis document exists listing all source modules and their test status.
- **Test 2:** Every previously uncovered module now has at least one test file.
- **Test 3:** `verification-strategy.md` exists with artifact definitions for all DAG stages.
- **Test 4:** All new tests pass with `uv run pytest` and have proper markers.
