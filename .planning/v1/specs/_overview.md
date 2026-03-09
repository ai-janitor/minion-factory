# Audit Spec Overview — v1

## Summary

- **Total specs:** 11 (AU-00 broad sweep + AU-01 through AU-10 deep dives)
- **Total rules:** 194 across 7 skill checklists
- **Execution order:** AU-00 first (blocking), then AU-01 through AU-10 in parallel
- **Cross-domain reconciliation:** after all deep dives complete

## Spec Inventory

| Spec | Name | Skills | Rule Count | Est. Effort |
|------|------|--------|------------|-------------|
| AU-00 | Broad Sweep | All 7 | 194 | Medium — breadth scan, triage-level |
| AU-01 | CLI Layer | CLI-, PP-, CA-, IC- | ~50 | High — 17 source files, primary interface |
| AU-02 | Database Layer | CS-, CA-, PP-, IC- | ~30 | Medium — 7 files, consistent pattern |
| AU-03 | Comms + Crew | CS-, CA-, PP-, IC- | ~35 | Medium — 12 files, tightly coupled |
| AU-04 | Task Engine | CS-, CA-, PP-, IC- | ~40 | High — 18 files, largest package |
| AU-05 | Daemon Runtime | CS-, CA-, PP-, IC- | ~40 | High — 13 files, mixin pattern, concurrency |
| AU-06 | Network API | API-, CS-, CA-, PP-, IC- | ~55 | High — 13 files, security surface |
| AU-07 | Intel + Providers | CA-, PP-, IC- | ~30 | Medium — 16 files, mid-tier |
| AU-08 | Prompts + Missions | IC-, PP-, CA- | ~20 | Low — mostly .md templates |
| AU-09 | Tests | TDD-, PP-, CA- | ~30 | Medium — 20 test files, concentrated |
| AU-10 | Cross-Cutting | CS-, CA-, PP-, IC- | ~35 | Medium — highest blast radius |

## Execution Plan

```
Phase 1: AU-00 (Broad Sweep)
  - One agent, all skills, entire codebase
  - Output: broad-sweep-triage.md
  - Blocking — must complete before Phase 2

Phase 2: AU-01 through AU-10 (Deep Dives) — ALL PARALLEL
  - One agent per spec
  - Each reads: its spec file + broad-sweep-triage.md
  - Output per spec: filled checklist, findings list, strengths list

Phase 3: Cross-Domain Reconciliation
  - Deduplicate findings across specs
  - Classify systemic vs domain-specific
  - Assign consistent severity
  - Check boundary contracts (per boundary-dependency-map.md)
  - Produce: consolidated findings, remediation backlog, strengths report
```

## Agent Context Requirements

Each deep dive agent receives:
1. Its spec file (AU-XX-*.md) — contains everything needed
2. broad-sweep-triage.md — triage prioritization from AU-00
3. Access to source files listed in its spec's Scope section

Agents do NOT need:
- Other specs (isolation prevents cross-contamination)
- Full decomposition.md (already distilled into each spec)
- Research files (relevant findings embedded in each spec)
