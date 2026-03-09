# AU-05 Daemon Runtime Audit Results

**Auditor:** AU-05 (Daemon Runtime Deep Dive)
**Date:** 2026-03-09
**Scope:** `src/minion/daemon/` — 18 Python files across 2 packages (daemon/, daemon/runner/)

---

## Mixin Architecture

### Class Hierarchy

```
AgentDaemon(
    StreamMixin,      # _stream.py — stream-json parsing, compaction detection
    HPMixin,          # _hp.py — token usage extraction, HP tracking
    StateMixin,       # _state.py — read/write agent state JSON, respawn reset
    DBMixin,          # _db.py — SQLite operations (invocations, PID, session, fenix)
    PromptMixin,      # _prompts.py — boot/inbox/watcher prompt assembly
    PollingMixin,     # _polling.py — inbox polling, standdown/wake logic
    ExecutionMixin,   # _execution.py — subprocess management, prompt processing
    AlertingMixin,    # _alerting.py — lead agent alerts
    WatcherModeMixin, # _watcher_mode.py — legacy direct-DB watcher mode
)
```

Composition root: `runner/__init__.py` — imports all mixins, defines `AgentDaemon` class with `__init__` and `run()` methods, plus the `_run_poll_mode` / `_poll_generation` orchestration logic.

### Mixin Interdependency Map

Each mixin declares `# Defined in other mixins` stubs at the bottom — a form of implicit interface. This is the dependency graph:

| Mixin | Calls methods from |
|-------|-------------------|
| StreamMixin | (self-contained) |
| HPMixin | `_update_session_id` (DBMixin), `_log` |
| StateMixin | `_log` (implicit — via `_get_rss_bytes` doing DB writes inline) |
| DBMixin | `_log` |
| PromptMixin | (self-contained, delegates to `minion.prompts`) |
| PollingMixin | `_log`, `_write_state` (StateMixin), `_alert_lead_poll` (AlertingMixin) |
| ExecutionMixin | `_log`, `_write_state`, `_alert_lead_poll`, `_update_hp` (HPMixin), `_extract_usage` (HPMixin), `_render_stream_line` (StreamMixin), `_print_stream_start/end` (StreamMixin), `_update_child_pid_in_db` (DBMixin), `_insert_invocation_start` (DBMixin), `_finalize_invocation` (DBMixin), `_check_interrupt` (DBMixin), `_log_compaction` (DBMixin) |
| AlertingMixin | `_log` |
| WatcherModeMixin | `_log`, `_write_state`, `_process_prompt` (ExecutionMixin), `_alert_lead_watcher` (AlertingMixin), `_handle_signal` |

**ExecutionMixin is the most coupled** — it depends on methods from 5 other mixins (StreamMixin, HPMixin, StateMixin, DBMixin, AlertingMixin). This is structurally justified: execution is the orchestration concern that ties monitoring, state, and DB together.

### Assessment

Mixins are **mostly orthogonal by concern** but **not independent** — they rely on the flat mixin composition to resolve cross-references. Each mixin declares the methods it needs from others as `... stubs` with type hints, which serves as an informal interface contract. This is a pragmatic pattern for Python, not a violation per se, but the implicit coupling is real.

---

## Concurrency Model

### Lock Inventory

**Zero `threading.Lock` or `threading.RLock` instances** in the entire daemon package.

### Thread Usage

1. **`threading.Event` (`_stop_event`)** — signal between main loop and signal handler. Correct usage.
2. **`threading.Event` (`_change_signal`)** in `watcher.py` — signal from filesystem watcher thread to main thread. Correct usage.
3. **`threading.Thread` (reader thread)** in `_execution.py:_run_command()` — reads subprocess stdout in a background daemon thread, feeds lines to a `queue.Queue`. Correct usage — Queue is thread-safe.
4. **`watchdog.Observer`** in `watcher.py` — runs a background thread for filesystem events.

### Thread Safety Assessment

The daemon is **effectively single-threaded for business logic**. The only concurrent thread is the stdout reader in `_run_command()`, which communicates via `queue.Queue` (thread-safe). There is no shared mutable state accessed from multiple threads simultaneously.

SQLite access from the main thread uses short-lived connections (`connect` + `commit` + `close` in each method). No connection is shared across threads. The `PRAGMA busy_timeout=5000` protects against concurrent access from other processes (other daemons, CLI commands).

**Verdict:** No locks needed because there is no concurrent access to shared mutable state within a single daemon process. The architecture is correct for its concurrency model.

---

## Resilience Pattern

### Broad Exception Inventory

| File | Line | Pattern | What Happens | Intentional? |
|------|------|---------|-------------|-------------|
| `_db.py:35` | `except Exception as exc` | `_write_agent_runtime` | Logs WARNING, continues | YES — non-critical metadata write |
| `_db.py:50` | `except Exception as exc` | `_update_child_pid_in_db` | Logs WARNING, continues | YES — non-critical PID update |
| `_db.py:75` | `except Exception as exc` | `_insert_invocation_start` | Logs WARNING, returns None | YES — invocation log is observability, not critical path |
| `_db.py:108` | `except Exception as exc` | `_finalize_invocation` | Logs WARNING, continues | YES — end-of-run metadata |
| `_db.py:127` | `except Exception:` | `_check_interrupt` | Silently returns False | **MARGINAL** — swallows error, but fail-open is correct (don't interrupt if check fails) |
| `_db.py:154` | `except Exception as exc` | `_log_compaction` | Logs WARNING, continues | YES — compaction log is observability |
| `_db.py:169` | `except Exception as exc` | `_update_session_id` | Logs WARNING, continues | YES — session_id in DB is non-critical |
| `_db.py:188` | `except Exception:` | `_has_pending_halt` | Silently returns False | **MARGINAL** — fail-open is debatable for halt detection |
| `_db.py:211` | `except Exception as exc` | `_fetch_fenix_records` | Logs WARNING, returns [] | YES — fenix records are resume context, not critical |
| `_state.py:84` | `except Exception:` | `_write_state` (RSS piggyback) | Silently passes | **MARGINAL** — RSS update is non-critical but silence hides DB connection issues |
| `_alerting.py:45` | `except Exception as exc` | `_alert_lead_poll` | Prints to stderr | YES — alert delivery failure must not crash daemon |
| `_alerting.py:59` | `except Exception as exc` | `_alert_lead_watcher` | Logs error message | YES — same rationale |
| `_polling.py:63` | `except Exception as exc` | `_poll_inbox` | Logs error, waits 5s | YES — poll failure is transient |
| `_polling.py:79` | `except Exception as exc` | `_check_available_work` | Logs, returns True (fail-open) | YES — documented fail-open |
| `_hp.py:148` | `except Exception as exc` | `_update_hp` | Logs + prints to stderr | YES — HP write failure must not crash daemon |
| `_execution.py:92` | `except Exception as exc` | `_run_command` (Popen) | Logs error, returns exit 127 | YES — launch failure handled gracefully |

**Summary:** 16 broad `except Exception` blocks. 13 are clearly intentional resilience (logged). 3 are marginal (silent `except Exception:` with `pass` — `_check_interrupt`, `_has_pending_halt`, `_write_state` RSS). The marginal ones swallow errors in non-critical paths but would benefit from at minimum a debug-level log.

### Fatal vs Transient Distinction

- **Fatal:** `FileNotFoundError` for `minion` binary (`_poll_inbox`) correctly triggers `_stop_event.set()` — daemon exits.
- **Transient:** All DB writes, HP updates, alert sends — logged and continued.
- **Context death:** `phoenix_down` at HP <= 5% — triggers respawn (outer loop).
- **Signal:** SIGTERM/SIGINT — clean exit via `_stop_event.set()`.
- **Stand down:** Poll exit code 3 — clean exit.

The taxonomy exists implicitly through code paths but is **not documented as a formal failure taxonomy**.

---

## Config Duplication Check (Boundary B-07)

### daemon/config.py vs crew/config.py

**DRY status: RESOLVED.** The daemon/config.py docstring and code explicitly state:

> `AgentConfig and SwarmConfig are defined once in crew/config.py. Daemon reuses them.`

Line 23: `from minion.crew.config import AgentConfig, SwarmConfig  # noqa: F401`

The `load_config()` function in daemon/config.py is a **separate function** from crew/config.py's `load_config()`, but they parse the same YAML format identically. The key difference:

- daemon/config.py: does NOT parse `skills` or `scope` fields (they have defaults on the dataclass)
- crew/config.py: parses `skills` and `scope` explicitly

Both share identical logic for: project_dir, comms_dir, comms_db, docs_dir, provider validation, agent parsing. This is **structural duplication of parsing logic** even though the dataclasses are shared.

**Assessment:** The dataclass DRY issue from AU-00 (SF-08) has been fixed. The `load_config()` parsing duplication remains — two 100+ line functions doing nearly identical YAML parsing. This should be a shared function with optional field hooks.

---

## Lifecycle Boundary Check (Boundary B-05)

### daemon/contracts.py

Minimal — just a JSON file loader for shared contracts from `docs/contracts/`. No lifecycle state machine defined here.

### Daemon Lifecycle States

From `_write_state()` calls across the codebase:

1. `idle` — waiting for work
2. `working` — processing a message/task
3. `error` — invocation failed (with `failures` count and `last_error`)
4. `phoenix_down` — context exhausted, awaiting respawn
5. `stood_down` — no work available, cheap polling
6. `self_dismissed` — like stood_down but AI session dropped
7. `stopped` — daemon exiting
8. `halted` — HALT message processed, clean exit

These states are **written to a JSON file** (`<agent>.json` in state_dir) and are not validated against a formal state machine. Any string can be written as status.

### Transitions

```
idle -> working (poll returns data)
working -> idle (success, work available)
working -> error (invocation failed)
working -> stood_down (success, no more work)
working -> self_dismissed (success, no more work, self_dismiss=true)
working -> phoenix_down (HP <= 5%)
working -> halted (HALT message processed)
error -> working (retry after backoff)
stood_down -> working (new work arrives)
self_dismissed -> working (new work arrives)
phoenix_down -> idle (auto-respawn, new generation)
any -> stopped (signal or stand_down)
```

**Assessment:** The lifecycle is implicit — defined by code flow, not a formal state machine. There is no validation that prevents invalid transitions. For a daemon of this complexity, this is acceptable but fragile.

---

## Monitoring and Observability

### daemon-level monitoring

No `daemon/monitoring.py` exists. Monitoring is handled externally via:

1. **State JSON file** — `<agent>.json` written by `_write_state()` on every transition
2. **DB tables** — `invocation_log`, `compaction_log`, `agents` (PID, RSS, HP, session_id)
3. **Log output** — structured JSON to stdout via `_log()` (timestamp, agent, level, message)
4. **Stream log** — raw `<agent>.stream.jsonl` for full provider output
5. **Error log** — `<agent>.error.log` for provider-filtered errors
6. **HP alerts** — messages sent to lead when HP drops below thresholds (via `monitoring.py` at package root, not in daemon/)

### Assessment

The daemon has **good observability for its scale**: structured JSON logs, state files, DB instrumentation (invocation_log, compaction_log, HP tracking, RSS tracking), and alerting to lead. The main gap is that logs go to stdout (no file rotation, no log levels beyond INFO).

---

## Filled Checklist

### CS Foundations -- Consistency & State

| Rule | Status | Evidence |
|------|--------|----------|
| CONSIST-1 | **YES** | Strong consistency per SQLite DB. Each daemon operates independently on its own agent rows. No cross-daemon state conflicts because each daemon owns its agent_name's data. |
| CONSIST-2 | **NO** | `_has_pending_halt()` reads messages and `_fetch_fenix_records()` does a multi-step read+update without explicit transaction boundary (`with conn:` not used in `_fetch_fenix_records` — uses manual `conn.commit()`). Most DB methods use individual statements which are auto-committed. The `_finalize_invocation` does a single UPDATE which is atomic. The risk is low because each daemon only writes to its own agent's rows. |
| CONSIST-3 | **YES** | No concurrent access to shared mutable state within a single daemon. The concurrency strategy is "single-threaded business logic with subprocess-based agent execution." The stdout reader thread communicates via `queue.Queue` (thread-safe). No locks needed. |
| CONSIST-4 | **NO** | Poll operations are not explicitly idempotent. `_fetch_fenix_records()` marks records as consumed — calling twice would lose records. `_insert_invocation_start()` creates a new row each call. However, the daemon architecture makes double-execution unlikely (single-threaded loop). |
| CONSIST-5 | **YES** | Message ordering via SQLite `ORDER BY id ASC` in `pop_next_message()`. Task ordering via poll data structure. Fenix records via `ORDER BY created_at DESC`. Ordering is consistent within the single-process loop. |

### CS Foundations -- Scale & Performance

| Rule | Status | Evidence |
|------|--------|----------|
| SCALE-1 | **YES** | Designed for 1-50 agents, one daemon per agent. Each daemon is a separate OS process with its own subprocess for the AI provider. Appropriate for scale. |
| SCALE-2 | **YES** | Hot path: `_poll_inbox()` runs `minion poll --interval 5 --timeout 30` as subprocess every cycle. Each poll is a subprocess launch + SQLite query. At 50 agents, that's 50 subprocesses polling every ~35s. Acceptable for local-first tool. |
| SCALE-3 | **N/A** | No caching in daemon. Each poll/DB operation is fresh. At this scale, caching would add complexity without benefit. |
| SCALE-4 | **NO** | No Big-O documentation. Key operations: `_poll_inbox()` O(1) per agent, `_check_available_work()` O(tasks), `pop_next_message()` O(messages). All bounded by SQLite query performance. Not documented. |
| SCALE-5 | **NO** | Resource bounds not enforced: (1) `buffer.py` RollingBuffer has `max_tokens` limit (good), (2) stream log (`<agent>.stream.jsonl`) grows unbounded — no rotation, (3) state JSON file is small and overwritten (OK), (4) DB connections are short-lived (OK), (5) subprocess stdout is consumed line-by-line (OK). **Main risk:** stream log files grow indefinitely for long-running daemons. |

### CS Foundations -- Error & Failure Modes

| Rule | Status | Evidence |
|------|--------|----------|
| ERR-1 | **NO** | No formal failure taxonomy. Failures are classified implicitly: transient (DB writes, HP updates), fatal (minion binary not found), context-death (phoenix_down), external (signal). Not documented as a taxonomy. |
| ERR-2 | **YES** | Retry strategy: (1) poll loop retries implicitly every cycle, (2) execution failures use exponential backoff (`retry_backoff_sec * 2^(failures-1)`, capped at `retry_backoff_max_sec`), (3) resume fallback (try resume, fall back to fresh session). Backoff is configurable per-agent. |
| ERR-3 | **YES** | Partial failure handled well: DB write failures don't crash the daemon, HP update failures don't crash the daemon, alert send failures don't crash the daemon. Each non-critical operation is independently protected. The daemon continues polling even when instrumentation fails. |
| ERR-4 | **YES** | Mixed by design: daemon uses graceful degradation (broad except, log, continue) for non-critical ops. Fatal conditions (binary not found, signal, stand_down) cause clean exit. Phoenix_down triggers auto-respawn. This is intentional and documented in code comments. |
| ERR-5 | **NO** | Structured JSON logs to stdout (good). But: (1) only INFO level — no DEBUG/WARN/ERROR levels, (2) 3 output paths (structured JSON via `_log()`, raw `print()` to stderr for alerts, `print()` to stdout for dots/stream), (3) no log rotation for stream.jsonl, (4) no metrics/counters beyond what's in SQLite. SF-02 (systemic logging finding) applies here. |

### Clean Architecture (subset)

| Rule | Status | Evidence |
|------|--------|----------|
| CA-DEP-1 | **YES** | daemon/ imports inward: `minion.providers`, `minion.defaults`, `minion.prompts`, `minion.auth`, `minion.db`. No outward dependencies (daemon is not imported by business logic). CLI imports daemon only at spawn time. |
| CA-SOLID-1 | **YES** | Each mixin has one responsibility: stream parsing, HP tracking, state I/O, DB ops, prompt building, polling, execution, alerting, watcher mode. 9 mixins for 9 concerns. |
| CA-SOLID-4 | **YES** | No transitive dependencies on unused modules. Each mixin imports only what it uses. `TYPE_CHECKING` blocks used for type hints to avoid runtime imports. |

### Pragmatic Programmer (subset)

| Rule | Status | Evidence |
|------|--------|----------|
| PP-CRAFT-1 | **YES** | Mixin interactions are intentional — each mixin declares its cross-mixin dependencies as typed stubs at the bottom of the file. The composition root (`runner/__init__.py`) documents which mixin serves which concern. Code is deliberate, not coincidental. |
| PP-DECOUPLE-1 | **YES** | No train wrecks. Method calls are direct: `self._log()`, `self._write_state()`. No chained `.get().get()` patterns in daemon code. |
| PP-DECOUPLE-4 | **YES** | Mixins ARE the delegation pattern recommended by Tip 51. No deep inheritance hierarchy. The flat mixin composition gives each concern a separate file while sharing `self` state. This is the Python-idiomatic alternative to interface-based delegation. |
| PP-ORTH-1 | **PARTIAL** | Mixins are self-contained by concern but not independent — ExecutionMixin depends on 5 other mixins. However, each mixin can be read and understood in isolation (the stubs document the interface). Changes to one mixin's internals don't ripple if the stub interface is preserved. |
| PP-ORTH-3 | **YES** | Changes within a mixin don't ripple to others as long as the stub interface (method signatures) is preserved. For example, changing HP calculation logic in `_hp.py` doesn't affect `_execution.py` which just calls `self._update_hp()`. |
| PP-CONTRACT-1 | **NO** | No formal preconditions/postconditions. `daemon/contracts.py` is just a JSON file loader for shared contract docs — not Design by Contract. The closest is the `agent_name not in config.agents` check in `__init__`. |
| PP-CONTRACT-2 | **YES** | Crashes early on fatal: `FileNotFoundError` for config, `KeyError` for unknown agent, `_stop_event.set()` when minion binary not found. Continues gracefully on transient: DB writes, HP updates. Appropriate split. |

### Implementation Coding Core (subset)

| Rule | Status | Evidence |
|------|--------|----------|
| IC-HDR-1 | **NO** | No formal PURPOSE headers. Module docstrings serve as informal equivalents (e.g., `"""DB operations -- invocation log, child PID tracking, session ID, compaction log."""`). SF-01 systemic finding applies. |
| IC-HDR-2 | **NO** | No formal RESPONSIBILITIES headers. Mixin class docstrings serve as informal equivalents. SF-01 applies. |
| IC-HDR-3 | **NO** | No formal NOT RESPONSIBLE FOR headers. SF-01 applies. |
| IC-HDR-4 | **NO** | No formal DEPENDENCIES headers. The `# Defined in other mixins` stubs serve a similar purpose but are not in mandated format. SF-01 applies. |
| IC-HDR-5 | **YES** | Docstrings are preserved — no evidence of removal. The mixin stub declarations at the bottom of each file are persistent interface documentation. |
| IC-SCALE-1 | **NO** | No "what happens at 10x/100x/1000x" analysis. At 100 agents: 100 daemon processes, each spawning subprocesses for minion CLI calls (poll, send, check-work, update-hp). That's potentially 400+ subprocess.run() calls per cycle across all daemons. SQLite contention with 100 concurrent writers could become an issue despite WAL mode. Not documented. |
| IC-SCALE-2 | **PARTIAL** | Timeouts present on most external calls: `subprocess.run(..., timeout=10)` for alert, HP, check-work. `subprocess.run()` in `_poll_inbox` has NO explicit timeout (the minion poll command has `--timeout 30` internally, but the subprocess itself has no Python-level timeout). `_run_command()` has `no_output_timeout_sec` (configurable, default 600s). SQLite connections have `timeout=5` (good). The `_poll_inbox` missing Python-level timeout is a gap — if `minion poll` hangs, the daemon hangs. |
| IC-SCALE-3 | **YES** | `RollingBuffer` in `buffer.py` bounds memory via `max_tokens * 4` chars. Subprocess stdout is consumed line-by-line. Stream log writes are line-by-line. No unbounded reads in daemon code. The stream.jsonl file grows unbounded on disk (SCALE-5 issue), but reads are bounded. |
| IC-SCALE-4 | **NO** | Assumptions not formally documented. Key undocumented assumptions: (1) one daemon per agent, (2) subprocess poll returns within 30s, (3) SQLite busy_timeout of 5s is sufficient, (4) RollingBuffer's max_tokens * 4 char approximation is close enough, (5) HP percentage based on turn_input vs context_window is accurate enough. |

---

## Findings

| # | Rule | Severity | Affected Files | Description | Remediation |
|---|------|----------|----------------|-------------|-------------|
| F-01 | CS-ERR-5, PP-APPROACH-3 | **Moderate** | All daemon files | Three output paths: structured JSON `_log()`, raw `print()` to stderr for alerts, `print()` to stdout for dots/stream markers. No log levels. Ref SF-02. | Unify under structured JSON logger with levels. Route stderr alerts through same logger. |
| F-02 | CS-SCALE-5 | **Moderate** | `_execution.py` | Stream log file (`<agent>.stream.jsonl`) grows unbounded. For a daemon running weeks, this could consume significant disk. | Add log rotation or max-size truncation for stream.jsonl. |
| F-03 | CS-ERR-1 | **Minor** | Implicit across daemon | No formal failure taxonomy document. Fatal, transient, and context-death categories exist in code but not documented. | Document failure categories and their handling strategy in a comment header or contract file. |
| F-04 | IC-SCALE-2 | **Moderate** | `_polling.py:39` | `subprocess.run()` for `_poll_inbox()` has no Python-level `timeout` parameter. If `minion poll` process hangs (e.g., stuck on DB lock beyond internal timeout), the daemon blocks indefinitely. | Add `timeout=60` (or 2x the internal `--timeout 30`) to the `subprocess.run()` call in `_poll_inbox()`. |
| F-05 | CS-CONSIST-2 | **Minor** | `_db.py:192-213` | `_fetch_fenix_records()` does a read-then-update without `with conn:` transaction wrapper. Uses manual `conn.commit()` which is functionally correct but inconsistent with the `with conn:` pattern used in `watcher.py`. | Wrap in `with conn:` for consistency. Low risk since only one daemon writes per agent. |
| F-06 | PP-CONTRACT-1 | **Minor** | `daemon/contracts.py` | File name is misleading — `contracts.py` suggests Design by Contract but is actually a JSON file loader for shared config. No actual preconditions/postconditions anywhere in daemon. | Rename to `contract_loader.py` or add actual contract validation (preconditions on `__init__`, postconditions on state transitions). |
| F-07 | IC-HDR-1 through IC-HDR-4 | **Major** (systemic) | All 18 daemon files | No formal PURPOSE/RESPONSIBILITIES/NOT RESPONSIBLE/DEPENDENCIES headers. Module docstrings serve as informal equivalents. Ref SF-01. | Mechanical fix — add headers to all files. Low complexity per file. |
| F-08 | PP-DRY-1 | **Moderate** | `daemon/config.py`, `crew/config.py` | `load_config()` parsing logic is duplicated between the two files (~100 lines each, nearly identical). Dataclass sharing is resolved (good), but the parsing function is still duplicated. Ref SF-08. | Extract shared parsing into a `_parse_crew_yaml()` function in `crew/config.py`, call from both. |
| F-09 | IC-SCALE-4 | **Minor** | `_hp.py:156`, `_constants.py:67-95` | Key assumptions undocumented: `len(boot_prompt) // 4` as token estimate, `CLAUDE_CODE_SYSTEM_TOKENS = 3500` as approximate, `max_tokens * 4` as char-to-token ratio. These approximations are reasonable but should have `# ASSUMPTION:` comments. | Add ASSUMPTION comments with rationale and what-breaks-if-wrong. |
| F-10 | — (Bug) | **High** | `_db.py:180` | `_has_pending_halt()` queries `WHERE read = 0` but the schema defines the column as `read_flag`. This query will fail with `sqlite3.OperationalError: no such column: read`. The broad `except Exception: pass` on line 188 silently swallows this error, meaning **halt detection during phoenix_down never works**. | Change `read = 0` to `read_flag = 0` on line 180. |
| F-11 | CS-ERR-4 | **Minor** | `_db.py:127`, `_db.py:188`, `_state.py:84` | Three `except Exception: pass` blocks with no logging. While the fail-open behavior is correct, completely silent exception handling hides potential issues (e.g., F-10 would have been caught immediately with a log). | Add `self._log(f"WARNING: ...")` to all three silent except blocks. |

---

## Strengths

1. **Well-decomposed mixin architecture** — 9 mixins with clear single-concern separation. Each file is readable in isolation. The `# Defined in other mixins` stubs serve as informal interface contracts.

2. **Correct concurrency model** — Single-threaded business logic with subprocess-based execution avoids the need for locks. The `queue.Queue` for stdout reading is the right choice. No over-engineering of thread safety.

3. **Robust resilience pattern** — 13 of 16 broad except blocks are intentional, logged, and correctly classified as non-critical. The daemon continues operating when instrumentation fails. Fatal conditions correctly trigger exit.

4. **Auto-respawn on context death** — The `phoenix_down` / generation loop is a sophisticated lifecycle feature. The daemon detects context exhaustion via HP tracking and respawns with a fresh session while preserving task state.

5. **Structured JSON logging** — `_log()` outputs machine-parseable JSON with timestamp, agent name, level, and message. This is the right foundation for a daemon.

6. **Exponential backoff with cap** — Failure handling uses `retry_backoff_sec * 2^(failures-1)` capped at `retry_backoff_max_sec`, both configurable per-agent. Alerts lead after 3 consecutive failures.

7. **RollingBuffer bounds memory** — `buffer.py` is a clean, bounded data structure with `deque`-based eviction. Prevents unbounded memory growth from agent output.

8. **Config DRY resolved** — `AgentConfig` and `SwarmConfig` dataclasses are defined once in `crew/config.py` and imported by `daemon/config.py`. The AU-00 finding SF-08 for dataclass duplication has been addressed.

9. **Provider abstraction** — Execution delegates to `BaseProvider` for command building, resume support, and log filtering. Adding a new provider doesn't require daemon changes.

10. **Standdown/wake lifecycle** — Sophisticated idle management: agent stands down when no work is available, wakes on new work, decides resume vs fresh session based on task continuity. Self-dismiss mode drops AI session to save resources.

---

## Boundary Checks

### B-05: Daemon <-> Crew Lifecycle

The daemon defines its own lifecycle states (idle, working, error, phoenix_down, stood_down, self_dismissed, stopped, halted) written to JSON state files. These are independent from the crew/lifecycle.py agent lifecycle (which manages registration, spawn, stand-down at the management level).

**Assessment:** The two lifecycle models operate at different levels — crew lifecycle is management-level (register, spawn, retire), daemon lifecycle is process-level (idle, working, error). They don't conflict because they track different things. The bridge point is `stand_down` (poll exit code 3) which triggers daemon exit, matching crew's stand-down command.

### B-07: Daemon Config <-> Crew Config

**Dataclass sharing: RESOLVED** — `AgentConfig` and `SwarmConfig` imported from `crew/config.py`.

**Parsing duplication: REMAINING** — `daemon/config.py:load_config()` and `crew/config.py:load_config()` are ~100 lines each of near-identical YAML parsing logic. Key differences: daemon skips `skills` and `scope` fields. This should be a shared function. Ref SF-08, finding F-08.

---

## Summary Statistics

- **Rules evaluated:** 30
- **YES:** 17
- **NO:** 9
- **PARTIAL:** 2
- **N/A:** 1
- **Findings:** 11 (1 High, 1 Major-systemic, 4 Moderate, 5 Minor)
- **Strengths:** 10

**Critical finding:** F-10 (High) — `_has_pending_halt()` queries a non-existent column `read` instead of `read_flag`, and the error is silently swallowed by `except Exception: pass`. This means halt detection during phoenix_down auto-respawn is completely broken.
