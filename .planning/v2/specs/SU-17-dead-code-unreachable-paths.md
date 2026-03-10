# SU-17: Dead Code and Unreachable Paths — Scaling, Logging, TaskDB, Intel

**Wave:** 5 (parallel within wave)
**Requirements:** 4.5
**Dependencies:** None
**Dependents:** SU-18

---

## Purpose

Fix five dead/unreachable code items: scaling endpoints, HTTP log suppression, TaskDB post-close errors, intel auto-link bare except, and generic file names.

## Requirements Traceability

- **4.5 (Dead/Unreachable Code):** "Scaling endpoints unreachable, server suppresses HTTP logs, TaskDB post-close AttributeError, bare except in intel, generic file names."

## Dependencies

None.

## Behavior

### 4.5.1 — Scaling Endpoints

**Current state:** `src/minion/network/handlers/scaling.py` exists with endpoint handlers, but they may not be registered in the router (`src/minion/network/routes.py`).

**Audit:**
- Check routes.py for scaling endpoint registration
- If registered: verify endpoints are reachable (test with HTTP request)
- If NOT registered: decide — wire them up or remove the module

**Decision criteria:**
- If the scaling feature is needed for v2 (on-demand spawning): wire up the endpoints
- If scaling is deferred/experimental: remove the module and dead handler code
- Document the decision for SU-18 (E-09 contract): "scaling endpoints are {wired/removed}"

### 4.5.2 — HTTP Request Logging

**Current state:** `src/minion/network/server.py` likely suppresses HTTP request logging entirely (uvicorn or custom server config).

**Target:**
- Enable access logging at INFO level for all HTTP requests
- Format: `"<method> <path> <status_code> <duration_ms>"`
- Use Python logging (not print) so it integrates with the existing log infrastructure

### 4.5.3 — TaskDB Post-Close Error

**Current state:** After a task DB is closed, subsequent operations raise `AttributeError` instead of a meaningful error message.

**Target:**
- If a DB operation is attempted on a closed connection, raise a clear error: `"Database connection is closed. Re-open with get_db() or connect()."`
- This could be implemented as a wrapper on the connection object or as a check in common access patterns

### 4.5.4 — Intel Auto-Link Bare Except

**Current state:** `src/minion/intel/*.py` has a bare `except Exception` (or `except:`) in auto-link logic that should be `except sqlite3.IntegrityError`.

**Target:**
- Find the auto-link code in intel/
- Narrow the exception to `sqlite3.IntegrityError` (the only expected failure — duplicate link)
- Other exceptions should propagate

### 4.5.5 — Generic File Names

**Current state:** Research says "Most files now follow filesystem-as-db naming. Some generic names remain."

**Target:**
- Audit `src/minion/` for remaining generic names: `utils.py`, `helpers.py`, `misc.py`, `common.py`
- For each: rename to describe contents, or merge into an existing descriptively-named module
- Update all imports referencing renamed files

## Constraints

- Scaling endpoint decision must be documented for SU-18 (E-09)
- File renames must update ALL import references
- Must not break any existing functionality
- HTTP logging must not leak sensitive data (message content, tokens)

## Edge Cases

1. **Scaling handlers referenced elsewhere:** Before removing, grep for imports of scaling.py. If other modules import from it, those references must be updated.
2. **HTTP logging performance:** Access logging on every request adds overhead. For a single-machine tool, this is negligible.
3. **TaskDB closed connection race:** If multiple threads try to use a closed connection, the error message should be thread-safe.
4. **Generic names that are actually descriptive:** `output.py` describes "output formatting" — that's fine. Only rename truly generic names.

## Current State

- scaling.py exists, registration status unknown
- HTTP logging likely suppressed
- TaskDB post-close behavior needs verification
- Intel bare except needs verification
- Most files already have descriptive names

## Test Contract

- **Test 1:** Scaling endpoints: either registered and reachable, or module removed. Document which.
- **Test 2:** HTTP request to network server produces a log entry at INFO level.
- **Test 3:** Close a DB connection, attempt an operation. Assert clear error message (not AttributeError).
- **Test 4:** Intel auto-link: only `sqlite3.IntegrityError` is caught. Other exceptions propagate.
- **Test 5:** `find src/minion -name "utils.py" -o -name "helpers.py" -o -name "misc.py" -o -name "common.py"` returns empty.
