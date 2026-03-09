# Decomposition — v1 Audit

Derived from: clean-requirements.md, research findings, upstream feedback.
Maps 15 audit domains (D1-D15) to audit spec units with skill checklists.

## Approach: Two-Pass Audit

Per MF-035 (two-pass audit), MANIFESTO.md, and DAG Stage 4 rules.

- **Pass 1 (AU-00):** Broad sweep. One agent, all 7 skills, entire codebase. Produces triage list.
- **Pass 2 (AU-01 through AU-10):** Deep dives. One spec per domain or grouped domains. Line-by-line against applicable checklists.

## Skill Inventory (Post-Research Refinement)

| Skill | Prefix | Rules | Notes |
|-------|--------|-------|-------|
| cs-foundations | CS- | 37 | Full codebase, architectural decisions |
| clean-architecture | CA- | 25 | Full codebase, structural compliance |
| pragmatic-programmer | PP- | 33 | Full codebase, craftsmanship |
| implementation-coding-core | IC- | 24 | Full codebase, implementation discipline |
| test-driven-development | TDD- | 19 | Tests directory + test coverage |
| ai-first-cli | CLI- | 19 | CLI layer only (D1) |
| ai-first-api | API- | 37 | Network API layer only (D7), aspirational per UF-001 |

**Dropped:** fast-api (24 rules) per UF-001 — network API uses stdlib http.server, not FastAPI.

**Effective total: 194 rules** (218 minus 24 fast-api).

## Spec Units

### AU-00: Broad Sweep (Pass 1)

| Field | Value |
|-------|-------|
| Name | Codebase-Wide Triage Scan |
| Domains | All (D1-D15) |
| Skills | CS-, CA-, PP-, IC-, TDD-, CLI-, API- (all 7) |
| Dependencies | None (first spec to execute) |
| Complexity | Medium — breadth over depth, one pass, triage-level evidence |
| Output | Triage list: failing rules, violation counts, affected files, severity estimate |

**Method:** Scan entire codebase once. For each skill, evaluate every rule at surface level. Mark PASS (likely compliant), FAIL (violation observed), NEEDS-DEEP-DIVE (can't tell from surface). Produce ranked triage list for Pass 2 prioritization.

---

### AU-01: CLI Layer Deep Dive

| Field | Value |
|-------|-------|
| Name | CLI Interface Audit |
| Domains | D1 (CLI layer) |
| Skills | CLI- (all 19), PP- (CRAFT, DECOUPLE, CONTRACT, DRY), CA- (SCRM, COMP), IC- (HDR, VER) |
| Dependencies | AU-00 (triage prioritization) |
| Complexity | High — 17 source files, primary interface, agent-facing |
| Scope | src/minion/cli/ (17 files), output.py, main.py entry point |

**Key questions from research:**
- CMD-1: noun-verb vs verb-noun (minion agent register = noun-verb, not verb-noun)
- OUT-1/2/3/4: JSON is default (inverted from ai-first-cli expectation of human default)
- AGENT-4: Exit codes partially implemented (0/1 only, no 2=usage)
- Top-level command leaks (deregister, rename, interrupt on root)

---

### AU-02: Database Layer Deep Dive

| Field | Value |
|-------|-------|
| Name | Database Architecture Audit |
| Domains | D2 (Database layer) |
| Skills | CS- (DATA all 6, CONSIST all 5), CA- (DEP, BOUND), PP- (DRY, ORTH), IC- (HDR) |
| Dependencies | AU-00 |
| Complexity | Medium — 7 files, consistent pattern, clean concern |
| Scope | src/minion/db/ (7 files) |

**Key questions from research:**
- Three separate DBs (project, coordinator, network) — data ownership clear?
- Inline SQL everywhere — no repository abstraction
- Migration system v1-v13, idempotent, transactional — well-designed
- WAL mode + per-operation connections — concurrency model

---

### AU-03: Comms + Crew + Lifecycle Deep Dive

| Field | Value |
|-------|-------|
| Name | Agent Communication and Lifecycle Audit |
| Domains | D3 (Comms), D5 (Crew & lifecycle) |
| Skills | CS- (COMM all 5, ERR), CA- (DEP, SOLID, BOUND), PP- (ORTH, DRY, CONTRACT), IC- (HDR) |
| Dependencies | AU-00 |
| Complexity | Medium — 12 files combined, tightly coupled domains |
| Scope | src/minion/comms/ (5 files), src/minion/crew/ (7 files), lifecycle.py |

**Grouping rationale (CA-COMP-4, CA-COMP-5):** Comms and crew change together (agent registration triggers comms registration). Crew lifecycle orchestrates comms. Same actors.

---

### AU-04: Task Engine Deep Dive

| Field | Value |
|-------|-------|
| Name | Task Engine Audit |
| Domains | D4 (Task engine) |
| Skills | CS- (CONSIST all 5, ERR all 5, DATA), CA- (DEP, SOLID, COMP), PP- (CRAFT, CONTRACT, DRY), IC- (HDR, SCALE) |
| Dependencies | AU-00 |
| Complexity | High — 18 files, largest package, DAG/gates/CRUD/engine/rollup |
| Scope | src/minion/tasks/ (18 files) |

**Key questions from research:**
- Flow gates and validation — consistency model?
- Task DAG — cycle detection? ordering guarantees?
- Deep test coverage exists — TDD rules applicable

---

### AU-05: Daemon Runtime Deep Dive

| Field | Value |
|-------|-------|
| Name | Daemon Runtime Audit |
| Domains | D6 (Daemon runtime) |
| Skills | CS- (CONSIST, SCALE, ERR all sections), CA- (DEP, SOLID), PP- (CRAFT, DECOUPLE, CONTRACT), IC- (HDR, SCALE) |
| Dependencies | AU-00 |
| Complexity | High — 13 files, mixin pattern in runner/, concurrency, long-running |
| Scope | src/minion/daemon/ (13 files including runner/ subdirectory) |

**Key questions from research:**
- Mixin pattern (_execution, _polling, _hp, _state, _watcher_mode) — orthogonality?
- Threading with Lock — concurrency strategy coherent?
- Broad except: Exception:pass — intentional resilience or swallowed errors?
- Config duplication with crew/config.py

---

### AU-06: Network API Deep Dive

| Field | Value |
|-------|-------|
| Name | Network API Audit |
| Domains | D7 (Network API) |
| Skills | API- (all 37, evaluated as aspirational per UF-001), CS- (COMM, SEC, ERR), CA- (DEP, BOUND), PP- (CRAFT, DECOUPLE), IC- (HDR, DATA) |
| Dependencies | AU-00 |
| Complexity | High — 13 files + handlers, stdlib http.server, security surface |
| Scope | src/minion/network/ (11 files + handlers/) |

**Key questions from research:**
- AuthMixin defined but NOT wired — server.py still uses inline _check_token
- No request validation, no OpenAPI, no middleware
- Consistent JSON responses — good pattern
- Bearer token optional (no token = all pass) — security gap

---

### AU-07: Intel + Providers Deep Dive

| Field | Value |
|-------|-------|
| Name | Intel and Providers Audit |
| Domains | D8 (Intel), D9 (Providers) |
| Skills | CA- (DEP, SOLID, BOUND, COMP), PP- (ORTH, DRY, DECOUPLE), IC- (HDR) |
| Dependencies | AU-00 |
| Complexity | Medium — 16 files combined, knowledge layer + provider abstraction |
| Scope | src/minion/intel/ (11 files), src/minion/providers/ (5 files) |

**Grouping rationale:** Both are mid-tier packages with similar skill applicability (clean-architecture dominant). Neither has test coverage. Provider protocol pattern is a CA-SOLID focus.

---

### AU-08: Prompts + Missions Deep Dive

| Field | Value |
|-------|-------|
| Name | Prompts and Missions Audit |
| Domains | D10 (Prompts), D14 (Missions) |
| Skills | IC- (HDR partially — .md files exempt per UF-002, .py files apply), PP- (DRY, ORTH, CRAFT), CA- (COMP) |
| Dependencies | AU-00 |
| Complexity | Low — mostly .md template files, 5 Python loaders |
| Scope | src/minion/prompts/ (17 files), src/minion/missions/ (5 files), missions/ (YAML templates) |

**Grouping rationale:** Both are content/template-heavy with thin Python loaders. IC-HDR applies only to .py files (per UF-002). Missions load prompts — same change axis.

---

### AU-09: Tests Deep Dive

| Field | Value |
|-------|-------|
| Name | Test Suite Audit |
| Domains | D12 (Tests) |
| Skills | TDD- (all 19), PP- (DELIVER, CRAFT-4), CA- (TEST all 4) |
| Dependencies | AU-00 |
| Complexity | Medium — 20 test files, 224 functions, but concentrated analysis |
| Scope | tests/ (20 files) |

**Key questions from research:**
- No conftest.py — fixture duplication across 11 files
- No pytest markers — no unit/integration/smoke separation
- Flat directory — not structured by use case (CA-TEST-2)
- Zero mocks — all real DB/filesystem
- 17 packages with zero behavioral test coverage

---

### AU-10: Cross-Cutting + Remaining Domains Deep Dive

| Field | Value |
|-------|-------|
| Name | Cross-Cutting Concerns and Small Domains Audit |
| Domains | D11 (Requirements), D13 (Backlog), D15 (Cross-cutting) |
| Skills | CS- (SEC all 5), CA- (COMP, DEP), PP- (DRY, ORTH), IC- (HDR) |
| Dependencies | AU-00 |
| Complexity | Medium — cross-cutting findings are highest impact per research |
| Scope | src/minion/requirements/ (5 files), src/minion/backlog/ (8 files), auth.py, monitoring.py, filesafety.py, output.py, triggers.py, defaults.py, fs.py |

**Grouping rationale:** Requirements and backlog are small standalone packages with deep test coverage (already validated). Cross-cutting files are the biggest finding source per research (logging 3 patterns, error handling 2 patterns, config duplication). Grouped for efficiency — the cross-cutting findings span all domains.

**Key focus:**
- Logging: 3 competing patterns (logging.getLogger, print, click.echo)
- Error handling: dict-return + raise stdlib, no domain exceptions
- Config: defaults.py canonical but 36 direct os.environ reads scattered
- Auth: _check_token duplication between server.py and network/auth.py

## Dependency Graph

```
AU-00 (Broad Sweep)
  |
  ├── AU-01 (CLI)
  ├── AU-02 (Database)
  ├── AU-03 (Comms + Crew)
  ├── AU-04 (Task Engine)
  ├── AU-05 (Daemon)
  ├── AU-06 (Network API)
  ├── AU-07 (Intel + Providers)
  ├── AU-08 (Prompts + Missions)
  ├── AU-09 (Tests)
  └── AU-10 (Cross-Cutting + Small Domains)
```

- AU-00 must complete first (provides triage prioritization for Pass 2).
- AU-01 through AU-10 can all run in parallel after AU-00.
- Cross-domain reconciliation runs after all deep dives complete.

## Execution Priority (Post-Triage)

Based on research findings, expected priority order:

1. **AU-10** (Cross-cutting) — highest blast radius, logging/error/config affect everything
2. **AU-09** (Tests) — 17 untested packages, TDD findings are foundational
3. **AU-01** (CLI) — primary interface, agent-facing, highest user visibility
4. **AU-06** (Network API) — security surface, aspirational gap analysis
5. **AU-04** (Task Engine) — largest package, consistency/error handling critical
6. **AU-05** (Daemon) — concurrency, long-running, mixin complexity
7. **AU-03** (Comms + Crew) — communication contracts, lifecycle
8. **AU-02** (Database) — cleanest concern per research, likely few findings
9. **AU-07** (Intel + Providers) — mid-tier, untested
10. **AU-08** (Prompts + Missions) — mostly content, low code complexity

Priority may change after AU-00 triage completes.

## Summary Table

| Spec | Name | Domains | Skill Count | Est. Findings |
|------|------|---------|-------------|---------------|
| AU-00 | Broad Sweep | D1-D15 | 194 rules | Triage list |
| AU-01 | CLI | D1 | ~50 | 8-12 |
| AU-02 | Database | D2 | ~30 | 3-5 |
| AU-03 | Comms + Crew | D3, D5 | ~35 | 6-10 |
| AU-04 | Task Engine | D4 | ~40 | 8-12 |
| AU-05 | Daemon | D6 | ~40 | 10-15 |
| AU-06 | Network API | D7 | ~55 | 15-20 |
| AU-07 | Intel + Providers | D8, D9 | ~30 | 5-8 |
| AU-08 | Prompts + Missions | D10, D14 | ~20 | 3-5 |
| AU-09 | Tests | D12 | ~30 | 10-15 |
| AU-10 | Cross-Cutting | D11, D13, D15 | ~35 | 12-18 |
