# SU-21: DAG Scaffolding Enforcement — Mechanical Gate

**Wave:** 6 (depends on SU-03)
**Requirements:** 5.4.2
**Dependencies:** SU-03
**Dependents:** None

---

## Purpose

Add a mechanical gate in the DAG flow that prevents advancing past the scaffolding stage without evidence of scaffolding completion. Currently, "no code without scaffolding" is enforced only by prompts.

## Requirements Traceability

- **5.4.2 (DAG Scaffolding Enforcement):** "Mechanically block code commits without scaffolding stage completion."

## Dependencies

- **SU-03 (DAG Self-Review):** Both modify `complete_phase()` validation logic. SU-03 adds self-review check, this adds scaffolding check. Both are additive AND — must not conflict.

## Behavior

### Current State
- `complete_phase()` validates agent class and transition legality
- No check for scaffolding artifacts
- Flow YAML files define stages including a "scaffolding" stage for some flows (e.g., feature flow)

### Target Behavior

**Gate condition:** When advancing FROM the scaffolding stage (e.g., completing scaffolding to move to in_progress):

1. Query the task's `files` field — this lists the files the task expects to create/modify
2. For each file in the list: verify the file exists on disk (it should have been created as a stub)
3. Optionally: verify each file has a comment header (the first non-empty line starts with `#` or `//` or `"""`)
4. If files field is empty: allow advancement with a warning "No files listed — scaffolding check skipped"
5. If any listed file is missing: return error `{"error": "BLOCKED: Scaffolding incomplete. Missing files: <list>. Create stubs before advancing."}`

**Integration with complete_phase():**
- Add the scaffolding check AFTER SU-03's self-review check
- The check fires only when `current_status` matches a scaffolding stage name
- Scaffolding stage names: look up in the flow definition — stages with name containing "scaffold" or with a `gate: "scaffolding"` attribute

### Gate Configuration (flow YAML)

**Option A:** Add `gate: "scaffolding"` attribute to the scaffolding stage in flow YAML:
```yaml
scaffolding:
  description: "Create file stubs with comment headers"
  next: in_progress
  gate: scaffolding
  workers: [coder]
```

**Option B:** Hard-code scaffolding stage detection by name pattern. Less flexible but simpler.

**Recommendation:** Option A — it's extensible and follows the existing flow YAML pattern (stages already have attributes like `terminal`, `skip`, `spawns`).

### Gate Implementation

When `complete_phase()` encounters a stage with `gate: "scaffolding"`:

1. Read task's `files` field (comma-separated paths)
2. Parse into list of file paths
3. Resolve paths relative to project root
4. For each path: `os.path.exists(path)` — must be True
5. Optionally: read first 10 lines, check for comment header
6. If all pass: allow phase completion
7. If any fail: return error dict with missing file list

### Inputs/Outputs

- **Input:** Same as `complete_phase()` — agent_name, task_id, passed, reason
- **Output:** New error case: `{"error": "BLOCKED: Scaffolding incomplete. Missing: [file1, file2]"}`
- **No new parameters** — the gate reads existing task data (files field)

## Constraints

- Must coordinate with SU-03 (both modify complete_phase)
- Must not break flows that don't have a scaffolding stage
- Must not break tasks with empty files field
- Gate fires only on scaffolding stages — other stages are unaffected
- File existence check must use the project root as base path (from defaults.py)

## Edge Cases

1. **No files listed on task:** Scaffolding check is skipped with a warning. The task may not have specified expected files.
2. **Files field has wildcard patterns:** e.g., `src/minion/new_module/*.py`. Glob the pattern — at least one matching file must exist.
3. **Files created but empty:** A zero-byte file counts as "exists" for the scaffolding check. The comment header check is optional (configurable).
4. **Flow without scaffolding stage:** Most flows don't have a scaffolding stage. Gate doesn't fire. No change in behavior.
5. **Lead override:** Should leads be able to bypass the scaffolding gate? Probably yes — add lead bypass similar to SU-03's self-review bypass.
6. **Relative vs absolute paths:** Files field may contain relative paths (`src/minion/foo.py`) or absolute paths. Normalize to absolute using project root.

## Current State

- complete_phase() exists with class eligibility and transition checks
- Flow YAML stages have attributes but no `gate` attribute yet
- Task `files` field exists as a comma-separated string
- The Stage dataclass in dag.py has a `gate` field already: `gate: str | None = None`

## Test Contract

- **Test 1:** Task with files `["src/test.py"]`. File doesn't exist. Try to complete scaffolding phase. Assert BLOCKED.
- **Test 2:** Task with files `["src/test.py"]`. Create the file. Complete scaffolding phase. Assert success.
- **Test 3:** Task with empty files field. Complete scaffolding phase. Assert success with warning.
- **Test 4:** Flow without scaffolding stage. Complete any phase. Assert no scaffolding check fires.
- **Test 5:** Lead agent completes scaffolding without all files. Assert success (lead bypass).
