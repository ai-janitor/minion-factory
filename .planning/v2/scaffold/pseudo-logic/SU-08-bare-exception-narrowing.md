# SU-08 Pseudo-Logic: Bare Exception Narrowing

## Mechanical process for all ~87 blocks

For EACH `except Exception` block in `src/minion/`:

```
# STEP 1: Read the try block — what operations does it perform?
#
# STEP 2: Identify specific exception types:
#   - sqlite3.connect/execute/commit -> sqlite3.OperationalError, sqlite3.IntegrityError
#   - open/read/write/makedirs -> OSError, PermissionError
#   - json.loads/dumps -> json.JSONDecodeError, TypeError
#   - yaml.safe_load -> yaml.YAMLError
#   - subprocess.run/Popen -> subprocess.SubprocessError
#   - dict/list access -> KeyError, IndexError
#   - int()/float() -> ValueError
#   - click.* -> click.exceptions.*
#   - HTTP/network -> ConnectionError, TimeoutError
#
# STEP 3: Apply one of four patterns:
#   A. NARROW + HANDLE: except (Type1, Type2) as exc: <existing handler>
#   B. NARROW + RE-RAISE: except Exception as exc: log.error(...); raise
#   C. KEEP BROAD + LOG: except Exception as exc: log.error(...); continue
#      (ONLY for daemon runner top-level loop)
#   D. REMOVE TRY: delete try/except entirely if unnecessary
#
# STEP 4: Verify the existing handler logic makes sense with narrowed types
#   - If handler returns None -> is that the right behavior for the specific error?
#   - If handler logs warning -> is warning the right level for the specific error?
```

### Priority order for implementation:
1. `src/minion/daemon/runner/*.py` — 8-10 files, highest risk of silent failures
2. `src/minion/polling.py` — poll loop failures cause agent deafness
3. `src/minion/comms/*.py` — 4 files, message delivery visibility
4. Remaining ~29 files — mechanical application of same pattern

### Daemon runner exception — documented broad catch:
```python
# In daemon runner main loop ONLY:
# except Exception as exc:
#     log.error("Daemon loop iteration failed: %s", exc, exc_info=True)
#     # Continue loop — daemon must never crash
#     continue
# This is the ONE place where broad catch is acceptable, per pattern registry.
```
