# AU-03: Comms + Crew + Lifecycle Deep Dive

## Purpose

Line-by-line audit of the communication system, crew management, and agent lifecycle against applicable skill checklists. These domains are grouped because they change together (CA-COMP-4): agent registration triggers comms registration, and crew lifecycle orchestrates comms.

## Scope

| Directory/File | Description |
|----------------|-------------|
| `src/minion/comms/__init__.py` | Package exports |
| `src/minion/comms/inbox.py` | Message inbox (receive) |
| `src/minion/comms/send.py` | Message sending |
| `src/minion/comms/router.py` | Message routing |
| `src/minion/comms/channels.py` | Channel management (if exists) |
| `src/minion/comms/broadcast.py` | Broadcast messaging (if exists) |
| `src/minion/crew/__init__.py` | Package exports |
| `src/minion/crew/config.py` | Crew configuration (YAML parsing — canonical) |
| `src/minion/crew/spawn.py` | Agent spawning (tmux sessions) |
| `src/minion/crew/daemon.py` | Crew's daemon interface |
| `src/minion/crew/registry.py` | Agent registry |
| `src/minion/crew/status.py` | Agent status tracking |
| `src/minion/crew/lifecycle.py` | Crew lifecycle management (if exists) |
| `src/minion/lifecycle.py` | Top-level lifecycle module |

Read ALL files in `src/minion/comms/` and `src/minion/crew/`, plus `src/minion/lifecycle.py`.

## Skills to Evaluate

### CS Foundations — Communication & Integration (CS-COMM, all 5 rules)
- **COMM-1:** Communication style — sync or async?
  - **How to check:** Read comms/ send and inbox modules. Is messaging sync (direct DB write/read) or async (queue/callback)?
  - **Evidence for YES:** Clear sync or async pattern documented/implemented.
  - **Evidence for NO:** Mixed patterns without clear intent.
- **COMM-2:** Integration points — external systems, contracts, failure modes?
  - **How to check:** Read crew/spawn.py — tmux integration. Check subprocess calls, error handling on spawn failure.
- **COMM-3:** Event taxonomy — named and versioned events?
  - **How to check:** Check for message types/categories in comms. Are message types enumerated?
- **COMM-4:** API style chosen — message-passing pattern?
  - **How to check:** Read the comms API. Is it publish/subscribe, point-to-point, broadcast, or hybrid?
- **COMM-5:** Serialization format — JSON, plain text?
  - **How to check:** Check message format in comms/send.py. What's stored in the DB?

### CS Foundations — Error & Failure Modes (CS-ERR, selected rules)
- **ERR-1:** Failure taxonomy — what if spawn fails? What if message delivery fails?
- **ERR-3:** Partial failure — what if agent registration succeeds but comms registration fails?
- **ERR-4:** Degradation strategy — does crew degrade gracefully when a spawn fails?

### Clean Architecture (selected rules)
- **CA-DEP-1:** Dependencies point inward — comms/ and crew/ should not import from cli/
- **CA-DEP-5:** Dependency Inversion at boundaries — check crew -> daemon interface
- **CA-SOLID-1:** SRP — each module has one reason to change
- **CA-SOLID-3:** LSP — if protocol/interface pattern used, check substitutability
- **CA-BOUND-3:** Data crossing boundaries is simple structures

### Pragmatic Programmer (selected rules)
- **PP-ORTH-1:** Components self-contained — comms/ independent from crew/?
- **PP-ORTH-3:** Change to one module doesn't ripple
- **PP-DRY-1:** Single authoritative representation — no duplicated logic between comms and crew
- **PP-CONTRACT-1:** Preconditions/postconditions — agent registration contract (what must be true before registering?)
- **PP-CONTRACT-2:** Crash early — what happens on bad input to register/send?
- **PP-CONTRACT-4:** Finish what you start — agent register -> deregister lifecycle complete?

### Implementation Coding Core (selected rules)
- **IC-HDR-1 through IC-HDR-5:** File headers — reference AU-00 systemic finding

## Audit Procedure

### Step 1: Communication Model Analysis
1. Read all files in `src/minion/comms/` in full
2. Map the message flow: sender -> routing -> inbox -> receiver
3. Identify: message types, delivery guarantees, ordering
4. Check: what happens to undelivered messages?

### Step 2: Crew Lifecycle Walk
1. Read all files in `src/minion/crew/` in full
2. Map the agent lifecycle: register -> spawn -> active -> deregister
3. Read `src/minion/lifecycle.py`
4. Check: state machine explicit? Transitions validated?
5. Check: what happens on abnormal termination? (agent dies without deregister)

### Step 3: Integration Points
1. Read crew/spawn.py — tmux integration
2. Check: subprocess error handling
3. Check: what if tmux is not installed? What if session name conflicts?
4. Check: cleanup on spawn failure

### Step 4: Boundary B-05 Check (Crew <-> Daemon)
1. Read crew/daemon.py — crew's view of daemon
2. Compare with daemon's contracts (src/minion/daemon/contracts.py if exists)
3. Check: do both sides agree on lifecycle states?
4. Check: state transition names match between crew and daemon

### Step 5: Configuration Ownership
1. Read crew/config.py — canonical YAML parsing
2. Note: daemon/config.py duplicates this (AU-05 will deep dive the duplication, AU-10 owns the cross-cutting finding)
3. Check: what config values does crew use?

### Step 6: Rule-by-Rule Evaluation

## Expected Findings from Research

1. **Comms is sync** — direct DB write/read, no message queue. Appropriate for scale.
2. **Crew spawns via tmux** — subprocess calls to tmux, potential failure point.
3. **Lifecycle state machine** may be implicit (not formally validated transitions).
4. **Boundary B-05 risk:** crew's lifecycle model and daemon's lifecycle model may have inconsistent state names.
5. **ERR-3 risk:** agent registration + comms registration are separate operations — what if one fails?
6. **PP-CONTRACT-4:** Register/deregister lifecycle — does deregister clean up all comms state?
7. **IC-HDR FAIL:** Systemic (reference AU-00).

## Output Format

```markdown
# AU-03 Comms + Crew + Lifecycle Audit Results

## Communication Model
[Message flow diagram, delivery guarantees, ordering]

## Lifecycle State Machine
[States, transitions, validation rules]

## Filled Checklist

### CS Foundations — Communication
| Rule | Status | Evidence |
|------|--------|----------|
| COMM-1 | YES/NO/N/A | [specific evidence] |
...

### CS Foundations — Error & Failure Modes (subset)
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

## Boundary Check: B-05 (Crew <-> Daemon)
[Lifecycle state consistency assessment]
```
