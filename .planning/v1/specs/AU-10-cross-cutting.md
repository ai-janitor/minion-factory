# AU-10: Cross-Cutting + Remaining Domains Deep Dive

## Purpose

Audit of cross-cutting concerns (logging, error handling, config, auth duplication) and small standalone packages (requirements, backlog). Cross-cutting findings have the highest blast radius — they affect every domain. This spec OWNS systemic findings. Domain deep dives reference AU-10 for cross-cutting issues rather than independently classifying them.

## Scope

### Cross-Cutting Files (D15)
| File | Description |
|------|-------------|
| `src/minion/auth.py` | Authorization (require_class, require_scope) |
| `src/minion/monitoring.py` | Monitoring/status |
| `src/minion/filesafety.py` | File safety utilities |
| `src/minion/output.py` | Output formatting (JSON/text funnel) |
| `src/minion/triggers.py` | Trigger logic |
| `src/minion/defaults.py` | Canonical config/defaults |
| `src/minion/fs.py` | Filesystem utilities |

### Requirements Package (D11)
| Directory/File | Description |
|----------------|-------------|
| `src/minion/requirements/` | Requirements management (5 files) |

### Backlog Package (D13)
| Directory/File | Description |
|----------------|-------------|
| `src/minion/backlog/` | Backlog management (8 files) |

Read ALL cross-cutting files, ALL files in requirements/, ALL files in backlog/.

**Also scan (for cross-cutting pattern verification):**
- `grep -r "logging.getLogger" src/minion/` — logging pattern 1
- `grep -rn "print(" src/minion/` — logging pattern 2
- `grep -r "click.echo" src/minion/` — logging pattern 3
- `grep -r "os.environ" src/minion/` — direct env reads (bypassing defaults.py)
- `grep -r '"error"' src/minion/` — dict-return error pattern
- `grep -r "raise " src/minion/` — exception error pattern

## Skills to Evaluate

### CS Foundations — Security (CS-SEC, all 5 rules)
- **SEC-1:** Trust boundaries — auth.py defines local trust boundary
  - **How to check:** Read auth.py. Map require_class and require_scope. Where is the trust boundary?
- **SEC-2:** Authentication — MINION_CLASS + MINION_AGENT_NAME (local), Bearer token (network)
- **SEC-3:** Authorization — five classes (coder, builder, recon, auditor, lead) with scope-based access
  - **How to check:** Read auth.py. List all class/scope combinations. Check if they're enforced consistently.
- **SEC-4:** Secrets management — env vars, no secrets in code
  - **How to check:** Grep for hardcoded tokens, passwords, secrets in source files.
- **SEC-5:** Input validation — cross-cutting validation patterns
  - **How to check:** Read filesafety.py. What file safety checks exist?

### Clean Architecture (selected rules)
- **CA-COMP-1:** No cycles in dependency graph
  - **How to check:** Map imports for all cross-cutting files. Check for circular dependencies.
- **CA-COMP-2:** Dependencies toward stability — cross-cutting files should be stable (depended upon, rarely changing)
- **CA-DEP-1:** Dependencies inward — cross-cutting utilities at bottom layer

### Pragmatic Programmer (selected rules — CRITICAL for cross-cutting)
- **PP-DRY-1:** Single authoritative representation — THE key rule for cross-cutting concerns
  - **How to check:** For each cross-cutting concern (logging, config, error handling, auth), verify there is ONE authoritative pattern:
    - **Logging:** 3 patterns (logging.getLogger: 3 files, print: 23 files, click.echo: 9 files). This is a DRY violation.
    - **Config:** defaults.py is canonical, but 36 direct os.environ reads scattered across 20 files.
    - **Error handling:** dict-return AND raise stdlib — two patterns, no single authority.
    - **Auth:** auth.py defines require_class/require_scope, but network/server.py has inline _check_token.
- **PP-DRY-2:** No inter-developer duplication
  - **How to check:** Check for identical/similar utility functions in different packages.
- **PP-ORTH-1:** Components self-contained
- **PP-ORTH-3:** Change to one module doesn't ripple to unrelated modules
- **PP-DECOUPLE-5:** Configuration externalized
  - **How to check:** Catalog all 36 direct os.environ reads. Classify: should each use defaults.py instead?

### Implementation Coding Core (selected rules)
- **IC-HDR-1 through IC-HDR-5:** Reference AU-00 systemic finding

## Audit Procedure

### Step 1: Logging Chaos Analysis
1. Run the three grep commands for logging patterns
2. Classify each occurrence: which pattern, which file, which package
3. Determine: is there a canonical logging approach? (No per research)
4. Assess severity: how does inconsistent logging affect debugging and operations?
5. Produce: logging pattern distribution table

### Step 2: Error Handling Duality Analysis
1. Grep for dict-return error pattern: `{"error": ...}` returns
2. Grep for exception raises: `raise ValueError`, `raise FileNotFoundError`, etc.
3. Classify each file: which pattern does it use?
4. Check: is there a consistent rule (dict-return for CLI, raise for config)?
5. Check: are there any custom Exception subclasses?
6. Assess: could callers accidentally miss error dicts?

### Step 3: Config Scatter Analysis
1. Read `defaults.py` in full — the canonical config source
2. Grep for `os.environ` across entire codebase
3. For each direct os.environ read:
   a. Is it already in defaults.py? (should use defaults.py instead)
   b. Is it unique to this context? (should be added to defaults.py)
   c. Is it necessary? (some may be redundant)
4. Produce: config scatter table (file, env var, in defaults.py?)

### Step 4: Auth Pattern Analysis
1. Read `src/minion/auth.py` in full
2. Read `src/minion/network/auth.py` (if exists, referenced in research)
3. Read `src/minion/network/server.py` _check_token inline
4. Map: where auth is enforced (CLI decorators vs network inline check)
5. Check: duplication between auth.py and network auth

### Step 5: Cross-Cutting Utility Review
1. Read monitoring.py — what does it monitor? Is it sufficient?
2. Read filesafety.py — what safety checks? Consistent usage?
3. Read fs.py — filesystem utilities. DRY with filesafety.py?
4. Read triggers.py — trigger logic. Relationship to daemon/triggers.py?
5. Read output.py — output funnel. Is it the single authority for CLI output?

### Step 6: Requirements Package Quick Audit
1. Read all files in requirements/
2. Check: requirements package has deep test coverage (per research). Verify.
3. Apply IC-HDR, PP-DRY, PP-ORTH rules.

### Step 7: Backlog Package Quick Audit
1. Read all files in backlog/
2. Check: backlog package has deep test coverage (per research). Verify.
3. Apply IC-HDR, PP-DRY, PP-ORTH rules.

### Step 8: Pattern Registry Assessment
1. Document the de facto patterns for each cross-cutting concern:

| Concern | De Facto Pattern | Documented? | Consistent? |
|---------|-----------------|-------------|-------------|
| Logging | 3 competing patterns | No | No |
| Error handling | dict-return + raise | No | Partially |
| Config | defaults.py + direct env | No | Partially |
| Auth | auth.py + inline _check_token | No | No |
| Output | output.py funnel | Implicit | Yes |
| DB access | db/get_db() | Implicit | Mostly |

2. Note: no formal pattern-registry.md exists. This is a finding.

### Step 9: Rule-by-Rule Evaluation

## Expected Findings from Research

1. **Logging chaos (PP-DRY-1 FAIL, ERR-5 FAIL):** 3 competing patterns, no config. CRITICAL — highest blast radius.
2. **Error handling duality (PP-DRY-1 FAIL, ERR-1 FAIL):** dict-return + raise stdlib, no domain exception hierarchy. MAJOR.
3. **Config scatter (PP-DECOUPLE-5 partial FAIL):** 36 direct os.environ reads vs defaults.py canonical. MAJOR.
4. **Auth duplication:** _check_token in server.py vs AuthMixin in network/auth.py. MINOR (contained).
5. **No pattern registry:** De facto patterns undocumented. MAJOR — agents have no reference.
6. **IC-HDR FAIL:** Systemic (reference AU-00).
7. **Requirements and backlog:** Already well-tested, likely few findings.
8. **monitoring.py:** Basic status, not real observability.

## Boundary Responsibilities

AU-10 OWNS these cross-domain findings. Other specs REFERENCE AU-10:

| Finding | Owned By | Referenced By |
|---------|----------|---------------|
| Logging 3 patterns | AU-10 | AU-05, AU-06 |
| Error handling duality | AU-10 | AU-04, AU-05, AU-06 |
| Config scatter | AU-10 | AU-01, AU-05, AU-06 |
| Auth duplication | AU-10 | AU-06 |
| No pattern registry | AU-10 | All |
| Comment headers | AU-00 (systemic) | All |

## Output Format

```markdown
# AU-10 Cross-Cutting + Small Domains Audit Results

## Cross-Cutting Pattern Analysis

### Logging
[3-pattern distribution table, file counts, recommendation]

### Error Handling
[dict-return vs raise distribution, file classification]

### Configuration
[defaults.py coverage, scatter table, 36 direct reads classified]

### Auth
[auth.py vs network inline, duplication assessment]

### Pattern Registry (De Facto)
[Table of current patterns, documented?, consistent?]

## Small Domain Results

### Requirements Package
[Quick audit results, test coverage confirmed]

### Backlog Package
[Quick audit results, test coverage confirmed]

## Filled Checklist

### CS Foundations — Security
| Rule | Status | Evidence |
|------|--------|----------|
...

### Clean Architecture (subset)
...

### Pragmatic Programmer (subset)
...

### Implementation Coding Core (subset)
...

## Findings

| # | Rule | Severity | Affected Files | Description | Remediation |
|---|------|----------|----------------|-------------|-------------|
| F001 | PP-DRY-1 | Critical | 35 files | 3 logging patterns, no canonical approach | Choose one, add config, migrate |
...

## Strengths
...
```
