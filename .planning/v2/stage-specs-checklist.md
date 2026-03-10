# Stage 6 Checklist — Specifications

## Pre-conditions
- [x] Decomposition approved (Stage 4)
- [x] Spec tree created (Stage 5)
- [x] Research files read
- [x] Source code surveyed for current state

## Spec Writing (22 specs)

### Wave 0: Foundation
- [x] SU-01: Pattern registry conventions and enforcement

### Wave 1: Verification
- [x] SU-02: Verify implemented requirements — 11 features

### Wave 2: Correctness Fixes
- [x] SU-03: DAG self-review bypass prevention
- [x] SU-04: Global comms cross-project edge cases
- [x] SU-05: Stale status terminal classification
- [x] SU-06: Terminal agent poll determinism hardening
- [x] SU-07: Backlog lineage and auth hardening

### Wave 3: Reliability and Quality
- [x] SU-08: Bare exception narrowing
- [x] SU-09: Contract and assertion expansion
- [x] SU-10: Documentation debt — assumptions and Big-O

### Wave 4: Test Infrastructure
- [x] SU-11: Test markers, fixtures, and conftest completion
- [x] SU-12: Missing test suites and verification artifact strategy

### Wave 5: Code Hygiene
- [x] SU-13: Dependency layer violation fixes
- [x] SU-14: Code deduplication
- [x] SU-15: CLI consistency
- [x] SU-16: Configuration consistency
- [x] SU-17: Dead code and unreachable paths

### Wave 6: Features and Agent Experience
- [x] SU-18: Network API CLI parity
- [x] SU-19: Cross-project coordination
- [x] SU-20: Agent experience improvements
- [x] SU-21: DAG scaffolding enforcement
- [x] SU-22: Dashboard UI consolidation

## Post-spec Deliverables
- [x] Test contracts extracted to test-contracts.md
- [x] Cross-spec contract reconciliation against boundary-dependency-map.md
- [ ] Full spec content presented to sys-lead
