# Stage 4 Decompose — Execution Checklist

## Prerequisites
- [done] Read DAG.md stage 4 spec
- [done] Read clean-requirements.md (73 items, 5 work streams)
- [done] Read all 8 research files
- [done] Read upstream-feedback.md (UF-V2-001 through UF-V2-003)
- [done] Read dependency-analysis-cross-requirement.md

## Decomposition Tasks
- [done] Classify all 73 items: verify-only (11), partial (8), full (53), deferred (1) = 72 in scope
- [done] Identify natural boundaries — features that can be built/tested independently
- [done] Group by affected subsystem (CLI, DB, daemon, network, tests)
- [done] Define spec units — 22 units (SU-01 through SU-22), each with name, requirements, dependencies, rationale
- [done] Check granularity — each unit has clear scope, testable independently
- [done] Produce dependency ordering — 10 explicit dependency edges, parallelism mapped
- [done] Define waves — 7 waves (0-6) with gates between waves
- [done] Write decomposition.md with spec units, dependency graph, build order, rationale
- [done] Write boundary-dependency-map.md — 12 edges + 3 intra-unit boundaries, all with contract types
- [ ] Present to sys-lead for relay to user

## CS-Foundations Checklist (Stage 4 gate)
- [done] CS-SEP-1..5: separation concerns — documented in decomposition.md CS-SEP section
- [done] CS-DATA-1..6: data ownership, state model, storage — no schema changes, ownership per SU documented
- [done] CS-COMM-1..5: sync/async stays sync, JSON/dict serialization preserved
- [done] CS-CONSIST-1..5: WAL mode, single-writer SQLite, idempotency noted for SU-07
- [done] CS-SCALE-1..5: SU-10 addresses Big-O, no scaling changes needed
- [done] CS-SEC-1..5: SU-07 (backlog auth), SU-19 (coordinator class), SU-03 (self-review)
- [done] CS-ERR-1..5: SU-01 (pattern registry), SU-08 (exception narrowing), SU-04 (partial failure)
- [done] PP-ORTH-1, PP-ORTH-3: each SU self-contained, cross-unit ripple only at documented edges
- [done] PP-DRY-1: no requirement covered by multiple SUs, SU-14 dedicated to DRY fixes
- [done] CA-COMP-1: dependency graph is acyclic (verified)
- [done] CA-COMP-4, CA-COMP-5: SU-07 (backlog co-change), SU-05 (stale co-change), SU-13+SU-14 (sequenced)
