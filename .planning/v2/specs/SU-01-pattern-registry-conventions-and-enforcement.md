# SU-01: Pattern Registry — Conventions and Enforcement

**Wave:** 0 (foundation)
**Requirements:** 2.9
**Dependencies:** None
**Dependents:** SU-08, SU-09, SU-10, SU-14

---

## Purpose

Create `.work/pattern-registry.md` as the single source of truth for cross-cutting conventions. Every subsequent spec unit references this artifact to ensure consistency. Without it, agents making independent decisions about error handling, logging, and DB access will produce inconsistent code.

## Requirements Traceability

- **2.9 (Pattern Registry):** "No pattern registry documenting conventions. Create a living document of decided patterns (error handling, logging, DB access, config loading)."

## Dependencies

None. This is the root of the dependency graph.

## Behavior

### Inputs
- Existing codebase patterns (discovered during research)
- Current code examples from each cross-cutting concern

### Outputs
- `.work/pattern-registry.md` with the following sections, each containing: (a) canonical pattern with code example, (b) rationale, (c) when to deviate

### Required Sections

**1. Error Handling**
- Convention: raise typed exceptions at module boundaries, return error dicts at CLI/API boundaries
- Current pattern in comms/delivery.py: `except Exception as exc: log.warning(...)` — this is the WRONG pattern for most code. The registry must specify which exception types each module should catch.
- Pattern: `except (sqlite3.OperationalError, sqlite3.IntegrityError) as exc:` for DB code, `except (OSError, PermissionError) as exc:` for filesystem code, `except (KeyError, ValueError) as exc:` for data parsing
- Fallback: `except Exception as exc: log.error(...); raise` — never silently swallow

**2. DB Access**
- Convention: `conn = get_db()` / `cursor = conn.cursor()` / `try: ... finally: conn.close()`
- Current pattern established in update_task.py, rollup.py, delivery.py
- Connection always closed in finally block
- WAL mode set by `connect()` in db/connection.py
- row_factory = sqlite3.Row always

**3. Config Resolution**
- Convention: all config values resolve through `src/minion/defaults.py`
- Environment variables read ONLY through defaults.py functions
- CLI `-C` flag sets `MINION_PROJECT_DIR` env var, then defaults.py resolves paths from it
- No direct `os.environ.get()` outside defaults.py

**4. Logging**
- Convention: `log = logging.getLogger(__name__)` at module top
- Levels: ERROR for unrecoverable, WARNING for degraded-but-continuing, INFO for operational events, DEBUG for tracing
- No print() in production code
- Log format includes module name via __name__

**5. Auth Decoration**
- Convention: `require_class()` decorator for CLI commands, `require_scope()` for scope-gated operations
- All write operations to foreign projects (via `-C`) must check auth
- Agent class loaded from `MINION_CLASS` env var or DB lookup

**6. Message Delivery**
- Convention: local delivery writes to `.work/inbox/<agent>/` + DB INSERT, cross-repo delivery via `route_cross_repo()` with coordinator DB lookup
- Message schema: `(from_agent, to_agent, content_file, timestamp, read_flag, is_cc, cc_original_to)`
- msg_type from VALID_MSG_TYPES = {"order", "sitrep", "query", "response", "alert", "system"}

**7. Contracts and Assertions**
- Convention: precondition assertions at function entry for public API functions
- Pattern: `assert param, "param must not be empty"` for string params, `assert isinstance(x, int) and x > 0` for ID params
- Postcondition: assert return value is not None where applicable
- Exception type: AssertionError (stdlib) — no custom exception class needed
- Where: db/, comms/, tasks/, crew/ public functions. Not in CLI command handlers (Click handles validation).

**8. Documentation Conventions**
- ASSUMPTION comments: `# ASSUMPTION: <what> — <why> — <consequence if wrong>`
- Big-O annotations: `# Time complexity: O(N) where N = <what N means>`
- Magic numbers: every literal number gets a named constant or ASSUMPTION comment

**9. Provider Error Classification**
- Convention: providers classify errors into {transient, permanent, auth, rate_limit}
- Transient: retry with backoff. Permanent: fail immediately. Auth: re-auth or fail. Rate_limit: backoff with longer delay.
- Pattern: shared classifier function, not duplicated per provider

## Constraints

- Documentation only — zero production code changes
- Must be written before SU-08, SU-09, SU-10, SU-14 begin work
- Must reference actual current code examples (not hypothetical patterns)
- Each section must have at least one "current good example" file reference

## Edge Cases

- **Convention conflict:** If two existing patterns conflict (e.g., some modules raise, others return dicts), the registry must pick one and document the migration path for the other.
- **Pattern not yet established:** If a cross-cutting concern has no current pattern (e.g., provider error classification), the registry defines the new pattern with rationale.
- **Deviation:** Each section must include "when to deviate" guidance. Example: daemon runner may catch broader exceptions because it must never crash.

## Current State

- No pattern-registry.md exists
- Patterns are implicitly established in code but undocumented
- Research confirms this is the prerequisite for waves 3 and 5

## Test Contract

- Verification: pattern-registry.md exists at `.work/pattern-registry.md`
- Verification: all 9 sections present with code examples
- Verification: each section references at least one existing source file as exemplar
