# Clean Requirements — Minion Factory Codebase Audit (Unbiased Derivation)

Derived from: REQUIREMENTS-RAW.md only. No prior clean requirements or upstream feedback consulted.

## 1. Audit Objective

Retrospective audit of an existing, working codebase against codified skill checklists. Produce actionable findings without requiring a system redesign.

## 2. Audit Inputs

### 2.1 Skill Checklists (Source of Audit Criteria)

Eight skills with mandatory compliance checklists, 218 rules total:

| Skill | Rules | Applicability |
|-------|-------|---------------|
| cs-foundations | 37 (SEP, DATA, COMM, CONSIST, SCALE, SEC, ERR) | Full codebase — architectural decisions |
| clean-architecture | 25 (DEP, SOLID, COMP, BOUND, SCRM, TEST) | Full codebase — structural compliance |
| pragmatic-programmer | 33 (DRY, ORTH, DECOUPLE, CONTRACT, CRAFT, DELIVER, REQ, APPROACH) | Full codebase — craftsmanship |
| implementation-coding-core | 24 (LAY, HDR, SCALE, DATA, VER) | Full codebase — implementation discipline |
| test-driven-development | 19 (CYC, QUAL, COV, BUG) | Tests directory + test coverage |
| fast-api | 24 (ARC, ERR, DI, PRD, REF) | Network API server (src/minion/network/) |
| ai-first-cli | 19 (CMD, OUT, DISC, CFG, AGENT) | CLI layer (primary interface) |
| ai-first-api | 37 (ROUTE, CONF, TOK, CLI, SPEC, INFRA, DOC, PLAN) | Network API server (if applicable) |

### 2.2 Codebase Under Audit

- ~150 Python source files
- 20 test files
- 11 mission templates (YAML)
- 7 agent role prompts
- 10 capability prompts
- Primary interface: CLI (`minion` command) consumed by AI agents
- Secondary interface: Network API server (FastAPI, `src/minion/network/`)
- Existing conventions: scaffold-first, filesystem-as-db, comment headers (per CLAUDE.md)

## 3. Audit Domains

Fifteen audit units mapped to codebase structure. Each domain is audited independently, then cross-domain findings are reconciled.

| # | Domain | Scope | Primary Skills |
|---|--------|-------|----------------|
| D1 | CLI layer | src/minion/cli/ (17 files) | ai-first-cli, pragmatic-programmer |
| D2 | Database layer | src/minion/db/ (7 files) | cs-foundations (DATA, CONSIST), clean-architecture |
| D3 | Comms system | src/minion/comms/ (5 files) | cs-foundations (COMM), clean-architecture |
| D4 | Task engine | src/minion/tasks/ (18 files) | cs-foundations (CONSIST, ERR), clean-architecture |
| D5 | Crew & lifecycle | src/minion/crew/, lifecycle.py (7 files) | cs-foundations (ERR), pragmatic-programmer |
| D6 | Daemon runtime | src/minion/daemon/ (13 files) | cs-foundations (CONSIST, SCALE, ERR), pragmatic-programmer |
| D7 | Network API | src/minion/network/ (13 files) | fast-api, ai-first-api, cs-foundations |
| D8 | Intel system | src/minion/intel/ (11 files) | clean-architecture, pragmatic-programmer |
| D9 | Providers | src/minion/providers/ (5 files) | clean-architecture (DEP, SOLID), pragmatic-programmer |
| D10 | Prompts | src/minion/prompts/ (17 files) | implementation-coding-core |
| D11 | Requirements | src/minion/requirements/ (5 files) | clean-architecture, pragmatic-programmer |
| D12 | Tests | tests/ (20 files) | test-driven-development (all sections) |
| D13 | Backlog | src/minion/backlog/ (8 files) | clean-architecture, pragmatic-programmer |
| D14 | Missions | src/minion/missions/, missions/ (15 files) | implementation-coding-core, pragmatic-programmer |
| D15 | Cross-cutting | auth.py, monitoring.py, filesafety.py, output.py, triggers.py, defaults.py, fs.py | cs-foundations (SEC), clean-architecture (COMP), pragmatic-programmer (DRY, ORTH) |

## 4. Audit Method

### 4.1 Two-Pass Audit (per MANIFESTO.md)

- **Pass 1 (Broad sweep):** One agent scans the entire codebase against all 218 rules. Produces a triage list: which rules are failing, how many violations per category, which files are involved. Fast and cheap — tells you where to look.
- **Pass 2 (Deep dive):** One agent per domain. Each agent reads the domain's code line by line and checks against applicable skill checklists. Slow and expensive — tells you what's broken.

### 4.2 Evidence Requirements

Every rule evaluation requires evidence:
- **YES** — file path, code pattern, or behavior observed
- **NO** — what's wrong, which files, what needs to change
- **N/A** — one-sentence justification why the rule doesn't apply

## 5. Audit Outputs

### 5.1 Completed Checklists
One filled checklist per skill (8 total), with YES/NO/N/A and evidence for every rule.

### 5.2 Findings List
Every NO from every checklist, with:
- Severity: critical / major / minor
- Affected files
- What needs to change
- Which domain(s) affected

### 5.3 Remediation Backlog
Prioritized list of what to fix first, based on:
- Severity (critical first)
- Blast radius (cross-domain issues before single-domain)
- Effort (quick wins before major refactors)

### 5.4 Strengths Report
Patterns the codebase already gets right — positive findings worth preserving and replicating.

## 6. Constraints

- Audit only — findings must be actionable without redesigning the system
- Respect existing CLAUDE.md conventions — the codebase has its own rules; audit measures compliance with those too
- No code changes during audit — observe and report only
