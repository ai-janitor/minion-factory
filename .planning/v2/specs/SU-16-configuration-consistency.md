# SU-16: Configuration Consistency — -C Flag, Env Vars, WAL

**Wave:** 5 (parallel within wave)
**Requirements:** 4.4
**Dependencies:** None
**Dependents:** None

---

## Purpose

Verify and close remaining configuration consistency gaps: -C flag env var mutation transparency, network env var routing through defaults.py, and daemon WAL consistency. Research indicates most items were already fixed in v1 — this is primarily verification.

## Requirements Traceability

- **4.4 (Configuration Consistency):** "-C flag mutates env vars non-transparently, network env vars bypass defaults.py, daemon WAL inconsistency."

## Dependencies

None.

## Behavior

### 4.4.1 — -C Flag Transparency

**Current state:** The `-C` / `--project-dir` global flag in `src/minion/cli/main.py` sets `MINION_PROJECT_DIR` env var. This mutates the process environment, which affects all subsequent calls in that CLI invocation.

**Audit target:**
- Read main.py's `-C` flag handler
- Verify: the env var mutation is documented in the help text
- Verify: the mutation is logged at DEBUG level so users can trace it
- Verify: the mutation does not persist after the CLI process exits (it shouldn't — env var mutation is process-scoped)

**Target behavior:**
- `-C` flag help text includes: "Sets MINION_PROJECT_DIR for this invocation"
- If DEBUG logging is enabled, log: `"Setting MINION_PROJECT_DIR=%s (from -C flag)"`
- No persistent side effects

### 4.4.2 — Network Env Vars Through defaults.py

**Current state (from research):** "5 network env vars bypass defaults.py, reading directly from os.environ. FIXED — env vars are now routed through defaults.py."

**Audit target:**
- `grep -r "os.environ" src/minion/ --include="*.py"` — check for remaining direct os.environ reads outside of defaults.py
- Acceptable exceptions: MINION_CLASS (auth.py), MINION_AGENT_NAME (polling.py — spawn-time env var), MINION_HOOKS_BYPASS (hook scripts)
- All MINION_NETWORK_*, MINION_CLUSTER_* vars must go through defaults.py

**Verification:** List all `os.environ` references. For each, verify it either:
1. Routes through defaults.py, OR
2. Is an acceptable exception (documented above)

### 4.4.3 — Daemon WAL Consistency

**Current state (from research):** "connection.py connect() function standardizes WAL and row_factory. FIXED."

**Audit target:**
- Verify `connect()` in `src/minion/db/connection.py` sets WAL mode and row_factory
- Verify all DB connections go through `connect()` or `get_db()` (which calls `connect()`)
- Check for any direct `sqlite3.connect()` calls outside of connection.py

**Verification:** `grep -r "sqlite3.connect" src/minion/` returns results only in connection.py.

## Constraints

- Primarily verification — fix only remaining gaps
- Must not change the -C flag behavior (only improve transparency)
- Must not break existing env var handling

## Edge Cases

1. **Nested -C usage:** `minion -C /path/a comms send -C /path/b` — does the second -C override? Verify behavior and document.
2. **-C with relative path:** `minion -C ../other-project who` — does it resolve correctly? defaults.py should normalize to absolute path.
3. **os.environ in test code:** Test files may use os.environ directly for setup. That's acceptable — the constraint is on production code.
4. **Third-party lib env vars:** If a dependency reads env vars (e.g., Click's own env vars), that's outside our control.

## Current State

- Research says most items FIXED in v1
- This spec is primarily audit + verification + gap closure
- Expected remaining work: 0-2 small fixes

## Test Contract

- **Test 1:** `-C` flag help text mentions MINION_PROJECT_DIR.
- **Test 2:** `grep -r "os.environ" src/minion/` — all hits are in defaults.py or documented exceptions.
- **Test 3:** `grep -r "sqlite3.connect" src/minion/` — all hits are in db/connection.py.
- **Test 4:** All existing tests pass after any changes.
