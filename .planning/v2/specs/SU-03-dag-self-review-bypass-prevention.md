# SU-03: DAG Self-Review Bypass Prevention

**Wave:** 2 (parallel correctness cluster)
**Requirements:** 1.1
**Dependencies:** None
**Dependents:** SU-21

---

## Purpose

Prevent implementing agents from self-closing QE and verify stages. Currently, `complete_phase()` checks agent class eligibility but does NOT check whether the completing agent was the one who implemented the task. This defeats the purpose of independent review.

## Requirements Traceability

- **1.1 (DAG Self-Review Bypass):** "The system must mechanically prevent the same agent that implemented a task from advancing it through QE/verify."

## Dependencies

None. Builds on existing `complete_phase()` in `src/minion/tasks/update_task.py`.

## Behavior

### Current State
- `complete_phase()` (line 128 of update_task.py) checks agent class eligibility for the current stage
- No check exists comparing the requesting agent to the implementing agent
- Any agent with the right class can close QE/verify on their own implementation

### Target State

**Input:** `complete_phase(agent_name, task_id, passed, reason)`

**New validation step** (inserted after the existing class eligibility check at line 167, before DAG transition at line 170):

1. Identify QE and verify stages: query the flow definition for stages where review is the purpose. These are stages whose `workers` field specifies reviewer classes (not the same as the implementing class).
2. Query `transition_log` for the agent who last advanced the task INTO the implementation stage (the stage immediately before the current review stage). This is the "implementer."
3. If `agent_name == implementer` AND current stage is a review stage (QE or verify): return error dict `{"error": "BLOCKED: Agent '<name>' implemented this task and cannot self-review. Assign a different agent for <stage>."}`
4. If no implementer found in transition_log (edge case: task was manually set to this status), allow the completion with a warning.

**Output change:** New error case added to the return type. No change to success output.

### State Changes
- No new DB tables or columns
- No schema changes
- Reads from existing `transition_log` table

### Identifying the Implementer
- Query: `SELECT agent_name FROM transition_log WHERE task_id = ? AND to_status = ? ORDER BY timestamp DESC LIMIT 1` where `to_status` is the implementation stage (e.g., "in_progress", "implement", "fix")
- The implementation stage is determined by walking backward in the flow from the current stage to find the non-review predecessor stage

### Identifying Review Stages
- A stage is a "review stage" if its workers field specifies classes with the `review` capability (from auth.py: classes_with(CAP_REVIEW))
- This is already queryable via `flow.workers_for(current, class_required)` — if the eligible workers for the current stage are all reviewer classes, it's a review stage

## Constraints

- Must not break existing `complete_phase()` behavior for non-review stages
- Must not require schema changes
- The check is additive (AND with existing checks) — failing this check returns an error dict, same as other validation failures
- Performance: one additional DB query (transition_log SELECT) per complete_phase call on review stages only

## Edge Cases

1. **No transition_log entry:** Task was manually set to QE/verify status (e.g., by lead override). Allow completion with warning: `"warning": "No implementer found in transition_log — self-review check skipped."`
2. **Multiple implementers:** Task was re-implemented by a different agent after first rejection. Use the MOST RECENT implementer (ORDER BY timestamp DESC LIMIT 1).
3. **Lead override:** Leads should be able to bypass this check. If agent_class == "lead", skip the self-review check. Leads are trusted to review their own work when necessary.
4. **Task with no flow:** If `_get_flow()` returns None or the flow has no review stages, the check is skipped entirely.
5. **Skipped stages:** If the implementation stage was skipped (skip=true in flow), walk further back in the flow to find the actual implementer.

## Current State

- `complete_phase()` exists at line 128 of update_task.py
- transition_log table exists and is populated by `_log_transition()`
- The function already returns error dicts for validation failures — this is one more check in the same pattern

## Test Contract

- **Test 1:** Agent "coder-a" implements a task (transitions to "in_progress"), then tries to complete QE phase. Assert BLOCKED error.
- **Test 2:** Agent "coder-a" implements, agent "reviewer-b" completes QE phase. Assert success.
- **Test 3:** No transition_log entry for task. Agent completes QE. Assert success with warning.
- **Test 4:** Agent with class "lead" implements and self-reviews. Assert success (lead bypass).
- **Test 5:** Task re-implemented by "coder-b" after rejection. "coder-a" (original implementer) tries to review. Assert success (they're not the most recent implementer).
