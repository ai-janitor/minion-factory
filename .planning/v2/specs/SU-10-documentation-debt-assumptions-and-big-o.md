# SU-10: Documentation Debt — Assumptions and Big-O Annotations

**Wave:** 3 (depends on SU-01 pattern registry)
**Requirements:** 2.6, 2.7
**Dependencies:** SU-01
**Dependents:** None

---

## Purpose

Add ASSUMPTION comments to files with magic numbers and Big-O documentation to remaining hot paths. Documentation-only changes — no behavior modification. The pattern registry defines annotation formats.

## Requirements Traceability

- **2.6 (Assumption Documentation):** "Key files (daemon constants, HP calculations, token estimates) lack ASSUMPTION comments."
- **2.7 (Big-O Documentation):** "No Big-O documentation on hot paths (dag.py, rollup.py, daemon polling)."

## Dependencies

- **SU-01 (Pattern Registry):** "Documentation Conventions" section defines: ASSUMPTION comment format, Big-O annotation format, what constitutes a "magic number."

## Behavior

### 2.6 — ASSUMPTION Comments

**Annotation format** (from pattern registry):
```python
# ASSUMPTION: <what is assumed> — <why this value> — <consequence if wrong>
```

**Files requiring ASSUMPTION annotations:**

| File | Magic Numbers | Expected Annotations |
|------|--------------|---------------------|
| `src/minion/daemon/runner/*.py` | Timeout values, retry intervals, buffer sizes | 5-8 annotations |
| `src/minion/monitoring.py` | HP thresholds, warning levels | 3-5 annotations |
| `src/minion/polling.py` | Poll intervals, heartbeat frequency (30 min), timeout defaults | 3-4 annotations |
| `src/minion/defaults.py` | MAX_DOC_SIZE, default paths, port numbers | 2-3 annotations |
| `src/minion/crew/spawn.py` | Tmux pane sizes, startup delays | 2-3 annotations |
| `src/minion/db/prune.py` | max_age_days default (30) | 1 annotation |

**Example:**
```python
HEARTBEAT_INTERVAL = 1800  # seconds
# ASSUMPTION: 30-minute heartbeat is sufficient for coordinator freshness —
# chosen because coordinator polling is advisory, not critical path —
# if too infrequent, `minion who` shows stale agents; if too frequent, extra DB writes
```

### 2.7 — Big-O Documentation

**Annotation format:**
```python
def some_function(...):
    """...

    Time complexity: O(N) where N = number of sibling tasks.
    Space complexity: O(1) — constant auxiliary space.
    """
```

**Files requiring Big-O annotations:**

| File | Function | Expected Complexity |
|------|----------|-------------------|
| `src/minion/tasks/rollup.py` | `check_and_rollup()` | O(C * D) — already documented, verify |
| `src/minion/tasks/rollup.py` | `_rollup_task_to_requirement()` | O(S) where S = siblings |
| `src/minion/tasks/rollup.py` | `_rollup_requirement_to_parent()` | O(S) where S = child requirements |
| `src/minion/tasks/dag.py` | `_resolve_skip()` | O(k) — already documented, verify |
| `src/minion/tasks/dag.py` | `valid_transitions()` | O(T) where T = stages with transitions |
| `src/minion/polling.py` | `poll_loop()` | O(M + T) per iteration where M = messages, T = tasks |
| `src/minion/polling.py` | `_collect_messages()` | O(M) where M = unread messages |
| `src/minion/db/prune.py` | `prune_old_records()` | O(R) where R = records older than threshold |
| `src/minion/comms/send.py` | `send()` | O(1) — single INSERT + file write |
| `src/minion/tasks/gates.py` | gate checking functions | O(1) per gate check |

### Inputs/Outputs
- No function signatures change
- No return types change
- Only comments and docstrings are added/modified

## Constraints

- Documentation only — zero behavior changes
- Must use format from pattern registry (SU-01)
- Must reference actual values (not placeholder "TODO" annotations)
- Every magic number literal must get either a named constant or ASSUMPTION comment

## Edge Cases

1. **Already documented:** Some functions (dag.py) already have Big-O annotations. Verify they are correct, don't duplicate.
2. **Constants with obvious meaning:** `0`, `1`, `True`, `False` don't need ASSUMPTION comments. The threshold is: would a new developer ask "why this value?"
3. **Configurable values:** If a magic number should be configurable (e.g., heartbeat interval), note that in the ASSUMPTION comment as "candidate for configuration."
4. **Amortized complexity:** Some functions (poll loop) have different per-call vs amortized complexity. Document both if they differ meaningfully.

## Current State

- Partial ASSUMPTION comments exist (v1 added some)
- dag.py has Big-O on key methods
- rollup.py has Big-O on check_and_rollup
- polling.py needs Big-O on poll_loop and sub-functions
- Daemon runner magic numbers largely undocumented

## Test Contract

- **Test 1:** Grep for magic number literals (integers > 1, not in test files). Assert each has an ASSUMPTION comment or named constant within 2 lines.
- **Test 2:** Grep for public functions in hot-path files. Assert each has a complexity annotation in its docstring.
- **Test 3:** Verify annotations are factually correct by reviewing the implementation logic.
