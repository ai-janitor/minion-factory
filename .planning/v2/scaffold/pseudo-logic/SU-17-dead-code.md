# SU-17 Pseudo-Logic: Dead Code and Unreachable Paths

## 4.5.1 — Scaling endpoints

```python
# Step 1: Check router.py for scaling endpoint registration
#   grep "scaling" src/minion/network/router.py
#
# Step 2: Decision
#   IF not registered AND scaling is experimental/deferred:
#     - Delete src/minion/network/handlers/scaling.py
#     - Remove any scaling imports from router.py, __init__.py
#     - Document: "scaling endpoints REMOVED — deferred to v3"
#   IF registered but unreachable:
#     - Fix registration or remove
#   IF registered and working:
#     - Add tests, document as "WIRED"
#
# CONTRACT E-09: document decision for SU-18
```

## 4.5.2 — HTTP request logging

```python
# In src/minion/network/server.py:
#
# Add access logging middleware or handler:
#   import logging, time
#   log = logging.getLogger(__name__)
#
#   # Before request: record start time
#   # After response: log.info("%s %s %d %dms", method, path, status_code, duration_ms)
#
# Implementation depends on framework (likely aiohttp or similar):
#   - If aiohttp: use middleware
#   - If custom: wrap handler dispatch
#   - Do NOT log request/response bodies (may contain secrets)
```

## 4.5.3 — TaskDB post-close error

```python
# In src/minion/db/connection.py:
#
# Option A: Wrap connection object
#   class SafeConnection:
#       def __init__(self, conn):
#           self._conn = conn
#           self._closed = False
#       def close(self):
#           self._conn.close()
#           self._closed = True
#       def cursor(self):
#           if self._closed:
#               raise RuntimeError("Database connection is closed. Re-open with get_db().")
#           return self._conn.cursor()
#
# Option B: Add check in get_db()
#   IF existing connection is closed, create new one instead of returning closed one
```

## 4.5.4 — Intel auto-link bare except

```python
# In src/minion/intel/link_doc.py (or wherever auto-link lives):
#
# Find: except Exception  (or except:)
# Replace with: except sqlite3.IntegrityError
#   (duplicate link is the only expected failure)
# All other exceptions should propagate
```

## 4.5.5 — Generic file names

```python
# Audit: find src/minion -name "utils.py" -o -name "helpers.py" -o -name "misc.py" -o -name "common.py"
# For each found:
#   - Read contents to understand what it does
#   - Rename to describe contents (e.g., utils.py with path functions -> path_helpers.py)
#   - Update ALL imports referencing the old name
#   - grep -r "from minion.old_name" to find all references
```
