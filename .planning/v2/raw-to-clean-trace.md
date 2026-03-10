# Raw-to-Clean Traceability — v2

Every raw input mapped to its clean requirement section or marked out-of-scope.

## Raw Input 1: System Identity → Context only (not a requirement)
Used to frame v2 as remediation of existing system.

## Raw Input 2: v1 Upstream Feedback
| UF | Status | Clean Req |
|----|--------|-----------|
| UF-001 (not FastAPI) | Methodology | N/A for v2 |
| UF-002 (skill mapping) | Methodology | N/A for v2 |
| UF-003 (halt detection) | FIXED v1 | N/A |
| UF-004 (network security) | FIXED v1 | N/A |
| UF-005 (systemic findings) | PARTIAL | §2.1, §2.4, §3.1, §3.2 |
| UF-006 (DAG methodology) | Methodology | N/A for v2 |
| UF-007 (additive remediation) | Design guidance | Frames all of v2 |

## Raw Input 3: Remaining Backlog (73 items)

### Bugs (10) → §1 Correctness
| # | Backlog Item | Clean Req |
|---|-------------|-----------|
| 1 | DAG self-review bypass | §1.1 |
| 2 | Global comms delivery failure | §1.2 |
| 3 | Poll path resolution | §1.3 |
| 4 | Global agent heartbeat | §1.4 |
| 5 | Stale terminal status | §1.5 |
| 6 | Terminal agent poll determinism | §1.6 |
| 7 | Test promote crew display | §1.10 |
| 8 | Backlog lineage linkage | §1.7 |
| 9 | Backlog promote null | §1.8 |
| 10 | Backlog auth cross-project | §1.9 |

### Debt (22) → §2 Reliability + §3 Tests
| # | Backlog Item | Clean Req |
|---|-------------|-----------|
| 1 | Daemon/crew logs unstructured | §2.1 (bare excepts encompass) |
| 2 | No assumption docs | §2.6 |
| 3 | No data lifecycle | §2.2 |
| 4 | Zero contracts/assertions | §2.4 |
| 5 | 103 bare excepts | §2.1 |
| 6 | No Big-O docs | §2.7 |
| 7 | No message type taxonomy | §2.8 |
| 8 | No conftest.py | §3.1 |
| 9 | Unbounded stream.jsonl | §2.3 |
| 10 | No pytest markers | §3.1 |
| 11 | No formal state machines | §2.5 |
| 12 | Zero mission tests | §3.2 |
| 13 | No pattern registry | §2.9 |
| 14 | No API CLI exerciser | §3.2 |
| 15 | No CLI ref-integrity tests | §3.2 |
| 16 | UI wrong DB path | §4.5 |
| 17-22 | Residuals | Covered by parent items |

### Ideas (14) → §5 Features
| # | Backlog Item | Clean Req |
|---|-------------|-----------|
| 1 | Context refresh | §5.3 |
| 2 | Auth scope narrowing | §5.4 |
| 3 | DAG enforcement | §5.4 |
| 4 | Dashboard views | §5.5 |
| 5 | Fuzzy matching | §5.3 |
| 6 | Cycle detection | §5.4 |
| 7 | Shell completions | §5.3 |
| 8 | Error remediation hints | §5.3 |
| 9 | On-demand spawning | §5.1 |
| 10 | Coordinator class | §5.2 |
| 11 | Leads report to sys-lead | §5.2 |
| 12 | Dashboard scope | §5.5 |
| 13 | Cold-start auto-gen | §5.3 |
| 14 | Sys-lead crew YAML | §5.2 |

### Requests (7) → §5 Features
| # | Backlog Item | Clean Req |
|---|-------------|-----------|
| 1 | CLI parity | §5.1 |
| 2 | Cross-project lead | §5.2 |
| 3 | Agent presence API | §5.1 |
| 4 | Agent registry schema | §5.1 |
| 5 | Composite agent key | §5.1 |
| 6 | Sys-lead review gaps | §5.1 |
| 7 | Prompt assembly research | §5.3 |

### Smells (20) → §4 Code Hygiene
All 20 smell items mapped to §4.1-§4.5 subsections. See clean-unbiased.md for details.

## Coverage Check
- All 73 backlog items traced ✓
- All 7 upstream feedback items addressed ✓
- No silent omissions ✓
