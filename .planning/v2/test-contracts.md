# Test Contracts — v2

Extracted from all 22 spec units. Each contract defines the minimum verification needed to confirm the spec is satisfied.

---

## Wave 0: Foundation

### SU-01: Pattern Registry
| ID | Test | Type |
|----|------|------|
| T-01-1 | `.work/pattern-registry.md` exists | artifact |
| T-01-2 | All 9 sections present with code examples | artifact |
| T-01-3 | Each section references at least one existing source file | artifact |

---

## Wave 1: Verification

### SU-02: Verify 11 Implemented Features
| ID | Test | Type |
|----|------|------|
| T-02-1 | Poll walk-up: resolve_db_path() finds DB from subdirectory | unit |
| T-02-2 | Poll walk-up: returns None when no DB in ancestor chain | unit |
| T-02-3 | Heartbeat: touch_coordinator_activity creates/updates agent entry | integration |
| T-02-4 | Promote: promoted_to is never None/empty | unit |
| T-02-5 | Pruning: old records (>30d) deleted, recent records survive | integration |
| T-02-6 | Log rotation: oversized file triggers rotation | integration |
| T-02-7 | State machines: valid transition succeeds, invalid raises | unit |
| T-02-8 | State machines: all states reachable | unit |
| T-02-9 | Message types: valid msg_type succeeds, invalid rejected | unit |
| T-02-10 | Error hints: known error pattern gets remediation hint | unit |
| T-02-11 | Fuzzy match: misspelled command suggests correct one | integration |
| T-02-12 | Auth scope: sys scope passes for authorized, blocks unauthorized | unit |
| T-02-13 | Cycle detection: cyclic flow raises error, acyclic loads | unit |

---

## Wave 2: Correctness Fixes

### SU-03: DAG Self-Review Bypass
| ID | Test | Type |
|----|------|------|
| T-03-1 | Implementer tries to complete QE — BLOCKED | integration |
| T-03-2 | Different agent completes QE — success | integration |
| T-03-3 | No transition_log entry — success with warning | integration |
| T-03-4 | Lead self-reviews — success (bypass) | integration |
| T-03-5 | Re-implemented task — original implementer can review | integration |

### SU-04: Global Comms Edge Cases
| ID | Test | Type |
|----|------|------|
| T-04-1 | Valid cross-project delivery returns success dict | integration |
| T-04-2 | Agent not in coordinator returns None | integration |
| T-04-3 | Missing target project path returns error dict | integration |
| T-04-4 | Locked target DB returns error dict | integration |
| T-04-5 | Old-schema target table — graceful degradation | integration |

### SU-05: Stale Terminal Classification
| ID | Test | Type |
|----|------|------|
| T-05-1 | "stale" in TERMINAL_STATUSES | unit |
| T-05-2 | Parent with [closed, stale] children — rollup triggers | integration |
| T-05-3 | Parent with [stale, in_progress] — rollup does NOT trigger | integration |
| T-05-4 | All stale children — parent becomes stale | integration |
| T-05-5 | is_terminal("stale") returns True | unit |

### SU-06: Poll Determinism Hardening
| ID | Test | Type |
|----|------|------|
| T-06-1 | install-hooks is idempotent | integration |
| T-06-2 | poll-on-stop.sh with MINION_AGENT_NAME unset — fail-open | integration |
| T-06-3 | poll-on-stop.sh with messages in inbox — blocks stop | integration |
| T-06-4 | poll-on-stop.sh with CLI not in PATH — fail-open | integration |
| T-06-5 | complete_phase result includes poll_reminder | unit |

### SU-07: Backlog Lineage and Auth
| ID | Test | Type |
|----|------|------|
| T-07-1 | Promote returns requirement_id (positive int) | integration |
| T-07-2 | Task created from promoted item has requirement_id | integration |
| T-07-3 | backlog add via -C with non-lead — BLOCKED | integration |
| T-07-4 | backlog add via -C with lead — success | integration |
| T-07-5 | Promote output includes required_crew and available_characters | integration |
| T-07-6 | Local backlog add without agent — success | integration |

---

## Wave 3: Reliability

### SU-08: Bare Exception Narrowing
| ID | Test | Type |
|----|------|------|
| T-08-1 | grep "except Exception" src/minion/ returns 0 (or documented exceptions) | audit |
| T-08-2 | All existing tests pass | regression |
| T-08-3 | Unexpected exception in priority module propagates | integration |
| T-08-4 | Daemon loop broad catch — logged and continues | integration |

### SU-09: Assertion Expansion
| ID | Test | Type |
|----|------|------|
| T-09-1 | Tier 1 function with empty param raises AssertionError | unit |
| T-09-2 | Tier 2 function with invalid class raises AssertionError | unit |
| T-09-3 | All existing tests still pass | regression |
| T-09-4 | Total assertion count >= 80 | audit |

### SU-10: Documentation Debt
| ID | Test | Type |
|----|------|------|
| T-10-1 | Magic number literals have ASSUMPTION comments | audit |
| T-10-2 | Hot-path functions have Big-O in docstrings | audit |
| T-10-3 | Annotations are factually correct | review |

---

## Wave 4: Test Infrastructure

### SU-11: Markers and Fixtures
| ID | Test | Type |
|----|------|------|
| T-11-1 | `pytest --co -m unit` returns >0 tests | smoke |
| T-11-2 | `pytest --co -m integration` returns >0 tests | smoke |
| T-11-3 | No unknown marker warnings | smoke |
| T-11-4 | No test file creates DB connection directly | audit |

### SU-12: Missing Tests and Verification Strategy
| ID | Test | Type |
|----|------|------|
| T-12-1 | Coverage analysis document exists | artifact |
| T-12-2 | Previously uncovered modules have test files | audit |
| T-12-3 | verification-strategy.md exists | artifact |
| T-12-4 | New tests pass with proper markers | regression |

---

## Wave 5: Code Hygiene

### SU-13: Dependency Violations
| ID | Test | Type |
|----|------|------|
| T-13-1 | No auth imports in db/ | audit |
| T-13-2 | No direct _tmux imports in tasks/ | audit |
| T-13-3 | No circular imports between comms and crew | integration |
| T-13-4 | All existing tests pass | regression |

### SU-14: Code Deduplication
| ID | Test | Type |
|----|------|------|
| T-14-1 | _append_error_log exists only in shared module | audit |
| T-14-2 | Role prompts use shared self-service block | audit |
| T-14-3 | Provider error classifier is shared | audit |
| T-14-4 | All existing tests pass | regression |
| T-14-5 | New shared modules have test files | audit |

### SU-15: CLI Consistency
| ID | Test | Type |
|----|------|------|
| T-15-1 | Moved commands work in new location | integration |
| T-15-2 | Backward-compat aliases work with deprecation warning | integration |
| T-15-3 | Short flags work for high-frequency options | integration |
| T-15-4 | Exit codes follow 0/1/2 convention | audit |

### SU-16: Configuration Consistency
| ID | Test | Type |
|----|------|------|
| T-16-1 | -C flag help mentions MINION_PROJECT_DIR | audit |
| T-16-2 | os.environ usage only in defaults.py + exceptions | audit |
| T-16-3 | sqlite3.connect only in db/connection.py | audit |
| T-16-4 | All tests pass | regression |

### SU-17: Dead Code Cleanup
| ID | Test | Type |
|----|------|------|
| T-17-1 | Scaling endpoints: wired or removed (documented) | audit |
| T-17-2 | HTTP request produces log entry | integration |
| T-17-3 | Closed DB connection gives clear error | unit |
| T-17-4 | Intel auto-link catches only IntegrityError | unit |
| T-17-5 | No generic file names (utils.py etc.) | audit |

---

## Wave 6: Features

### SU-18: Network API Parity
| ID | Test | Type |
|----|------|------|
| T-18-1 | Each new endpoint returns 200 with correct JSON | integration |
| T-18-2 | GET /who?class=coder filters correctly | integration |
| T-18-3 | GET /tasks/{id}/lineage returns history | integration |
| T-18-4 | GET /db/stats returns DB metrics | integration |
| T-18-5 | All new routes registered | audit |

### SU-19: Cross-Project Coordination
| ID | Test | Type |
|----|------|------|
| T-19-1 | multi_project_poll returns aggregated results | integration |
| T-19-2 | coordinator class registers successfully | integration |
| T-19-3 | Coordinator bypasses -C auth for backlog | integration |
| T-19-4 | Invalid project path skipped gracefully | integration |
| T-19-5 | Global sitrep sends to sys-lead | integration |

### SU-20: Agent Experience
| ID | Test | Type |
|----|------|------|
| T-20-1 | refresh returns expected keys | integration |
| T-20-2 | cold-start returns live team composition | integration |
| T-20-3 | Bash completion script outputs | smoke |
| T-20-4 | completions install is idempotent | integration |
| T-20-5 | research-prompt-strategy.md exists | artifact |

### SU-21: DAG Scaffolding Gate
| ID | Test | Type |
|----|------|------|
| T-21-1 | Missing files — scaffolding phase BLOCKED | integration |
| T-21-2 | All files present — scaffolding phase succeeds | integration |
| T-21-3 | Empty files field — succeeds with warning | integration |
| T-21-4 | Non-scaffolding stage — no gate fires | integration |
| T-21-5 | Lead bypass works | integration |

### SU-22: Dashboard
| ID | Test | Type |
|----|------|------|
| T-22-1 | GET /dashboard/ returns 200 with HTML | integration |
| T-22-2 | GET /dashboard/agents shows registered agents | integration |
| T-22-3 | GET /dashboard/tasks shows pipeline | integration |
| T-22-4 | GET /dashboard/health shows DB stats | integration |
| T-22-5 | Empty state renders valid HTML | integration |

---

## Summary

| Category | Count |
|----------|-------|
| Unit tests | 25 |
| Integration tests | 58 |
| Audit checks | 23 |
| Artifact verifications | 6 |
| Smoke tests | 4 |
| Regression checks | 7 |
| Review checks | 1 |
| **Total test contracts** | **124** |
