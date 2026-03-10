# SU-07: Backlog Lineage and Auth Hardening

**Wave:** 2 (parallel correctness cluster)
**Requirements:** 1.7, 1.9, 1.10
**Dependencies:** None
**Dependents:** SU-19 (via auth.py changes)

---

## Purpose

Three related backlog subsystem fixes: (a) ensure requirement_id propagates from promote to task creation, (b) add auth checks on all backlog write mutations via `-C` flag, (c) verify crew display in promote output.

## Requirements Traceability

- **1.7 (Backlog Lineage):** "requirement_id not consistently set on tasks created from promoted backlog items."
- **1.9 (Backlog Auth):** "Backlog operations via -C flag have no auth check — any agent can mutate any project's backlog."
- **1.10 (Test Promote Crew Display):** "Test that promote command correctly displays required crew and available characters."

## Dependencies

None.

## Behavior

### 1.7 — Lineage Propagation

**Current state:**
- `promote()` in promote.py creates a requirement via `register()` (from requirements/crud.py)
- The registered requirement gets an ID in the requirements table
- When tasks are later created for this requirement, they should carry the `requirement_id`

**Target behavior:**
- Verify: `register()` returns the requirement ID
- Verify: `promote()` includes the requirement ID in its return value
- Verify: when a task is created with `task create --requirement <id>`, the `requirement_id` column is set
- If the propagation is broken: fix the `register()` return value or the `task create` parameter passing

**Inputs:** `promote(file_path, origin, db, slug, agent)` — existing signature
**Outputs:** Return dict must include `"requirement_id": <int>` key

### 1.9 — Auth on Cross-Project Backlog Mutations

**Current state:**
- `promote()` has auth gate checking `agent_class == "lead"` (line 127-133)
- Other backlog mutations (add, update, close) via CLI may lack auth checks
- The `-C` flag changes project context — mutations to a foreign project's backlog should require lead class

**Target behavior:**
- All backlog write operations must check agent class when targeting a foreign project
- Affected CLI commands in `backlog_cmds.py`: `backlog add`, `backlog update`, `backlog close`, `backlog promote`
- Auth check: if `-C` flag is active (i.e., `MINION_PROJECT_DIR` != cwd), require class "lead"
- Error message: `"BLOCKED: Backlog mutations on foreign projects require lead class. Current class: <class>"`

**Detection of foreign project:** Compare `os.environ.get("MINION_PROJECT_DIR", os.getcwd())` to actual cwd. If they differ, the `-C` flag is active.

### 1.10 — Crew Display in Promote Output

**Current state:**
- `promote()` returns `required_crew` and `available_characters` in its result dict
- `_scan_crew_characters()` scans crew YAMLs for matching characters
- CLI output rendering of these fields needs test verification

**Target behavior:**
- Verify: promote output includes `required_crew` (list of needed agent classes for the requirement's DAG flow)
- Verify: promote output includes `available_characters` (list of {name, class, crew, snippet} dicts)
- Test must verify the CLI renders these fields in human-readable format

## Constraints

- Auth checks must not break local backlog operations (no `-C` flag = no extra auth)
- Promote already has auth — the fix is extending auth to add/update/close
- Must not change the `promote()` function signature

## Edge Cases

1. **No agent registered (anonymous backlog add):** If `MINION_CLASS` env var is not set and no agent is registered, backlog add should still work locally. Only cross-project mutations need auth.
2. **Lead agent on foreign project:** Lead agents should pass the auth check for all backlog operations.
3. **requirement_id already set:** If tasks already have requirement_id from a previous promote, re-promote should not create duplicate requirements.
4. **Empty crew scan:** If no crew YAMLs exist or no characters match, promote should succeed with empty `available_characters` list.
5. **Promote with no flow_type:** If the requirement has no associated DAG flow, `required_crew` should be empty (no specific classes needed).

## Current State

- promote() has auth gate for lead class
- backlog add/update/close likely lack auth gates
- requirement_id propagation needs verification
- crew display exists in promote return value

## Test Contract

- **Test 1:** Promote a backlog item. Assert `requirement_id` in return dict is a positive integer.
- **Test 2:** Create a task for the promoted requirement. Assert `requirement_id` on the task row matches.
- **Test 3:** Attempt `backlog add` via `-C` flag with non-lead class. Assert BLOCKED error.
- **Test 4:** Attempt `backlog add` via `-C` flag with lead class. Assert success.
- **Test 5:** Promote a backlog item. Assert `required_crew` and `available_characters` in output.
- **Test 6:** Local `backlog add` without `-C` flag and without registered agent. Assert success (no auth required locally).
