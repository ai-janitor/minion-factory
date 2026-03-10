# SU-02: Verify Implemented Requirements — 11 Features

**Wave:** 1 (parallel with wave 0 — no code changes, test-writing only)
**Requirements:** 1.3, 1.4, 1.8, 2.2, 2.3, 2.5, 2.8, 5.3.3, 5.3.4, 5.4.1, 5.4.3
**Dependencies:** None (production code already exists)
**Dependents:** None

## Domain Preamble

Eleven requirements are already implemented but lack verification tests. This spec unit writes or verifies tests for each: poll path resolution (1.3), global agent heartbeat (1.4), backlog promote null validation (1.8), data lifecycle management (2.2), unbounded log files (2.3), formal state machines (2.5), message type taxonomy (2.8), error messages with remediation hints (5.3.3), fuzzy matching for CLI commands (5.3.4), auth scope-based permission narrowing (5.4.1), and cycle detection at flow YAML load time (5.4.3). No production code changes — each item needs at least one test proving the behavior works.

## Scope

- Write tests for all 11 already-implemented features
- No production code changes
- Soft dependency on SU-05 for the 2.5 (state machines) verification — must account for stale status

## Affected Files

- `tests/` (new test functions in existing or new test files)

## Boundary Edges

- E-11 (soft): SU-05 → this (state-transition: stale status affects 2.5 verification)
