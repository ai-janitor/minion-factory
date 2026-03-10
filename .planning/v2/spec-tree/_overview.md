# Spec Tree Overview — v2

**Total spec units:** 22
**Total requirements covered:** 72 (73 minus 1 deferred to v3)
**Waves:** 7 (0 through 6)
**Dependency edges:** 12 (documented in boundary-dependency-map.md)

## Category Breakdown

| Wave | Directory | Specs | Focus |
|------|-----------|-------|-------|
| 0 | `wave-0-foundation/` | 1 | Pattern registry — blocks waves 3 and 5 |
| 1 | `wave-1-verification/` | 1 | Verify 11 already-implemented features (tests only) |
| 2 | `wave-2-correctness-fixes/` | 5 | Independent bug fixes — all parallel |
| 3 | `wave-3-reliability-and-quality/` | 3 | Exception narrowing, assertions, docs (depends on wave 0) |
| 4 | `wave-4-test-infrastructure/` | 2 | Markers, fixtures, coverage gaps (SU-11 before SU-12) |
| 5 | `wave-5-code-hygiene/` | 5 | Dedup, dependency fixes, CLI/config cleanup (mostly parallel) |
| 6 | `wave-6-features-and-agent-experience/` | 5 | Network API, cross-project, agent DX, dashboard |

## Build Order

1. **Wave 0** (SU-01) — foundation, must complete first
2. **Wave 1** (SU-02) — can run parallel with wave 0
3. **Wave 2** (SU-03 through SU-07) — all 5 specs run in parallel
4. **Wave 3** (SU-08 through SU-10) — after wave 0 completes
5. **Wave 4** (SU-11 then SU-12) — parallel with waves 2-3
6. **Wave 5** (SU-14 then SU-13; SU-15, SU-16, SU-17 parallel) — after wave 0
7. **Wave 6** (SU-18 then SU-22; SU-19, SU-20, SU-21 parallel) — various dependencies

## Critical Path

SU-01 → SU-14 → SU-13 (pattern registry → dedup → dependency fixes)
SU-17 → SU-18 → SU-22 (dead code → API parity → dashboard)
SU-04 → SU-19 (global comms → cross-project coordination)
SU-03 → SU-21 (DAG self-review → scaffolding enforcement)

## What Changed from v1

v1 had no spec tree — decomposition went directly to implementation. This is the first formal spec tree for the minion-factory project. Key differences:

- **v1:** 62 audit findings mapped to 54 backlog items, no structured decomposition
- **v2:** 73 clean requirements decomposed into 22 spec units across 7 waves
- **v2 additions:** Formal dependency graph, boundary dependency map, wave-based build order, CS-foundations review
- **Deferred:** Composite agent key (5.1) moved to v3

## Naming Convention

All file and folder names follow filesystem-as-DB convention:
- Wave folders encode build order and domain: `wave-2-correctness-fixes/`
- Spec files describe contents: `bare-exception-narrowing-87-blocks-across-43-files.md`
- No generic names: no `spec-001.md`, no `fixes/`, no `utils.md`
- An agent can understand the v2 architecture from `tree` output alone

## Next Stage

Stage 6 (Specifications) — fill each spec file with full behavioral contracts, constraints, edge cases. Write WHAT not HOW. Then extract test contracts to `test-contracts.md`.
