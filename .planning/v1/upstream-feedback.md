# Upstream Feedback — v1

## Stage 3 (Research) Findings

### UF-001: Network API is not FastAPI (Clean Requirements Impact)
- **Layer wrong:** Clean requirements §2.1 assumed FastAPI
- **What happened:** Research discovered src/minion/network/ uses stdlib http.server
- **Impact:** fast-api skill (24 rules) is mostly N/A for current-state audit. ai-first-api partially applicable.
- **Resolution:** Audit fast-api as aspirational (migration path), not compliance. Note in decomposition.

### UF-002: Skill applicability varies by domain more than expected
- **Layer wrong:** Clean requirements §3 mapped primary skills per domain but research shows some mappings need adjustment
- **Impact:** D7 (Network API) should drop fast-api as primary, use ai-first-api + cs-foundations only. D10 (Prompts) is mostly .md files — implementation-coding-core headers don't apply to markdown.
- **Resolution:** Refine domain-to-skill mapping at decomposition stage.

## Stage 8 (Audit Execution) Findings

### UF-003: Real bug discovered — halt detection silently broken
- **Source:** AU-05 (Daemon Runtime), F-004-C
- **What happened:** `_has_pending_halt()` queries `WHERE read = 0` but schema column is `read_flag`. `except Exception: pass` swallows the OperationalError. Halt detection during phoenix_down auto-respawn never works.
- **Impact:** Critical correctness bug. Daemon will always respawn even when HALT message is pending.
- **Resolution:** Backlog item #44 (P0). Fix column name, add logging to except block, add test.

### UF-004: Security surface larger than expected on network API
- **Source:** AU-06 (Network API), F-003-C/F-005-C/F-007/F-011
- **What happened:** No Content-Length limit (DoS), no input validation on /register (25+ unvalidated fields), timing-unsafe token comparison, AuthMixin dead code.
- **Impact:** 4 findings at critical/major severity on the untrusted network boundary. Existing auth design is good but implementation has gaps.
- **Resolution:** Backlog items #45-48, #55 (P0/P1). Body limit, input validation, timing-safe compare, wire AuthMixin.

### UF-005: Systemic findings dominate — 12 affect entire codebase
- **Source:** Cross-domain reconciliation (Stage 8b)
- **What happened:** 12 of 62 findings are systemic (affect all domains): logging (3 patterns), error handling (2 patterns), no headers (181 files), no tests (17 packages), config scatter, no assertions, bare excepts.
- **Impact:** These 12 systemic findings generate the majority of per-domain FAIL results. Fixing them has outsized ROI.
- **Resolution:** P1 backlog items #49-60. Recommended execution: logging strategy first, then error convention, then headers incrementally.

### UF-006: DAG audit methodology gap — no "audit execution" stage
- **Source:** Methodology observation
- **What happened:** The canonical DAG has Stage 8 = implement and Stage 9 = verify. For a retrospective audit, we repurposed Stage 8 as "audit execution" and Stage 9 as "backlog ingestion." This worked but required interpretation.
- **Impact:** Running the DAG on an existing codebase is a valid use case but the DAG doesn't formally support it.
- **Resolution:** Record as methodology finding for iterative-decomposition-dag repo. Consider adding an "audit" variant to DAG.md.

### UF-007: Strengths are architectural — weaknesses are gaps and inconsistencies
- **Source:** STRENGTHS-REPORT.md
- **What happened:** The codebase has a clean dependency graph, good db design, agent-first CLI, solid task state machine, proper provider abstraction. Weaknesses are missing conventions (logging, errors, headers) and missing coverage (tests, validation), not structural flaws.
- **Impact:** Remediation is additive (fill gaps) not structural (rewrite). The foundation is solid.
- **Resolution:** Preserve strengths report as reference. Remediation should add conventions and coverage, not restructure.
