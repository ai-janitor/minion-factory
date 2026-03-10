# Cross-Spec Contract Reconciliation — v2 Stage 6

Reconciliation of all 12 boundary edges from boundary-dependency-map.md against the written specs. For each edge, verify the contract is honored by both sides.

---

## E-01: SU-01 (pattern registry) -> SU-08 (bare exception narrowing)
- **Contract type:** convention
- **SU-01 spec says:** Error Handling section defines when to raise typed exceptions vs return error dicts. Specific exception types per module category.
- **SU-08 spec says:** "Follow pattern registry convention for error handling." Per-block decision table references pattern registry.
- **Status:** [reconciled] — SU-08 explicitly defers to SU-01's error handling section. Contract artifact is `.work/pattern-registry.md` "Error Handling" section.

## E-02: SU-01 (pattern registry) -> SU-09 (assertion expansion)
- **Contract type:** convention
- **SU-01 spec says:** "Contracts and Assertions" section defines what/where to assert, exception types.
- **SU-09 spec says:** "Follow pattern registry convention for assertion style and exception types." Tier-based coverage plan.
- **Status:** [reconciled] — SU-09 explicitly defers to SU-01. Contract artifact is `.work/pattern-registry.md` "Contracts and Assertions" section.

## E-03: SU-01 (pattern registry) -> SU-10 (documentation debt)
- **Contract type:** convention
- **SU-01 spec says:** "Documentation Conventions" section defines ASSUMPTION format, Big-O format, magic number policy.
- **SU-10 spec says:** "Follow pattern registry convention for annotation format." Specific format strings defined.
- **Status:** [reconciled] — SU-10 defines the specific format strings which SU-01 must document. SU-10's format is the proposal; SU-01 makes it canonical.

## E-04: SU-01 (pattern registry) -> SU-14 (code deduplication)
- **Contract type:** convention
- **SU-01 spec says:** Sections on DB Access, Provider Error Classification, Logging define canonical patterns.
- **SU-14 spec says:** "Following pattern registry's canonical patterns." Extracts shared code to match canonical patterns.
- **Status:** [reconciled] — SU-14 deduplicates TOWARD the patterns SU-01 defines. If SU-01 doesn't define a pattern for a duplication cluster, SU-14 proposes one and SU-01 should be updated.

## E-05: SU-04 (global comms) -> SU-19 (cross-project coordination)
- **Contract type:** data-shape
- **SU-04 spec says:** Return type updated — success returns dict with keys (timestamp, status, from, to, routed_via, target_project), failure returns error dict, not found returns None. CREATE TABLE IF NOT EXISTS preserves message schema.
- **SU-19 spec says:** "Cross-project coordination requires reliable cross-repo message delivery." Depends on route_cross_repo() returning success/error dicts.
- **Status:** [reconciled] — SU-04's updated return types (error dicts instead of None for failures) are compatible with SU-19's needs. SU-19 can distinguish "agent not found" (None) from "delivery failed" (error dict).

## E-06: SU-03 (DAG self-review) -> SU-21 (DAG scaffolding enforcement)
- **Contract type:** state-transition
- **SU-03 spec says:** New validation check in complete_phase() after line 167, before DAG transition. Returns error dict on self-review violation.
- **SU-21 spec says:** Scaffolding check added AFTER SU-03's self-review check. Both are additive AND.
- **Status:** [reconciled] — Both specs explicitly state checks are additive AND. SU-21 inserts after SU-03's check. Order: class eligibility -> self-review check (SU-03) -> scaffolding gate (SU-21) -> DAG transition.

## E-07: SU-11 (test infrastructure) -> SU-12 (missing tests)
- **Contract type:** naming
- **SU-11 spec says:** Defines markers: `unit`, `integration`, `smoke`. Registered in pyproject.toml.
- **SU-12 spec says:** "Use pytest markers from SU-11." New tests must use registered markers.
- **Status:** [reconciled] — SU-12 explicitly references SU-11's marker names. Contract artifact is `pyproject.toml` marker registration.

## E-08: SU-14 (deduplication) -> SU-13 (dependency fixes)
- **Contract type:** naming
- **SU-14 spec says:** Extracted modules: `src/minion/providers/_shared_error_log.py`, `src/minion/providers/_shared_error_classifier.py`, `src/minion/prompts/roles/_shared_self_service_block.py`.
- **SU-13 spec says:** "Coordinate with SU-14's extracted shared modules." Needs to know import paths for dependency direction verification.
- **Status:** [reconciled] — SU-14 explicitly names extracted module paths. SU-13 verifies import directions include these new modules. If SU-14 changes paths, SU-13 must be notified.

## E-09: SU-17 (dead code) -> SU-18 (network API)
- **Contract type:** naming
- **SU-17 spec says:** Decision criteria for scaling endpoints: "wire up or remove." Documents decision for SU-18.
- **SU-18 spec says:** "Based on SU-17's decision — if wired, verify; if removed, no work."
- **Status:** [reconciled] — SU-17 makes the decision, SU-18 acts on it. Contract artifact is the documented decision in SU-17's deliverable.

## E-10: SU-18 (network API) -> SU-22 (dashboard)
- **Contract type:** naming + data-shape
- **SU-18 spec says:** New endpoints with defined paths and JSON response shapes.
- **SU-22 spec says:** Dashboard views call API endpoints. Dashboard is read-only HTML rendering of API data.
- **Status:** [reconciled] — SU-22 consumes SU-18's endpoint paths and response shapes. Contract artifact is `routes.py` (paths) and handler return types (shapes).

## E-11 (soft): SU-05 (stale terminal) -> SU-02 (verify state machines)
- **Contract type:** state-transition
- **SU-05 spec says:** Adds "stale" to TERMINAL_STATUSES.
- **SU-02 spec says:** "After SU-05 completes, add test verifying stale is a valid terminal state." Soft dependency — SU-02 can run in parallel and update test later.
- **Status:** [reconciled] — Soft dependency handled. SU-02 writes initial test against current state, adds stale test after SU-05. No blocking conflict.

## E-12: SU-07 (backlog auth) -> SU-19 (coordinator class)
- **Contract type:** naming
- **SU-07 spec says:** Auth checks on backlog mutations via -C flag.
- **SU-19 spec says:** Coordinator class needs all lead permissions PLUS cross-project capabilities. Coordinator bypasses -C auth for backlog.
- **Status:** [reconciled] — SU-07 adds the auth gates, SU-19 adds the coordinator class which inherits lead permissions and gets the bypass. The two are compatible: SU-07's gate checks class, SU-19's coordinator class passes that check.

---

## Non-Edge Boundaries

### B-01: SU-05 internal — dag.py <-> rollup.py
- **SU-05 spec says:** rollup.py imports TERMINAL_STATUSES from dag.py. Adding "stale" propagates automatically.
- **Status:** [reconciled] — single source of truth import pattern already correct.

### B-02: SU-15 internal — CLI command names <-> help text
- **SU-15 spec says:** Renamed commands must update help text, CLAUDE.md, all hardcoded references.
- **Status:** [reconciled] — spec explicitly lists update requirements.

### B-03: SU-19 internal — auth.py <-> agent-classes.yaml
- **SU-19 spec says:** Coordinator class in both auth.py and agent-classes.yaml.
- **Status:** [reconciled] — spec explicitly states both locations.

---

## Summary

| Edge | Status |
|------|--------|
| E-01 | [reconciled] |
| E-02 | [reconciled] |
| E-03 | [reconciled] |
| E-04 | [reconciled] |
| E-05 | [reconciled] |
| E-06 | [reconciled] |
| E-07 | [reconciled] |
| E-08 | [reconciled] |
| E-09 | [reconciled] |
| E-10 | [reconciled] |
| E-11 | [reconciled] |
| E-12 | [reconciled] |
| B-01 | [reconciled] |
| B-02 | [reconciled] |
| B-03 | [reconciled] |

All 12 edges and 3 non-edge boundaries reconciled. No conflicts found.
