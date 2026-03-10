# SU-04 Pseudo-Logic: Global Comms Cross-Project Edge Cases

## File: `src/minion/comms/delivery.py` — `route_cross_repo()`

### Change 1: Narrow coordinator lookup exception (~line 44)

```python
# BEFORE: except Exception: return None
# AFTER:
#   except sqlite3.OperationalError:
#       return None  # DB not found or table missing — agent genuinely not found
#   except PermissionError as exc:
#       return {"error": f"Coordinator DB permission denied: {exc}"}
#   except sqlite3.DatabaseError as exc:
#       return {"error": f"Coordinator DB corrupt or unreadable: {exc}"}
```

### Change 2: Schema compatibility check (after CREATE TABLE IF NOT EXISTS, ~line 81)

```python
# After ensuring messages table exists in target project DB:
# 1. cursor.execute("PRAGMA table_info(messages)")
# 2. existing_columns = {row["name"] for row in cursor.fetchall()}
# 3. expected_columns = {"id", "from_agent", "to_agent", "message", "msg_type", "timestamp", ...}
# 4. missing = expected_columns - existing_columns
# 5. If missing:
#      - For each missing column: ALTER TABLE messages ADD COLUMN <col> <type> DEFAULT <default>
#      - Or: log warning and insert with only available columns
#      - Prefer ALTER TABLE — it's forward-compatible
```

### Change 3: Clear error returns for failure modes

```python
# Before remote DB insert attempt:
# IF target project path doesn't exist:
#   return {"error": f"Target project at {path} does not exist."}
# IF target project DB is locked (catch sqlite3.OperationalError "database is locked"):
#   return {"error": f"Target project DB at {path} is locked. Try again later."}
# IF permission denied on inbox directory:
#   catch PermissionError from os.makedirs/atomic_write_file
#   return {"error": f"Permission denied writing to inbox at {inbox_path}"}
```

### Edge case: stale agent registry
```python
# Current: checks os.path.exists(remote_db_path) and returns None
# Change: return error dict instead of None for stale paths
#   return {"error": f"Target project at {path} no longer exists. Agent registry may be stale."}
```
