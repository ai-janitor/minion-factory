# SU-04: Global Comms Cross-Project Edge Cases

**Wave:** 2 (parallel correctness cluster)
**Requirements:** 1.2
**Dependencies:** None
**Dependents:** SU-19

---

## Purpose

Fix `route_cross_repo()` to handle edge cases in cross-project message delivery. The function currently has a silent failure mode and an overly broad exception handler that masks real errors.

## Requirements Traceability

- **1.2 (Global Comms Delivery Failure):** "comms send with -C targeting a foreign project fails silently when the target project's messages table doesn't exist."

## Dependencies

None. This is a standalone fix to `src/minion/comms/delivery.py`.

## Behavior

### Current State (from source code review)

`route_cross_repo()` in delivery.py already handles the missing-table case:
- Line 69-81: `CREATE TABLE IF NOT EXISTS messages (...)` ensures the table exists before INSERT
- Line 44: `except Exception: return None` on coordinator lookup — this is the problem. It catches ALL exceptions and returns None (agent not found), hiding real errors like DB corruption, permission issues, or network problems.
- Line 89: `except Exception as exc: log.warning(...)` on remote DB insert — logs the error but continues. This is acceptable (file delivered even if DB insert fails).

### Target State

**Change 1: Narrow coordinator lookup exception**
- Current: `except Exception: return None`
- Target: `except sqlite3.OperationalError: return None` — only catch DB-not-found or table-missing errors
- Other exceptions (PermissionError, sqlite3.DatabaseError for corruption) should propagate or be caught and returned as error dicts

**Change 2: Validate message schema compatibility**
- After `CREATE TABLE IF NOT EXISTS`, verify the existing table has the expected columns
- If the target project's messages table has a different schema (e.g., old version without msg_type column), log a warning and attempt delivery with available columns
- Query: `PRAGMA table_info(messages)` — check column names match expected set

**Change 3: Return clear error for common failure modes**
- If coordinator DB is unreachable: return `{"error": "Coordinator DB unreachable — cannot route cross-project message."}`
- If target project DB exists but is corrupt: return `{"error": "Target project DB at <path> is corrupt or locked."}`
- If target project path doesn't exist on disk: return `{"error": "Target project path <path> does not exist."}`

### Inputs
- `to_agent: str` — target agent name
- `from_agent: str` — sender agent name
- `message: str` — message content
- `now: str` — ISO timestamp

### Outputs (updated return type)
- Success: `{"timestamp": now, "status": "sent", "from": from_agent, "to": to_agent, "routed_via": "coordinator", "target_project": path}` (unchanged)
- Partial success: same as above with `"warning"` key (unchanged)
- Failure: `{"error": "..."}` dict (NEW — currently returns None for all failures)
- Not found: `None` (only when agent genuinely not found in coordinator)

### State Changes
- No new tables or columns
- May create messages table in target project DB if it doesn't exist (current behavior preserved)

## Constraints

- Must not break existing successful delivery paths
- Must not add new dependencies
- The `CREATE TABLE IF NOT EXISTS` pattern is correct and must be preserved
- Performance: one additional PRAGMA query on first delivery to a new target (negligible)

## Edge Cases

1. **Coordinator DB doesn't exist:** `get_coordinator_db()` should handle this — but if it raises, return an error dict instead of None.
2. **Target project DB exists but is locked:** sqlite3.OperationalError("database is locked") — return error dict with "try again later" message.
3. **Target project DB has old schema:** Messages table exists but lacks columns (e.g., no `is_cc` column). INSERT should use only columns that exist, or the `CREATE TABLE IF NOT EXISTS` should be `ALTER TABLE ADD COLUMN IF NOT EXISTS` for missing columns.
4. **Agent registered in coordinator but project_path is stale:** Path exists in coordinator DB but directory was deleted. Current code checks `os.path.exists(remote_db_path)` and returns None. Should return error dict: `{"error": "Target project at <path> no longer exists. Agent registry may be stale."}`.
5. **Permission denied on target inbox:** `os.makedirs(remote_inbox)` or `atomic_write_file()` fails with PermissionError. Must catch and return error dict, not crash.

## Current State

- `route_cross_repo()` exists and works for the happy path
- Messages table auto-creation already implemented
- Main issue: overly broad exception handling hiding real errors

## Test Contract

- **Test 1:** Deliver message to valid target project. Assert success dict returned.
- **Test 2:** Deliver to agent not in coordinator DB. Assert None returned.
- **Test 3:** Deliver to agent whose project_path doesn't exist on disk. Assert error dict with descriptive message.
- **Test 4:** Deliver to agent whose project DB is locked. Assert error dict (not None, not crash).
- **Test 5:** Deliver to agent whose project has old-schema messages table. Assert message still delivered (graceful degradation).
