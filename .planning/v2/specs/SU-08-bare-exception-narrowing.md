# SU-08: Bare Exception Narrowing — 87 Blocks Across 43 Files

**Wave:** 3 (depends on SU-01 pattern registry)
**Requirements:** 2.1
**Dependencies:** SU-01
**Dependents:** None

---

## Purpose

Narrow 87 remaining `except Exception` blocks to specific exception types. Bare exception handlers silently swallow errors, making debugging impossible. The pattern registry (SU-01) defines the convention; this spec applies it systematically.

## Requirements Traceability

- **2.1 (Bare Exception Cleanup):** "103 bare except Exception blocks across 43 files silently swallow errors. Each must be narrowed to specific exception types or re-raise after logging."

## Dependencies

- **SU-01 (Pattern Registry):** Must complete first. The error handling section of the pattern registry defines: which exceptions each module should catch, when to re-raise vs log-and-continue, when broader catches are acceptable (daemon runner).

## Behavior

### Target State

For each of the 87 `except Exception` blocks:

1. **Identify the try block's operations.** What can actually fail? DB access -> sqlite3 exceptions. File I/O -> OSError/PermissionError. JSON parsing -> json.JSONDecodeError/KeyError/ValueError. YAML parsing -> yaml.YAMLError. Network -> ConnectionError/TimeoutError. Subprocess -> subprocess.SubprocessError.

2. **Narrow to specific types.** Replace `except Exception` with the identified specific types.

3. **Handle the remainder.** If unexpected exceptions are possible, add a final `except Exception as exc: log.error("Unexpected: %s", exc); raise` — never silently swallow.

### Module Priority Order

**Priority 1 — Daemon (highest risk of silent failures):**
- `src/minion/daemon/runner/*.py` — long-running processes where silent failures cause agent deafness
- Exception: the top-level daemon loop may keep a broad `except Exception` with logging + restart, per pattern registry "daemon runner" exception in the convention

**Priority 2 — Polling:**
- `src/minion/polling.py` — poll loop failures directly cause agent deafness
- Narrow to: sqlite3.OperationalError (DB), OSError (PID files), KeyError/ValueError (malformed data)

**Priority 3 — Comms:**
- `src/minion/comms/*.py` — message delivery failures should be visible
- Narrow to: sqlite3.* (DB), OSError (file delivery), PermissionError (cross-project)

**Priority 4 — Remaining modules:**
- All other files with bare exception handlers
- Apply the pattern registry convention mechanically

### Per-Block Decision

For each block, the implementing agent makes ONE of these decisions:

| Decision | When | Pattern |
|----------|------|---------|
| Narrow + handle | Specific exceptions are identifiable | `except (sqlite3.OperationalError, KeyError) as exc:` |
| Narrow + re-raise | Unexpected errors should propagate | `except Exception as exc: log.error(...); raise` |
| Keep broad + log | Daemon top-level loop only | `except Exception as exc: log.error(...); continue` |
| Remove try/except | The try block is unnecessary | Delete the try/except wrapper entirely |

### Inputs
- Pattern registry error handling convention (from SU-01)
- Each `except Exception` block and its try body

### Outputs
- 87 blocks narrowed or re-raise-guarded
- Each change is mechanical and local to the function containing the try/except

## Constraints

- Must follow pattern registry convention (SU-01)
- Must not change function behavior for the expected error cases
- Must not add new dependencies to any module
- Must not change function signatures
- Daemon runner top-level loop MAY keep broad catch (explicitly allowed by pattern registry)

## Edge Cases

1. **Nested try/except:** Some functions have nested try blocks. Narrow each independently based on its specific operations.
2. **Bare except (no Exception):** Some code uses `except:` without `Exception`. These are even worse — narrow them the same way.
3. **Re-raise after logging:** Some blocks do `log.warning(...); return None`. If the function's contract allows None return on error, this is acceptable. But the exception type should still be narrowed.
4. **Test-only exceptions:** Some test files have `except Exception`. These are lower priority but should still be narrowed for consistency.
5. **Third-party library exceptions:** Some try blocks call libraries (yaml, click, etc.). Use the library's documented exception types.

## Current State

- 87 `except Exception` blocks remain (down from 103 after v1 partial work)
- No pattern registry exists yet (SU-01 must complete first)
- Priority modules: daemon, polling, comms

## Test Contract

- **Test 1:** After narrowing, `grep -r "except Exception" src/minion/ | wc -l` returns 0 (or a documented small number for daemon top-level).
- **Test 2:** All existing tests still pass (no behavior change for expected error paths).
- **Test 3:** For each priority module (daemon, polling, comms): inject an unexpected exception type. Assert it propagates (not silently caught).
- **Test 4:** Daemon runner top-level loop: inject an exception. Assert it's logged and the loop continues (intentional broad catch).
