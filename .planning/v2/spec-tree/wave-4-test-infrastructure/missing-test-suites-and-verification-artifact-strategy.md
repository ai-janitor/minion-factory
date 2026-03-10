# SU-12: Missing Test Suites and Verification Artifact Strategy

**Wave:** 4 (after SU-11)
**Requirements:** 3.2, 3.3
**Dependencies:** SU-11 (test infrastructure should be clean first)
**Dependents:** None

## Domain Preamble

Coverage gaps exist: zero tests for missions package (load_mission, resolve_slots, list_missions, suggest_party), missing reference integrity tests for CLI commands, and no verification artifacts produced per DAG stage. This spec identifies uncovered modules by comparing test files to source modules, writes tests for the gaps, and designs the verification artifact strategy — what each DAG stage produces as evidence of completion. Coverage analysis feeds into artifact design.

## Scope

- Compare test files to source modules — identify uncovered modules
- Write tests for missions package and other gaps
- Design verification artifact strategy (what evidence each DAG stage produces)
- Use pytest markers from SU-11

## Affected Files

- `tests/` (new test files for uncovered modules)
- `.planning/v2/verification-strategy.md` (new)

## Boundary Edges

- E-07: SU-11 → this (naming: must use registered pytest marker names)
