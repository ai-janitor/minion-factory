# SU-16 Pseudo-Logic: Configuration Consistency

## Primarily audit and verification — minimal code changes expected.

## 4.4.1 — -C flag transparency

```python
# In src/minion/cli/main.py, -C flag handler:
#
# Current behavior: sets os.environ["MINION_PROJECT_DIR"] = project_dir
#
# Add:
#   1. Update help text: help="Sets MINION_PROJECT_DIR for this invocation. ..."
#   2. Add debug log: log.debug("Setting MINION_PROJECT_DIR=%s (from -C flag)", project_dir)
#   3. Normalize to absolute path: project_dir = os.path.abspath(project_dir)
```

## 4.4.2 — Network env vars through defaults.py

```python
# Audit: grep -r "os.environ" src/minion/ --include="*.py"
# For each hit:
#   IF in defaults.py -> OK
#   IF reading MINION_CLASS -> OK (auth.py, documented exception)
#   IF reading MINION_AGENT_NAME -> OK (polling.py, spawn-time env var)
#   IF reading MINION_HOOKS_BYPASS -> OK (hook scripts)
#   IF reading MINION_NETWORK_* or MINION_CLUSTER_* -> MUST go through defaults.py
#   IF any other direct read -> evaluate and route through defaults.py
```

## 4.4.3 — Daemon WAL consistency

```python
# Audit: grep -r "sqlite3.connect" src/minion/ --include="*.py"
# Every hit MUST be in src/minion/db/connection.py
# IF found elsewhere: refactor to use connect() or get_db()
#
# Verify in connection.py:
#   conn.execute("PRAGMA journal_mode=WAL")
#   conn.row_factory = sqlite3.Row
```
