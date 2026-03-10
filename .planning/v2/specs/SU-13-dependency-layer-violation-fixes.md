# SU-13: Dependency Layer Violation Fixes — db/auth, comms/crew

**Wave:** 5 (after SU-14)
**Requirements:** 4.1
**Dependencies:** SU-14
**Dependents:** None

---

## Purpose

Fix three dependency layer violations: db/ importing from auth, task files importing private _tmux, and bidirectional coupling between comms and crew. Must coordinate with SU-14's extracted shared modules since deduplication may resolve some violations naturally.

## Requirements Traceability

- **4.1 (Dependency Layer Violations):** "db/ imports auth (dependency inversion), task files import _tmux, comms <-> crew bidirectional coupling."

## Dependencies

- **SU-14 (Code Deduplication):** Deduplication may extract shared modules that resolve some import violations. Wait for SU-14 to complete so we know where shared code lives.

## Behavior

### Violation 1: db/ imports auth

**Current state:** Some module in `src/minion/db/` imports from `src/minion/auth.py`. This is a dependency inversion — the DB layer should not depend on the auth layer.

**Target:** Audit all imports in `src/minion/db/*.py`. Remove any import of auth.py. If auth-related data is needed (e.g., VALID_CLASSES for validation), either:
- Move the data to defaults.py (already the convention for shared constants)
- Pass the data as a parameter instead of importing it
- Lazy-import within the function body (last resort)

**Verification:** `grep -r "from minion.auth" src/minion/db/` returns no results.

### Violation 2: Task files import _tmux

**Current state:** Some module in `src/minion/tasks/` imports `_tmux` from `src/minion/crew/`. Private modules (prefixed with `_`) should not be imported outside their package.

**Target:** Audit all imports in `src/minion/tasks/*.py`. If _tmux is imported:
- Determine what _tmux provides (likely pane management functions)
- The import in update_task.py (`from minion.crew import update_pane_task`) is through the crew package's public API — this is CORRECT if `update_pane_task` is exported in `crew/__init__.py`
- If any task file imports `crew._tmux` directly, change to import through the public crew API

**Verification:** `grep -r "_tmux" src/minion/tasks/` returns no results for direct _tmux imports.

### Violation 3: comms <-> crew bidirectional coupling

**Current state:** `src/minion/comms/register.py` contains crew-context-merge logic. This creates a bidirectional dependency: comms depends on crew, and crew depends on comms.

**Target:**
- Identify the crew-context-merge logic in comms/register.py
- Extract it to a neutral location:
  - If SU-14 created a shared module, use that
  - Otherwise, extract to a new module in the appropriate layer (e.g., `src/minion/agent_context.py` or add to `lifecycle.py`)
- comms/register.py should only handle registration-related comms, not context merging
- Verify: no circular imports between comms/ and crew/

**Verification:**
- `python -c "from minion.comms import register; from minion.crew import spawn"` succeeds without circular import error
- No function in comms/ directly references crew internals (only public API)

## Constraints

- Must coordinate with SU-14 output — extracted modules may already fix some violations
- Must not break any existing functionality
- Import changes may require updating `__init__.py` files
- The fix should result in a clean dependency DAG: CLI -> core logic -> DB (no back-edges)

## Edge Cases

1. **Lazy imports already used:** Some violations may already use lazy imports (inside function body) to break cycles. These are acceptable but should be documented as "lazy import to break cycle."
2. **Circular import at module level:** If removing an import causes a circular import elsewhere, use the lazy-import pattern.
3. **Test imports:** Test files may import private modules for testing purposes. This is acceptable — the constraint is on production code only.
4. **SU-14 didn't extract the needed module:** If deduplication didn't create the shared module needed, create it as part of this spec unit.

## Current State

- defaults.py was created in v1 to break some circular deps
- Some violations may already be resolved (research says "partially addressed")
- Full audit needed to confirm current state

## Test Contract

- **Test 1:** `grep -r "from minion.auth" src/minion/db/` returns empty.
- **Test 2:** `grep -r "_tmux" src/minion/tasks/` returns no direct _tmux imports.
- **Test 3:** `python -c "from minion import comms, crew"` succeeds without circular import.
- **Test 4:** All existing tests still pass after import restructuring.
