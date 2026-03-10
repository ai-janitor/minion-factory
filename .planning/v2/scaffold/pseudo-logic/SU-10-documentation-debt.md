# SU-10 Pseudo-Logic: Documentation Debt — Assumptions and Big-O

## No behavior changes. Comments and docstrings only.

### ASSUMPTION comment pattern:
```python
SOME_CONSTANT = 42
# ASSUMPTION: 42 chosen because <reason> — <why this value> — <consequence if wrong>
```

### Big-O annotation pattern:
```python
def some_function(...):
    """One-line summary.

    Time complexity: O(N) where N = <what N means in this context>.
    Space complexity: O(1) — constant auxiliary space.
    """
```

### Per-file plan:

**daemon/runner/_constants.py:**
- Every timeout, interval, buffer size, retry count gets ASSUMPTION comment
- Example: POLL_INTERVAL, MAX_RETRIES, BUFFER_SIZE, HEARTBEAT_TIMEOUT

**monitoring.py:**
- HP thresholds (100, 75, 50, 25, 0) — ASSUMPTION: why these breakpoints
- Warning level triggers — when does HP generate alerts

**polling.py:**
- HEARTBEAT_INTERVAL (1800s / 30 min) — ASSUMPTION comment
- Poll timeout defaults — ASSUMPTION comment
- poll_loop() — Big-O: O(M + T) per iteration, M=messages, T=tasks
- _collect_messages() — Big-O: O(M), M=unread messages

**defaults.py:**
- MAX_DOC_SIZE — ASSUMPTION comment
- Default port numbers — ASSUMPTION comment
- Default paths — ASSUMPTION comment

**crew/spawn.py:**
- Tmux pane dimensions — ASSUMPTION comment
- Startup delay — ASSUMPTION comment

**db/prune.py:**
- max_age_days=30 — ASSUMPTION comment
- Verify existing Big-O annotation

**tasks/rollup.py:**
- _rollup_task_to_requirement() — Big-O: O(S) where S = sibling count
- _rollup_requirement_to_parent() — Big-O: O(S)
- check_and_rollup() — verify existing Big-O is accurate

**tasks/dag.py:**
- _resolve_skip() — verify existing Big-O
- valid_transitions() — add Big-O: O(T) where T = stages

**comms/send.py:**
- send() — Big-O: O(1) single INSERT + file write

**tasks/gates.py:**
- gate checking functions — Big-O: O(1) per gate
