# Boundary Dependency Map — v1 Audit

Living artifact. Created at Stage 4, refined at every reflect gate through Stage 9.

For an audit, boundaries are between:
1. Broad sweep findings and deep dive prioritization
2. Cross-domain findings (violations spanning multiple packages)
3. Skill overlap (same rule evaluated in two domains — need consistent evaluation)

## Layer 1: Spec-to-Spec Boundaries (Stage 4)

### B-01: AU-00 Triage -> All Deep Dives

| Field | Value |
|-------|-------|
| Boundary | Broad sweep output feeds deep dive prioritization |
| Contract type | Data shape — triage list with per-rule PASS/FAIL/NEEDS-DEEP-DIVE |
| Shared artifact | `.planning/v1/broad-sweep-triage.md` (produced by AU-00, consumed by AU-01 through AU-10) |
| Risk | If triage categories are vague, deep dives waste time re-scanning |

### B-02: AU-10 Cross-Cutting -> All Domain Deep Dives

| Field | Value |
|-------|-------|
| Boundary | Cross-cutting findings affect evaluation of every domain |
| Contract type | Naming contract — error handling pattern, logging pattern, config pattern |
| Shared artifact | Cross-cutting findings list with per-file classification |
| Risk | Domain deep dives may independently discover the same cross-cutting violation and report it as domain-specific rather than systemic |

**Resolution protocol:** If a domain deep dive finds a pattern violation, check if AU-10 already classified it as cross-cutting. If yes, reference AU-10 finding. If no, escalate to AU-10 as new cross-cutting finding.

### B-03: AU-09 Tests -> All Domain Deep Dives

| Field | Value |
|-------|-------|
| Boundary | Test coverage gaps inform domain-level TDD findings |
| Contract type | Data shape — coverage map: package -> test file -> function count |
| Shared artifact | `.planning/v1/research/test-coverage.md` (already exists) |
| Risk | Domain auditors may redundantly note "no tests" without referencing AU-09's comprehensive gap list |

### B-04: AU-01 CLI -> AU-06 Network API

| Field | Value |
|-------|-------|
| Boundary | CLI is client, Network API is server — shared interface contract |
| Contract type | API contract — endpoint paths, request/response shapes, auth mechanism |
| Shared code | src/minion/network/client.py (CLI's client for network API) |
| Risk | CLI audit and API audit may evaluate the same interface inconsistently |

### B-05: AU-03 Comms+Crew -> AU-05 Daemon

| Field | Value |
|-------|-------|
| Boundary | Crew spawns daemons, daemon uses comms for message passing |
| Contract type | State transition — agent lifecycle (registered -> active -> polling -> stopped) |
| Shared code | crew/daemon.py (crew's daemon interface), daemon/contracts.py |
| Risk | Lifecycle state inconsistencies between crew's model and daemon's model |

### B-06: AU-04 Task Engine -> AU-02 Database

| Field | Value |
|-------|-------|
| Boundary | Tasks package has its own db.py — potential duplication of db/ patterns |
| Contract type | Data access pattern — tasks/db.py vs db/ package conventions |
| Shared code | tasks/db.py imports from db/ |
| Risk | Task-specific DB patterns may diverge from canonical db/ patterns |

### B-07: AU-05 Daemon -> AU-10 Cross-Cutting (Config)

| Field | Value |
|-------|-------|
| Boundary | daemon/config.py duplicates crew/config.py parsing logic |
| Contract type | Code duplication — same YAML parsing, different files |
| Shared data | Crew config YAML format |
| Risk | Already identified as DRY violation. Both AU-05 and AU-10 will evaluate — need consistent severity rating |

## Skill Overlap Boundaries

Rules that apply in multiple deep dives and must be evaluated consistently.

### S-01: IC-HDR-1 through IC-HDR-5 (Comment Headers)

| Applies to | AU-01 through AU-10 (all deep dives) |
|------------|---------------------------------------|
| Risk | Research found ZERO formal headers, 95% docstrings. This is one finding reported once, not per-file. |
| Resolution | AU-00 broad sweep classifies this as systemic. Deep dives reference AU-00 finding, do not re-report. |

### S-02: PP-DRY-1 (Single Authoritative Representation)

| Applies to | AU-03, AU-05, AU-07, AU-10 |
|------------|------------------------------|
| Risk | Config duplication (daemon/config.py vs crew/config.py), auth duplication (server.py vs network/auth.py), logging pattern scatter |
| Resolution | Each deep dive notes DRY violations within its scope. AU-10 aggregates cross-domain DRY violations. |

### S-03: CS-ERR-1 through CS-ERR-5 (Error Handling)

| Applies to | AU-04, AU-05, AU-06, AU-10 |
|------------|------------------------------|
| Risk | Two error patterns (dict-return vs raise). Each deep dive may assess differently. |
| Resolution | AU-10 defines the systemic finding (two patterns exist). Domain deep dives evaluate whether their domain's usage of either pattern is internally consistent. |

### S-04: PP-DECOUPLE-5 (Config Externalized)

| Applies to | AU-01, AU-05, AU-06, AU-10 |
|------------|------------------------------|
| Risk | 36 direct os.environ reads scattered across 20 files vs defaults.py canonical |
| Resolution | AU-10 owns the systemic finding. Domain deep dives note domain-specific direct reads. |

### S-05: CA-TEST-1 through CA-TEST-4 (Test Architecture)

| Applies to | AU-09 (primary), all domain deep dives (secondary) |
|------------|------------------------------------------------------|
| Risk | AU-09 is the comprehensive test audit. Domain deep dives should not independently re-audit test quality. |
| Resolution | Domain deep dives note untested behavioral contracts in their domain. AU-09 owns all test architecture findings. |

## Cross-Domain Finding Categories (Expected)

Based on research, these cross-domain findings will span multiple spec units:

| Category | Expected Finding | Affected Specs |
|----------|-----------------|----------------|
| Logging chaos | 3 patterns, no config | AU-05, AU-06, AU-10 (systemic) |
| Error handling duality | dict-return + raise, no hierarchy | AU-04, AU-05, AU-06, AU-10 |
| Comment header convention | Docstrings not formal headers | All (systemic, report once) |
| Test coverage gap | 17 packages untested | AU-09 (primary), all others (reference) |
| Config scatter | 36 direct env reads | AU-01, AU-05, AU-06, AU-10 |
| No pattern registry | De facto patterns undocumented | AU-10 (systemic) |

## Reconciliation Protocol

After all deep dives complete:

1. **Collect all findings** from AU-01 through AU-10
2. **Deduplicate** — same violation found in multiple specs gets one entry with cross-references
3. **Classify** — systemic (cross-cutting) vs domain-specific
4. **Assign severity** — critical/major/minor, consistent across specs
5. **Check boundary contracts** — for each boundary above, verify both sides agree on the finding
6. **Update this map** — add function-level boundaries discovered during deep dives
