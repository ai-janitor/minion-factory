# AU-00: Broad Sweep (Pass 1)

## Purpose

Scan the entire minion-factory codebase against all 7 skill checklists (194 rules) at surface level. Produce a triage list that tells deep dive agents WHERE to look, not WHAT's broken.

## Scope

**Entire codebase:**
- `src/minion/` — all packages (27 packages, ~150 Python files)
- `tests/` — 20 test files
- `missions/` — YAML templates
- `src/minion/prompts/` — markdown templates + Python loaders
- Project root — setup.py, pyproject.toml, CLAUDE.md

## Skills to Evaluate

All 7 skills, every rule. Surface-level assessment only.

### CS Foundations (37 rules)
- SEP-1 through SEP-5
- DATA-1 through DATA-6
- COMM-1 through COMM-5
- CONSIST-1 through CONSIST-5
- SCALE-1 through SCALE-5
- SEC-1 through SEC-5
- ERR-1 through ERR-5

### Clean Architecture (25 rules)
- DEP-1 through DEP-6
- SOLID-1 through SOLID-5
- COMP-1 through COMP-5
- BOUND-1 through BOUND-3
- SCRM-1, SCRM-2
- TEST-1 through TEST-4

### Pragmatic Programmer (33 rules)
- DRY-1 through DRY-3
- ORTH-1 through ORTH-3
- DECOUPLE-1 through DECOUPLE-5
- CONTRACT-1 through CONTRACT-4
- CRAFT-1 through CRAFT-6
- DELIVER-1 through DELIVER-5
- REQ-1 through REQ-4
- APPROACH-1 through APPROACH-5

### Implementation Coding Core (24 rules)
- LAY-1 through LAY-6
- HDR-1 through HDR-5
- SCALE-1 through SCALE-4 (IC-SCALE to distinguish from CS-SCALE)
- DATA-1 through DATA-5 (IC-DATA to distinguish from CS-DATA)
- VER-1 through VER-4

### Test-Driven Development (19 rules)
- CYC-1 through CYC-6
- QUAL-1 through QUAL-5
- COV-1 through COV-4
- BUG-1 through BUG-4

### AI-First CLI (19 rules)
- CMD-1 through CMD-4
- OUT-1 through OUT-4
- DISC-1 through DISC-3
- CFG-1 through CFG-3
- AGENT-1 through AGENT-5

### AI-First API (37 rules — aspirational per UF-001)
- ROUTE-1 through ROUTE-6
- CONF-1 through CONF-5
- TOK-1 through TOK-6
- CLI-1 through CLI-6
- SPEC-1 through SPEC-4
- INFRA-1 through INFRA-5
- DOC-1 through DOC-6
- PLAN-1 through PLAN-4

## Audit Procedure

### Step 1: Codebase Structure Survey
1. Read the directory tree: `tree src/minion/ -I __pycache__`
2. Read the test directory tree: `tree tests/`
3. Note package count, file count, test file count

### Step 2: Rapid Skill Scan
For EACH skill, scan the codebase at surface level:

**CS Foundations scan:**
- Read 2-3 representative files per package (prefer __init__.py, the largest file, and any db.py or config.py)
- For each CS- section, assess the codebase-wide pattern (not per-file)
- Focus on: error handling patterns, data ownership, concurrency model, security boundaries

**Clean Architecture scan:**
- Check import graph for dependency direction: `grep -r "from minion" src/minion/ | head -100`
- Check for circular imports
- Check top-level directory naming (screaming architecture)
- Check test directory structure

**Pragmatic Programmer scan:**
- Search for DRY violations: `grep -r "def get_db" src/` (known duplication candidate)
- Search for hardcoded config: `grep -r "os.environ" src/` (count and distribution)
- Check naming consistency across packages
- Check for train wrecks (method chaining)

**Implementation Coding Core scan:**
- Check for file headers: `head -20` on 10 representative files
- Check for layering evidence (stub comments, TODO markers)
- Check for schema validation at boundaries

**TDD scan:**
- Count test files vs source files
- Check test naming convention
- Check for conftest.py, markers, fixtures
- Map: which packages have tests, which don't

**AI-First CLI scan:**
- Run `minion --help` and check output
- Check command structure (verb-noun vs noun-verb)
- Check output formatting (--json, --quiet flags)
- Check exit codes

**AI-First API scan:**
- Read `src/minion/network/server.py` and `src/minion/network/router.py`
- Check routing pattern (verb prefixes?)
- Check response format consistency
- Check for OpenAPI/docs endpoint
- Note: evaluate as aspirational (stdlib http.server, not FastAPI)

### Step 3: Triage Classification
For each rule, classify as:
- **PASS** — likely compliant based on surface evidence
- **FAIL** — violation observed (note file/pattern)
- **NEEDS-DEEP-DIVE** — can't determine from surface scan

### Step 4: Produce Triage Output

## Expected Findings from Research

The research phase already identified these. Broad sweep should CONFIRM them, not rediscover:

1. **IC-HDR-1 through IC-HDR-5:** FAIL — zero formal headers, 95% docstrings (systemic, report once)
2. **ERR-5 (CS):** FAIL — 3 logging patterns, no strategy (systemic)
3. **ERR-1 (CS):** FAIL — 2 error patterns, no taxonomy (systemic)
4. **DRY-1 (PP):** FAIL — config duplication (daemon/config.py vs crew/config.py), auth duplication
5. **DECOUPLE-5 (PP):** FAIL — 36 direct os.environ reads vs defaults.py canonical
6. **SEC-5 (CS):** FAIL — no network input validation
7. **COV-1 through COV-3 (TDD):** FAIL — 17 packages with zero behavioral tests
8. **CMD-1 (CLI):** FAIL — noun-verb, not verb-noun
9. **OUT-1 (CLI):** FAIL — JSON default, not human default (inverted from skill expectation)
10. **ROUTE-1 through ROUTE-6 (API):** FAIL — no verb-prefix routing (aspirational)

## Output Format

Produce file: `.planning/v1/broad-sweep-triage.md`

```markdown
# Broad Sweep Triage — v1

## Summary
- Rules scanned: 194
- PASS: X
- FAIL: X
- NEEDS-DEEP-DIVE: X

## Triage by Skill

### CS Foundations
| Rule | Status | Evidence | Affected Domains |
|------|--------|----------|------------------|
| SEP-1 | PASS/FAIL/NDD | one-line evidence | D1, D4, ... |
...

### Clean Architecture
...

[repeat for all 7 skills]

## Priority Ranking (for Pass 2)
1. [spec] — [reason for priority]
...

## Systemic Findings (report once, reference everywhere)
| Finding | Rules | Severity | All Domains? |
|---------|-------|----------|-------------|
| No formal headers | IC-HDR-1-5 | Major | Yes |
...
```
