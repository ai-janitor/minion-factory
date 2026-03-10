# Stage 8 Checklist — v2 Implementation

## 8a: Context Setup
- [ ] Write implement-context.md (upstream-feedback + claim protocol only — NO specs/research/requirements)
- [ ] Initialize implement-claims.md (22 specs grouped by wave)
- [ ] Present plan to user for approval

## 8b: Wave 0 — Foundation (SU-01)
- [ ] Spawn Wave 0 agent: SU-01 Pattern Registry
- [ ] Wave 0 reflect gate — collect findings, resolve
- [ ] Wave 0 complete

## 8c: Wave 1 — Verification (SU-02)
- [ ] Spawn Wave 1 agent: SU-02 Verify 11 Features (test-only)
- [ ] Wave 1 reflect gate
- [ ] Wave 1 complete

## 8d: Wave 2 — Correctness Fixes (SU-03 through SU-07, parallel)
- [ ] Spawn Wave 2 agents: SU-03, SU-04, SU-05, SU-06, SU-07 (up to 5 parallel)
- [ ] Wave 2 reflect gate
- [ ] Wave 2 complete

## 8e: Wave 3 — Reliability (SU-08, SU-09, SU-10, depends on wave 0)
- [ ] Spawn Wave 3 agents: SU-08, SU-09, SU-10
- [ ] Wave 3 reflect gate
- [ ] Wave 3 complete

## 8f: Wave 4 — Test Infrastructure (SU-11 then SU-12)
- [ ] Spawn Wave 4a: SU-11 (test markers)
- [ ] Spawn Wave 4b: SU-12 (missing tests, depends on SU-11)
- [ ] Wave 4 reflect gate
- [ ] Wave 4 complete

## 8g: Wave 5 — Code Hygiene (SU-13 through SU-17, depends on wave 0)
- [ ] Spawn Wave 5 agents: SU-14 first, then SU-13; SU-15, SU-16, SU-17 parallel
- [ ] Wave 5 reflect gate
- [ ] Wave 5 complete

## 8h: Wave 6 — Features (SU-18 through SU-22, various dependencies)
- [ ] Spawn Wave 6 agents: SU-18 then SU-22; SU-19, SU-20, SU-21 parallel
- [ ] Wave 6 reflect gate
- [ ] Wave 6 complete

## 8i: Final Reconciliation
- [ ] All 22 specs marked [done] in implement-claims.md
- [ ] Run `uv run pytest` — all tests pass
- [ ] Record findings in upstream-feedback.md
- [ ] Present results to user
