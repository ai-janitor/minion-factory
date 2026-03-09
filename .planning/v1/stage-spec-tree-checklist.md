# Stage 5 (Spec Tree) Checklist — v1 Audit

## DAG Gate Rules

- [done] CA-SCRM-1: Top-level directories communicate use cases, not framework — specs/ directory named by audit domain
- [done] CA-SCRM-2: A stranger can tell the domain from `tree` output alone — AU-XX-descriptive-name.md pattern
- [done] PP-CRAFT-5: Names reveal intent — each spec file name identifies its audit target

## Spec Tree Structure

- [done] specs/ directory created at `.planning/v1/specs/`
- [done] _overview.md — execution summary, spec inventory, agent context requirements
- [done] AU-00-broad-sweep.md — Pass 1 triage spec
- [done] AU-01-cli-layer.md — CLI deep dive spec
- [done] AU-02-database-layer.md — Database deep dive spec
- [done] AU-03-comms-and-crew.md — Comms + Crew + Lifecycle deep dive spec
- [done] AU-04-task-engine.md — Task Engine deep dive spec
- [done] AU-05-daemon-runtime.md — Daemon Runtime deep dive spec
- [done] AU-06-network-api.md — Network API deep dive spec
- [done] AU-07-intel-and-providers.md — Intel + Providers deep dive spec
- [done] AU-08-prompts-and-missions.md — Prompts + Missions deep dive spec
- [done] AU-09-tests.md — Tests deep dive spec
- [done] AU-10-cross-cutting.md — Cross-Cutting + Small Domains deep dive spec

## Tree Reviewability

- [done] `tree .planning/v1/specs/` output communicates the audit plan without opening any file
- [done] File names encode: sequence number + domain name
- [done] AU-00 clearly identified as broad sweep (first to execute)
- [done] AU-01 through AU-10 clearly identified as deep dives (parallel after AU-00)
