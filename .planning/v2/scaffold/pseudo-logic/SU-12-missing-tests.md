# SU-12 Pseudo-Logic: Missing Test Suites and Verification Artifacts

## Coverage gap analysis method:

```
# 1. List all source modules: find src/minion -name '*.py' -not -name '__init__.py'
# 2. List all test files: ls tests/test_*.py
# 3. For each source module: check if a corresponding test exists
# 4. Mark as: covered, partially covered, uncovered
# 5. For "uncovered": write at least one test
```

## New test files needed:

### tests/test_intel_add_and_find.py
```python
# Test add_doc(): create intel doc, verify it's written to .work/intel/
# Test find_docs(): search by keyword, verify results match
# Test read_doc(): read an existing doc, verify content
# Test link_doc(): link doc to task, verify link in DB
# Use isolated_db fixture + tmp dir for .work/
```

### tests/test_dashboard_render_and_queries.py
```python
# Test queries.py: get_agent_summary(), get_task_pipeline(), get_system_stats()
# Use isolated_db with sample data
# Test render.py: render_agent_table() returns string output
# No HTTP needed — test the query and render functions directly
```

### tests/test_providers_error_log_and_classify.py
```python
# Test _append_error_log (or its shared equivalent after SU-14)
# Test error classification logic
# Use tmp dir for log files, no real HTTP calls
```

## Verification strategy document:

### .planning/v2/verification-strategy.md
```
# Define per-DAG-stage artifacts:
# - open: spec.md exists in .work/tasks/<id>/
# - assigned: file_claims table has entries for task
# - scaffolding: listed files exist on disk (SU-21 enforces this)
# - in_progress: git diff shows changes to claimed files
# - fixed: result.md exists in .work/tasks/<id>/
# - qe: test-report.md exists in .work/tasks/<id>/
# - verify: review.md exists in .work/tasks/<id>/
# - closed: transition_log has complete stage history
#
# This is a DESIGN document. Implementation is SU-21 or future work.
```
