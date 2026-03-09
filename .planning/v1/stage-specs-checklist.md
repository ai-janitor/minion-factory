# Stage 6 (Specifications) Checklist — v1 Audit

## DAG Gate Rules

- [done] CS-* spot check: specs consistent with Stage 4 CS-foundations decisions
- [done] PP-CONTRACT-1: preconditions, postconditions, invariants defined — each spec defines audit procedure with clear evidence criteria
- [done] PP-REQ-3: policy is metadata — skill rules referenced by ID, not hardcoded in specs
- [done] PP-REQ-4: glossary — terms consistent across specs (PASS/FAIL/NEEDS-DEEP-DIVE, YES/NO/N/A)
- [done] TDD-COV-1: contracts cover happy path — each spec defines what constitutes YES (compliant)
- [done] TDD-COV-2: edge cases — each spec defines what constitutes partial compliance
- [done] TDD-COV-3: error cases — each spec defines what constitutes NO (violation)
- [done] CA-BOUND-3: data crossing boundaries is simple structures — output format defined per spec

## Per-Spec Completeness

### AU-00 Broad Sweep
- [done] Scope defined — entire codebase
- [done] Skills listed — all 7, all 194 rules
- [done] Audit procedure — step-by-step scan method
- [done] Expected findings — 10 known findings from research embedded
- [done] Output format — triage table with PASS/FAIL/NEEDS-DEEP-DIVE

### AU-01 CLI Layer
- [done] Scope defined — 17 CLI files + output.py + entry point
- [done] Skills listed with specific rule IDs — CLI- (all 19), PP- (selected), CA- (selected), IC- (selected)
- [done] Audit procedure — 5 steps: command tree, output format, error handling, config, rule evaluation
- [done] Expected findings from research — 8 findings embedded
- [done] Output format — filled checklist + findings table + strengths

### AU-02 Database Layer
- [done] Scope defined — 7 db files + boundary checks (tasks/db.py, network/project_db.py)
- [done] Skills listed — CS-DATA (all 6), CS-CONSIST (all 5), CA- (selected), PP- (selected), IC- (selected)
- [done] Audit procedure — 6 steps: schema, migrations, connections, queries, cross-package, rule eval
- [done] Expected findings from research — 9 findings embedded
- [done] Output format — schema summary + filled checklist + boundary check

### AU-03 Comms + Crew + Lifecycle
- [done] Scope defined — 12 files across comms/, crew/, lifecycle.py
- [done] Skills listed — CS-COMM (all 5), CS-ERR (selected), CA- (selected), PP- (selected), IC- (selected)
- [done] Audit procedure — 6 steps: comms model, lifecycle walk, integrations, boundary B-05, config, rule eval
- [done] Expected findings from research — 7 findings embedded
- [done] Output format — comm model + lifecycle state machine + boundary check

### AU-04 Task Engine
- [done] Scope defined — 18 files in tasks/
- [done] Skills listed — CS-CONSIST (all 5), CS-ERR (all 5), CS-DATA (selected), CA- (selected), PP- (selected), IC- (selected)
- [done] Audit procedure — 6 steps: state machine, DAG, CRUD, task DB, rollup, rule eval
- [done] Expected findings from research — 8 findings embedded
- [done] Output format — state machine + DAG analysis + boundary check B-06

### AU-05 Daemon Runtime
- [done] Scope defined — 13 files including runner/ subdirectory
- [done] Skills listed — CS-CONSIST (all 5), CS-SCALE (all 5), CS-ERR (all 5), CA- (selected), PP- (selected), IC- (selected)
- [done] Audit procedure — 7 steps: mixin architecture, concurrency, resilience, config dup, lifecycle boundary, monitoring, rule eval
- [done] Expected findings from research — 7 findings embedded
- [done] Output format — mixin map + concurrency model + boundary checks B-05, B-07

### AU-06 Network API
- [done] Scope defined — 13+ files including handlers/
- [done] Skills listed — API- (all 37, aspirational), CS-SEC (all 5), CS-COMM (selected), CS-ERR (selected), CA- (selected), PP- (selected), IC- (selected)
- [done] Audit procedure — 7 steps: server architecture, auth, handler walk, input validation, response format, client boundary, rule eval
- [done] Expected findings from research — 8 findings embedded
- [done] Output format — endpoint inventory + auth model + boundary check B-04

### AU-07 Intel + Providers
- [done] Scope defined — 16 files across intel/ and providers/
- [done] Skills listed — CA- (primary, 8+ rules), PP- (selected), IC- (selected)
- [done] Audit procedure — 5 steps: intel analysis, provider protocol, provider comparison, dependency direction, rule eval
- [done] Expected findings from research — 7 findings embedded
- [done] Output format — provider interface + DRY comparison

### AU-08 Prompts + Missions
- [done] Scope defined — prompts/ + missions/ + missions/ (root YAML)
- [done] Skills listed — IC- (.py only per UF-002), PP- (selected), CA- (selected)
- [done] Audit procedure — 5 steps: prompt survey, loader analysis, mission survey, content-code boundary, rule eval
- [done] Expected findings from research — 6 findings embedded
- [done] Output format — prompt inventory + mission inventory

### AU-09 Tests
- [done] Scope defined — 20 test files + pytest config
- [done] Skills listed — TDD- (all 19), PP- (selected), CA-TEST (all 4)
- [done] Audit procedure — 6 steps: infrastructure, coverage map, quality walk, fixture duplication, test execution, rule eval
- [done] Expected findings from research — 9 findings embedded
- [done] Output format — coverage map + untested packages list

### AU-10 Cross-Cutting
- [done] Scope defined — 7 cross-cutting files + requirements/ + backlog/
- [done] Skills listed — CS-SEC (all 5), CA- (selected), PP- (critical DRY/ORTH/DECOUPLE), IC- (selected)
- [done] Audit procedure — 9 steps: logging, error handling, config scatter, auth, utilities, requirements, backlog, pattern registry, rule eval
- [done] Expected findings from research — 8 findings embedded, boundary ownership table
- [done] Output format — pattern analysis tables + de facto pattern registry

## Cross-Spec Consistency

- [done] All specs use same evidence criteria (YES/NO/N/A with file paths)
- [done] All specs use same output format (filled checklist + findings table + strengths)
- [done] Boundary dependencies documented in relevant specs (B-04 through B-07)
- [done] Skill overlap boundaries handled: systemic findings owned by AU-00 or AU-10, domain specs reference
- [done] Expected findings from research embedded in each spec — agents validate, not rediscover

## Reflect Gate: Cross-Spec Contract Reconciliation

- [done] Boundary B-04 (CLI <-> Network API): AU-01 and AU-06 both define their side of the endpoint contract
- [done] Boundary B-05 (Crew <-> Daemon): AU-03 and AU-05 both define their side of the lifecycle contract
- [done] Boundary B-06 (Tasks <-> DB): AU-04 and AU-02 both define their side of the DB pattern contract
- [done] Boundary B-07 (Daemon Config <-> Crew Config): AU-05 and AU-10 both define their side of the DRY finding
- [done] Skill overlap S-01 (IC-HDR): systemic finding owned by AU-00, all deep dives reference
- [done] Skill overlap S-02 (PP-DRY-1): cross-domain DRY owned by AU-10, domain-specific DRY in each spec
- [done] Skill overlap S-03 (CS-ERR): systemic finding owned by AU-10, domain-specific error handling per spec
- [done] Skill overlap S-04 (PP-DECOUPLE-5): systemic finding owned by AU-10, domain-specific direct reads per spec
- [done] Skill overlap S-05 (CA-TEST): AU-09 owns test architecture, domain specs note untested contracts
