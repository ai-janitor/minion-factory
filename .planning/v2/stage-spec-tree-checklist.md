# Stage 5: Spec Tree — Checklist

Stage: spec-tree
Iteration: v2
Derived from: decomposition.md (22 spec units, 7 waves)

## Tasks

- [done] Create `.planning/v2/spec-tree/` directory with wave-based subdirectories
- [done] Create spec file for SU-01: pattern registry (wave 0)
- [done] Create spec file for SU-02: verify implemented requirements (wave 1)
- [done] Create spec file for SU-03: DAG self-review bypass prevention (wave 2)
- [done] Create spec file for SU-04: global comms cross-project edge cases (wave 2)
- [done] Create spec file for SU-05: stale status terminal classification (wave 2)
- [done] Create spec file for SU-06: terminal agent poll determinism (wave 2)
- [done] Create spec file for SU-07: backlog lineage and auth hardening (wave 2)
- [done] Create spec file for SU-08: bare exception narrowing (wave 3)
- [done] Create spec file for SU-09: contract and assertion expansion (wave 3)
- [done] Create spec file for SU-10: documentation debt assumptions and big-o (wave 3)
- [done] Create spec file for SU-11: test infrastructure completion (wave 4)
- [done] Create spec file for SU-12: missing test suites and verification artifacts (wave 4)
- [done] Create spec file for SU-13: dependency layer violation fixes (wave 5)
- [done] Create spec file for SU-14: code deduplication (wave 5)
- [done] Create spec file for SU-15: CLI consistency (wave 5)
- [done] Create spec file for SU-16: configuration consistency (wave 5)
- [done] Create spec file for SU-17: dead code and unreachable path cleanup (wave 5)
- [done] Create spec file for SU-18: network API CLI parity and gaps (wave 6)
- [done] Create spec file for SU-19: cross-project coordination (wave 6)
- [done] Create spec file for SU-20: agent experience improvements (wave 6)
- [done] Create spec file for SU-21: DAG scaffolding enforcement (wave 6)
- [done] Create spec file for SU-22: dashboard and UI consolidation (wave 6)
- [done] Create `_overview.md` at spec-tree root
- [done] Run `tree` and include in report
- [done] Gate check: CA-SCRM-1, CA-SCRM-2 (tree communicates use cases), PP-CRAFT-5 (names reveal intent)

## Gate Check: Stage 5

- CA-SCRM-1: Tree communicates use cases — YES (wave folders encode build order, file names encode domain and scope)
- CA-SCRM-2: Stranger understands domain from `tree` — YES (reading tree output reveals: foundation first, then verify, then correctness, then reliability, then tests, then hygiene, then features)
- PP-CRAFT-5: Names reveal intent — YES (every file name describes its spec content, no generic names)
