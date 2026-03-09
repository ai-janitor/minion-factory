# AU-05: Daemon Runtime Deep Dive

## Purpose

Line-by-line audit of the daemon runtime — long-running background process with mixin pattern, threading, and broad exception handling. High complexity due to concurrency and resilience requirements.

## Scope

| Directory/File | Description |
|----------------|-------------|
| `src/minion/daemon/__init__.py` | Package exports |
| `src/minion/daemon/runner.py` | Main runner class (if exists) |
| `src/minion/daemon/runner/__init__.py` | Runner package init (if subdirectory) |
| `src/minion/daemon/runner/_execution.py` | Execution mixin |
| `src/minion/daemon/runner/_polling.py` | Polling mixin |
| `src/minion/daemon/runner/_hp.py` | Heartbeat/health mixin |
| `src/minion/daemon/runner/_state.py` | State management mixin |
| `src/minion/daemon/runner/_watcher_mode.py` | File watcher mixin |
| `src/minion/daemon/config.py` | Daemon config (duplicates crew/config.py) |
| `src/minion/daemon/contracts.py` | Daemon behavioral contracts |
| `src/minion/daemon/triggers.py` | Trigger/threshold logic |
| `src/minion/daemon/monitoring.py` | Basic monitoring/status |
| Plus any other files in `src/minion/daemon/` |

Read ALL files in `src/minion/daemon/` including `runner/` subdirectory.

## Skills to Evaluate

### CS Foundations — Consistency & State (CS-CONSIST, all 5 rules)
- **CONSIST-1:** Consistency model — daemon's internal state consistency
- **CONSIST-2:** Transaction boundaries — daemon operations atomic?
- **CONSIST-3:** Concurrency strategy — threading with Lock
  - **How to check:** Read all mixin files. Map all threading.Lock usage. Check lock granularity (global lock vs per-resource).
  - **Evidence for YES:** Locks protect specific shared state, documented.
  - **Evidence for NO:** Single coarse lock, or locks missing on shared state access.
- **CONSIST-4:** Idempotency — daemon poll operations safely retriable?
- **CONSIST-5:** Ordering — poll/execute ordering matters?

### CS Foundations — Scale & Performance (CS-SCALE, all 5 rules)
- **SCALE-1:** Expected load — 1-50 agents, daemon per agent
- **SCALE-2:** Hot path — polling loop (every few seconds)
  - **How to check:** Read _polling.py. What's the poll interval? What happens each poll cycle?
- **SCALE-3:** Caching — any caching in daemon?
- **SCALE-4:** Big-O — poll cycle complexity
- **SCALE-5:** Resource bounds — memory/disk/connection limits
  - **How to check:** Check for unbounded growth (log accumulation, message queue growth, connection leaks).

### CS Foundations — Error & Failure Modes (CS-ERR, all 5 rules)
- **ERR-1:** Failure taxonomy — daemon failure categories
- **ERR-2:** Retry strategy — implicit retry via poll loop?
- **ERR-3:** Partial failure — one mixin fails, others continue?
- **ERR-4:** Degradation strategy — broad `except Exception: pass`
  - **How to check:** Grep for `except Exception` and `except:` in daemon/. Count occurrences. Classify: intentional resilience vs swallowed errors.
  - **Evidence for YES:** Each broad except has a comment explaining why.
  - **Evidence for NO:** Broad except without logging or justification.
- **ERR-5:** Observability — how are daemon failures detected?

### Clean Architecture (selected rules)
- **CA-DEP-1:** Dependencies inward — daemon/ imports
- **CA-SOLID-1:** SRP — each mixin has one responsibility
- **CA-SOLID-4:** ISP — no transitive dependencies on unused modules

### Pragmatic Programmer (selected rules)
- **PP-CRAFT-1:** No programming by coincidence — mixin interactions intentional
- **PP-DECOUPLE-1:** No train wrecks — mixin method chaining
- **PP-DECOUPLE-4:** Prefer interfaces/delegation over inheritance — mixins ARE a delegation pattern (but check if properly scoped)
- **PP-ORTH-1:** Components self-contained — each mixin independent?
  - **How to check:** Read each mixin. Does _execution depend on _state? Does _polling depend on _hp? Map mixin interdependencies.
- **PP-ORTH-3:** Change to one mixin doesn't ripple to others
- **PP-CONTRACT-1:** Preconditions — daemon start requirements
- **PP-CONTRACT-2:** Crash early — does daemon crash or silently continue on fatal errors?

### Implementation Coding Core (selected rules)
- **IC-HDR-1 through IC-HDR-5:** Reference AU-00 systemic finding
- **IC-SCALE-1:** 10x/100x/1000x — what if 100 agents run daemons?
- **IC-SCALE-2:** Timeouts on external calls — does daemon timeout on poll, send, heartbeat?
- **IC-SCALE-3:** Streaming/limiting — file I/O in watcher mode bounded?
- **IC-SCALE-4:** Assumptions documented

## Audit Procedure

### Step 1: Mixin Architecture Analysis
1. Read all files in daemon/runner/ (or runner.py if not a subdirectory)
2. Map the mixin class hierarchy: which class inherits which mixins?
3. Map mixin interdependencies: which mixin calls methods from which other mixin?
4. Check: are mixins truly orthogonal or secretly coupled?
5. Check: is there a composition root that wires them together?

### Step 2: Concurrency Analysis
1. Find all threading.Lock instances
2. Map what each lock protects
3. Check for potential deadlocks (nested locks, lock ordering)
4. Check for unprotected shared state (state accessed without lock)
5. Check for thread safety of SQLite access from daemon threads

### Step 3: Resilience Pattern Analysis
1. Grep for `except Exception` and `except:` in all daemon files
2. For each: what is caught, what happens (log? pass? retry?), is it intentional?
3. Classify: intentional resilience vs swallowed errors
4. Check: is there a distinction between fatal and transient errors?

### Step 4: Config Duplication Check (Boundary B-07)
1. Read `daemon/config.py` in full
2. Read `crew/config.py` in full (from AU-03 scope)
3. Diff the parsing logic: what's duplicated, what's different?
4. Note: AU-10 owns the cross-cutting DRY finding. AU-05 notes the daemon-side details.

### Step 5: Lifecycle Boundary Check (Boundary B-05)
1. Read `daemon/contracts.py` — daemon's lifecycle contract
2. Compare with crew's lifecycle model (from AU-03)
3. Check: do lifecycle state names match?
4. Check: do transition rules agree?

### Step 6: Monitoring and Observability
1. Read `daemon/monitoring.py`
2. Check: what does monitoring actually monitor?
3. Check: how are issues reported (log, metric, alert)?
4. Check: is monitoring sufficient for the daemon's complexity?

### Step 7: Rule-by-Rule Evaluation

## Expected Findings from Research

1. **Mixin pattern** — _execution, _polling, _hp, _state, _watcher_mode. Orthogonality questionable — need to verify interdependencies.
2. **Threading with Lock** — coarse granularity suspected. Need to verify lock coverage.
3. **Broad except: Exception: pass** — intentional resilience pattern for long-running daemon, but may swallow important errors.
4. **Config duplication with crew/config.py** — DRY violation (boundary B-07, cross-cutting finding owned by AU-10).
5. **ERR-5 FAIL:** Monitoring is basic status check, not observability. Logging uses print (part of systemic 3-pattern finding).
6. **IC-SCALE risk:** Resource bounds not documented. Daemon runs indefinitely — memory/connection leak potential.
7. **PP-ORTH risk:** Mixin interdependencies may violate orthogonality.

## Output Format

```markdown
# AU-05 Daemon Runtime Audit Results

## Mixin Architecture
[Class hierarchy, interdependency map]

## Concurrency Model
[Lock inventory, protected state, thread safety assessment]

## Resilience Pattern
[Broad except inventory, classification]

## Filled Checklist

### CS Foundations — Consistency & State
| Rule | Status | Evidence |
|------|--------|----------|
...

### CS Foundations — Scale & Performance
...

### CS Foundations — Error & Failure Modes
...

### Clean Architecture (subset)
...

### Pragmatic Programmer (subset)
...

### Implementation Coding Core (subset)
...

## Findings

| # | Rule | Severity | Affected Files | Description | Remediation |
|---|------|----------|----------------|-------------|-------------|
...

## Strengths
...

## Boundary Checks
### B-05: Daemon <-> Crew Lifecycle
[State consistency assessment]

### B-07: Daemon Config <-> Crew Config
[Duplication assessment — reference AU-10 systemic finding]
```
