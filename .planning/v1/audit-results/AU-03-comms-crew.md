# AU-03 Comms + Crew + Lifecycle Audit Results

**Auditor:** AU-03
**Date:** 2026-03-09
**Scope:** `src/minion/comms/` (6 files), `src/minion/crew/` (9 files), `src/minion/lifecycle.py`

---

## Communication Model

### Message Flow

```
sender → send() → inbox discipline check → staleness check →
  → write content_file to .work/inbox/{to_agent}/ (atomic_write_file)
  → INSERT INTO messages (metadata: from, to, content_file, timestamp)
  → auto-CC lead
  → trigger word scan
  → commit
```

### Delivery Guarantees

- **Local:** Synchronous — DB write + filesystem write in same transaction scope. Content file written first, then DB INSERT. If DB insert fails, content file exists but is unreferenced (orphan).
- **Cross-repo (delivery.py):** File written to remote project's inbox dir, then DB INSERT to remote project's SQLite. If DB INSERT fails, file still delivered with a warning. Partial delivery is possible.
- **Global (send_global):** Three-tier fallback: coordinator DB → network API → offline queue. Graceful degradation documented in code.

### Ordering

- Messages ordered by `timestamp` (ISO 8601 strings). SQLite rowid provides insertion order as fallback.
- `check_inbox` sorts by timestamp: `all_messages.sort(key=lambda x: x.get("timestamp", ""))`.
- No sequence numbers or vector clocks — appropriate for scale (single-host, <50 agents).

### Undelivered Messages

- No TTL on messages (DATA-5 from AU-00 confirmed).
- `purge_inbox` exists for manual cleanup with configurable `older_than_hours`.
- No automatic garbage collection of orphaned content files.

## Lifecycle State Machine

### Agent States (Implicit)

States observed in code — **not formally defined as an enum or state machine**:

| State | Set By | Evidence |
|-------|--------|----------|
| `waiting for work` | register() | `register.py:53` — default on INSERT |
| `phoenix_down` | fenix_down() | `lifecycle.py:253` |
| (free-text status) | set_status() | `register.py:324` — any string accepted |

### Transitions

```
(unregistered) → register() → "waiting for work"
"waiting for work" → set_status() → (any string)
(any) → fenix_down() → "phoenix_down"
(any) → deregister() → (removed from DB)
(any) → retire_agent() → (flag set + deregistered)
```

**Critical observation:** `set_status()` accepts any arbitrary string. No validation of valid transitions. No state machine enforcement. The lifecycle is **implicit** — a convention, not a mechanism.

### Interrupt/Retire Flags

- `agent_interrupt` and `agent_retire` tables hold flags with `set_at`/`set_by`.
- Daemon run loop checks these flags — not validated in comms layer.
- `retire_agent()` sets flag AND deregisters — atomic from caller's perspective.

---

## Filled Checklist

### CS Foundations — Communication (COMM)

| Rule | Status | Evidence |
|------|--------|----------|
| COMM-1 | **YES** | Synchronous request/response. `send()` writes to DB and returns result dict. `check_inbox()` reads from DB and returns messages. No async, no callbacks, no queues. Pattern documented clearly in module docstrings. |
| COMM-2 | **YES** | External integrations identified and handled: (1) tmux subprocess calls in `crew/_tmux.py` and `crew/spawn.py`, (2) coordinator DB (cross-repo), (3) network API client (tier 3), (4) filesystem (content files). Each has try/except with fallback. |
| COMM-3 | **NO** | No formal event taxonomy. Messages are untyped — `content_file` is a free-text markdown file. No `message_type` field. Trigger words (`moon_crash`, `stand_down`) are detected by string scanning, not by message type. The `is_cc` flag is the only structural typing. |
| COMM-4 | **YES** | Point-to-point messaging (sender → recipient) with broadcast support (`to_agent = 'all'`). Auto-CC to lead. Clear hybrid pattern: direct + broadcast. |
| COMM-5 | **YES** | JSON for structured data (return dicts serialized by CLI). Markdown for message content (`.md` files in inbox/). YAML for crew config. Consistent with codebase-wide pattern. |

### CS Foundations — Error & Failure Modes (ERR subset)

| Rule | Status | Evidence |
|------|--------|----------|
| ERR-1 | **NO** | No failure taxonomy. `register.py` uses dict-return `{"error": ...}` for validation failures. `delivery.py` returns `None` for lookup failures. `_tmux.py` uses `print(WARNING:...)` to stderr. Three different error patterns in scope. No custom exceptions. |
| ERR-3 | **NO** | Partial failure paths exist but are not atomic. `register()` does: (1) local DB insert, (2) coordinator DB insert, (3) network registration. Steps 2 and 3 each have `except Exception: pass/warn`. If step 2 fails, agent is registered locally but not globally — no rollback, no retry, just a stderr warning. Similarly, `delivery.py:route_cross_repo` writes file then attempts DB insert — if DB insert fails, file is orphaned with a warning. |
| ERR-4 | **YES** | Graceful degradation by design. Network tier is optional (`except Exception: pass`). Coordinator DB failures produce warnings but don't block registration. `send_global()` has 3-tier fallback: coordinator → network → offline queue. Daemon designed to survive component failures. |

### Clean Architecture (subset)

| Rule | Status | Evidence |
|------|--------|----------|
| CA-DEP-1 | **YES** | Neither `comms/` nor `crew/` imports from `cli/`. Dependencies point inward: comms/ → db/, fs/; crew/ → comms/, db/, defaults/, auth/. No outward violations. |
| CA-DEP-5 | **NO** | `crew/daemon.py` imports directly from `minion.daemon.config` (concrete `load_config`). No interface/port between crew and daemon — concrete coupling. `from minion.daemon.config import load_config` appears in `init_swarm()`, `start_agent_daemon()`, and `stop_swarm()`. |
| CA-SOLID-1 | **YES** | Each module has a clear single reason to change: `inbox.py` (reading messages), `send.py` (sending messages), `register.py` (agent registration), `delivery.py` (cross-repo routing), `routing.py` (global routing/pruning). Similarly crew: `config.py` (YAML parsing), `spawn.py` (party orchestration), `lifecycle.py` (dismissal), `daemon.py` (daemon process management), `_tmux.py` (tmux pane management). |
| CA-SOLID-3 | **N/A** | No protocol/interface pattern used in comms/ or crew/. No ABCs, no Protocol classes. Provider abstraction (BaseProvider) is in providers/, not in scope. |
| CA-BOUND-3 | **YES** | Data crossing boundaries is simple structures: plain dicts (`dict[str, object]`) returned from all public functions. `AgentConfig` and `SwarmConfig` are frozen dataclasses — simple value objects. No ORM entities or complex objects crossing boundaries. |

### Pragmatic Programmer (subset)

| Rule | Status | Evidence |
|------|--------|----------|
| PP-ORTH-1 | **PARTIAL** | `comms/` and `crew/` are mostly independent packages. However, `comms/register.py` has a lazy import of `crew/spawn._find_crew_file` and `crew/config.load_config` (lines 152-153) — the registration function reaches into crew to merge crew YAML context. `crew/lifecycle.py` imports `comms.deregister` and `crew/spawn.py` imports `comms.register` — these are intentional orchestration dependencies, but they create bidirectional coupling between comms ↔ crew. |
| PP-ORTH-3 | **YES** | Changes to crew/ config format don't ripple to comms/ (crew data merged at register time via lazy import). Adding a new crew field doesn't require comms/ changes. Adding a new message field doesn't require crew/ changes. |
| PP-DRY-1 | **PARTIAL** | `daemon/config.py` has its own `load_config()` that duplicates 80% of `crew/config.py`'s `load_config()`. The dataclasses are now shared (import from crew), but the YAML parsing logic is duplicated line-for-line. The docstring in `daemon/config.py` says "DRY" but the function body is a near-copy. Daemon version lacks `skills` field handling and `scope` field — divergence risk. |
| PP-CONTRACT-1 | **NO** | No formal preconditions/postconditions. `register()` validates inputs (class, transport, model whitelist) but there's no contract declaration. `send()` has implicit preconditions (inbox must be read, context must be fresh, sender must be registered) — enforced in code but not documented as contracts. |
| PP-CONTRACT-2 | **YES** | Crash early pattern followed. `register()` returns `{"error": ...}` immediately on invalid input. `send()` returns error on unread inbox, stale context, unregistered sender, or missing target. `stand_down()` and `retire_agent()` block non-leads. These are fail-fast patterns. |
| PP-CONTRACT-4 | **PARTIAL** | `register()` creates: local DB row, coordinator DB row, network registration, roster file, inbox dir. `deregister()` cleans up: local DB row, file claims, waitlist, coordinator DB row, roster file. **Gap:** deregister does NOT clean up message content files in `.work/inbox/{agent}/`. Messages referencing the agent remain in the DB until purge. Coordinator deregister is `except Exception: pass` — may leave ghost entries. |

### Implementation Coding Core (subset)

| Rule | Status | Evidence |
|------|--------|----------|
| IC-HDR-1 | **NO** | Zero files have formal `PURPOSE:` header. All files use module-level docstrings instead. Example: `register.py` has `"""Agent registration — register, deregister, rename, set_status, set_context, who."""` — informative but not mandated format. **Systemic — reference SF-01.** |
| IC-HDR-2 | **NO** | Zero files have formal `RESPONSIBILITIES:` header. Docstrings describe responsibilities informally. **Systemic — reference SF-01.** |
| IC-HDR-3 | **NO** | Zero files have formal `NOT RESPONSIBLE FOR:` header. **Systemic — reference SF-01.** |
| IC-HDR-4 | **NO** | Zero files have formal `DEPENDENCIES:` header. **Systemic — reference SF-01.** |
| IC-HDR-5 | **YES** | Module docstrings are persistent — no evidence of removal. Docstrings present on all 16 files in scope. |

---

## Findings

| # | Rule | Severity | Affected Files | Description | Remediation |
|---|------|----------|----------------|-------------|-------------|
| F-01 | COMM-3 | Moderate | `comms/send.py`, `comms/inbox.py` | **No message type taxonomy.** Messages are untyped text blobs. No `message_type` field distinguishes commands from status reports from data payloads. Trigger words are detected by string scanning, not message metadata. | Add `message_type` column to messages table (e.g., `direct`, `broadcast`, `command`, `sitrep`, `cc`). Populate at send time. |
| F-02 | ERR-1 | Major | All 16 files in scope | **Three competing error patterns.** (1) dict-return `{"error": ...}` in register/send/lifecycle, (2) return None in delivery.py, (3) print WARNING to stderr in _tmux.py and delivery.py. No custom exception hierarchy. **Systemic — reference SF-03.** | Define error types. Use exceptions for exceptional conditions, dict-return for expected validation failures, eliminate stderr print as error reporting. |
| F-03 | ERR-3 | Major | `comms/register.py:79-129` | **Non-atomic multi-tier registration.** `register()` writes to 3 tiers sequentially: local DB, coordinator DB, network API. Each tier has `except Exception` that swallows failures. If tier 2 fails, agent is locally registered but globally invisible. No rollback, no compensation, no explicit documentation of partial success semantics. | Document partial registration as accepted behavior OR implement compensation (deregister local on coordinator failure). At minimum, return partial_success status. |
| F-04 | PP-CONTRACT-4 | Moderate | `comms/register.py`, `comms/routing.py` | **Incomplete deregister cleanup.** `deregister()` removes DB rows and roster file but does NOT: (a) delete message content files in `.work/inbox/{agent}/`, (b) remove messages in DB where agent is sender, (c) notify in-flight senders. Coordinator deregister silently swallows exceptions. | Add inbox directory cleanup to deregister(). Document what deregister does and does not clean up. |
| F-05 | CA-DEP-5 | Moderate | `crew/daemon.py:15-16, 67` | **Concrete coupling: crew → daemon.** `crew/daemon.py` imports `from minion.daemon.config import load_config` — concrete dependency on daemon's config loader. If daemon config changes, crew is affected. No interface boundary. | Extract shared config loading into a common module or use DIP (define interface in crew, implement in daemon). |
| F-06 | PP-DRY-1 | Major | `crew/config.py`, `daemon/config.py` | **Duplicated config parsing logic.** `daemon/config.py:load_config()` is a near-copy of `crew/config.py:load_config()` (90+ lines duplicated). Dataclasses shared, but YAML-to-dataclass mapping is duplicated. Divergence already exists: crew has `skills` field, daemon does not. **Reference SF-08.** | Extract common YAML→SwarmConfig parsing into a shared function. Both modules call it with their domain-specific overrides. |
| F-07 | PP-ORTH-1 | Minor | `comms/register.py:152-153` | **Bidirectional coupling: comms ↔ crew.** `comms/register.py` lazy-imports `crew.spawn._find_crew_file` and `crew.config.load_config`. `crew/lifecycle.py` imports `comms.deregister`. `crew/spawn.py` imports `comms.register`. This creates a cycle at the package level (comms → crew → comms). | Extract crew-context-merge into a mediator or move it to crew/ (crew calls register, not the other way). |
| F-08 | IC-HDR-1-4 | Major | All 16 files | **No formal comment headers.** Zero files use mandated PURPOSE/RESPONSIBILITIES/NOT RESPONSIBLE/DEPENDENCIES format. All use module docstrings. **Systemic — reference SF-01.** | Add mandated headers to all files. Module docstrings can remain as-is. |
| F-09 | PP-CONTRACT-1 | Moderate | `comms/send.py`, `comms/register.py` | **Implicit contracts not documented.** `send()` has 5 preconditions (inbox read, context fresh, sender registered, target exists locally, no cross-project mismatch) enforced in code but not declared. A caller must read the source to know what's required. | Document preconditions as docstring contracts or add a Contracts section to module headers. |
| F-10 | N/A | Minor | `comms/register.py:321-332` | **set_status() accepts any string.** No validation of status values. Any agent can set any status. Combined with no formal state machine, lifecycle states are unenforced. | Define an enum of valid statuses. Validate in set_status(). |
| F-11 | ERR-3 | Minor | `comms/delivery.py:54-83` | **Cross-repo delivery partial failure.** File written to remote inbox, but DB insert can fail (`except Exception`). File exists but is not indexed in target DB. Target agent may never see the message if they rely on DB polling. Warning printed to stderr only. | Return explicit partial_delivery status. Consider: if DB insert fails, delete the orphaned file OR queue a retry. |

---

## Strengths

1. **WAL snapshot isolation awareness.** `check_inbox()` has explicit comments (lines 25-28) explaining why all reads must happen before writes to avoid snapshot isolation races. This is sophisticated concurrency thinking for a SQLite-based system.

2. **Inbox discipline enforcement.** `send()` blocks sending if the sender has unread messages — a mechanical enforcement of the "read before write" protocol. Combined with staleness checks, this prevents fire-and-forget messaging patterns.

3. **Three-tier routing with graceful degradation.** `send_global()` implements local → coordinator → network → offline queue fallback. Each tier fails gracefully without blocking the others. The offline queue (`network/outbox.queue_message`) ensures no message is lost even when the network is down.

4. **Frozen dataclasses for config.** `AgentConfig` and `SwarmConfig` are `@dataclass(frozen=True)` — immutable after construction. Prevents accidental mutation of config state during crew orchestration.

5. **Auto-CC to lead.** `send()` automatically CCs the lead agent on all messages (line 113-115), ensuring the lead has visibility without requiring senders to remember. Implemented as a separate DB row with `is_cc=1` flag.

6. **Atomic file writes.** All content file writes use `atomic_write_file()` from `minion.fs` — write to temp, then rename. Prevents partial file reads.

7. **Task-protected pruning.** `prune_global()` checks for active tasks before removing stale agents from the coordinator DB (line 101-108). Agents with open work are protected regardless of staleness — prevents orphaned tasks.

8. **Module docstrings on 100% of files.** Every file in comms/ and crew/ has a descriptive module docstring explaining its purpose and scope. Not the mandated format, but documentation exists.

9. **Broadcast deduplication.** `broadcast_reads` table ensures each agent sees each broadcast exactly once. `check_inbox()` queries unread broadcasts and marks them as read atomically.

10. **Clean separation of transport concerns.** `crew/` cleanly separates terminal transport (`terminal.py`), daemon transport (`daemon.py`), and tmux management (`_tmux.py`). Adding a new transport type would be a new file, not modifications to existing ones.

---

## Boundary Check: B-05 (Crew ↔ Daemon)

### Lifecycle State Consistency

- **crew/lifecycle.py** manages: `stand_down` (flag in DB), `retire_agent` (flag + deregister), `interrupt_agent` (flag in DB), `stop_agent_process` (SIGTERM).
- **daemon/** manages: daemon run loop, PID tracking, state files as JSON.
- **Shared concepts:** `agent_interrupt` table (set by crew, read by daemon), `agent_retire` table (set by crew, read by daemon).

### Assessment

The boundary is **functional but fragile**:

1. **State names match.** Both sides use the same DB tables (`agent_interrupt`, `agent_retire`, `flags`). No naming inconsistency.
2. **No formal contract.** `daemon/contracts.py` loads JSON contract files but these are for agent behavior protocols, not for the crew↔daemon interface. The crew↔daemon interface is implicitly defined by shared DB tables.
3. **Config duplication is the main risk.** `crew/config.py` and `daemon/config.py` both define `load_config()` with nearly identical YAML parsing. They produce the same `SwarmConfig` object (shared dataclass), but the parsing paths can diverge (and already have — `skills` field handling differs).
4. **Concrete coupling.** `crew/daemon.py` directly imports `minion.daemon.config.load_config`. If daemon's config loader changes signature or behavior, crew breaks.

**Recommendation:** Extract shared config parsing into a single function. Define the crew↔daemon interface as a shared contract (table schemas + flag semantics), not just implicit DB column names.
