# AU-07: Intel + Providers Deep Dive

## Purpose

Line-by-line audit of the intel (knowledge) system and provider abstraction layer. Both are mid-tier packages with clean-architecture focus: intel manages documents/knowledge, providers abstract AI model access.

## Scope

| Directory/File | Description |
|----------------|-------------|
| `src/minion/intel/__init__.py` | Package exports |
| `src/minion/intel/read_doc.py` | Document reading |
| `src/minion/intel/war_plan.py` | War plan generation |
| `src/minion/intel/registry.py` | Document registry |
| `src/minion/intel/search.py` | Document search (if exists) |
| Plus all other files in `src/minion/intel/` (11 files total) |
| `src/minion/providers/__init__.py` | Package exports |
| `src/minion/providers/base.py` | Provider base/protocol (if exists) |
| `src/minion/providers/claude.py` | Claude provider |
| `src/minion/providers/codex.py` | Codex provider |
| `src/minion/providers/gemini.py` | Gemini provider |
| `src/minion/providers/opencode.py` | OpenCode provider (if exists) |

Read ALL files in `src/minion/intel/` and `src/minion/providers/`.

## Skills to Evaluate

### Clean Architecture (PRIMARY — selected rules)
- **CA-DEP-1:** Dependencies inward — intel/ and providers/ should depend on entities/core, not on cli/ or daemon/
  - **How to check:** `grep -r "from minion" src/minion/intel/` and same for providers/. Map all imports.
- **CA-DEP-5:** Dependency Inversion — provider protocol pattern
  - **How to check:** Check if providers implement a common protocol/interface. Is there a base class or Protocol?
- **CA-SOLID-1:** SRP — each module has one reason to change
- **CA-SOLID-3:** LSP — provider implementations interchangeable via interface
  - **How to check:** Read each provider. Do they all implement the same method signatures? Can you swap one for another?
- **CA-SOLID-5:** DIP — high-level policy depends on abstractions
  - **How to check:** Do callers of providers depend on the abstraction (Protocol/base) or on concrete providers?
- **CA-COMP-1:** No cycles in dependency graph
- **CA-COMP-4, CA-COMP-5:** Grouping coherence
- **CA-BOUND-3:** Data crossing boundaries — what shapes do providers return?

### Pragmatic Programmer (selected rules)
- **PP-ORTH-1:** Components self-contained — each provider independent, intel independent
- **PP-ORTH-3:** Change to one provider doesn't ripple to others
- **PP-DRY-1:** Single authoritative representation — no duplicated logic across providers
  - **How to check:** Compare the 4 provider files. Is there common logic that should be in base?
- **PP-DRY-2:** No inter-developer duplication — provider implementations follow same structure
- **PP-DECOUPLE-4:** Prefer interfaces over inheritance — protocol pattern preferred
- **PP-CRAFT-5:** Names reveal intent

### Implementation Coding Core (selected rules)
- **IC-HDR-1 through IC-HDR-5:** Reference AU-00 systemic finding
- **IC-SCALE-3:** intel/read_doc.py — does it limit file size? Unbounded reads?
  - **How to check:** Read read_doc.py. Does it stream or load entire file? Any size limits?

## Audit Procedure

### Step 1: Intel Package Analysis
1. Read ALL files in `src/minion/intel/`
2. Map: what knowledge does intel manage? (documents, war plans, search)
3. Check: document lifecycle (register, read, update, delete?)
4. Check: read_doc.py — file size limits? Streaming? Error handling on missing files?
5. Check: war_plan.py — what is it? How complex? Dependencies?

### Step 2: Provider Protocol Analysis
1. Read `src/minion/providers/__init__.py` — check for Protocol or base class definition
2. Read each provider (claude.py, codex.py, gemini.py, opencode.py if exists)
3. Map the provider interface: what methods must each provider implement?
4. Check: is there a formal Protocol/ABC, or is it informal (duck typing)?
5. Check: do all providers implement the same interface completely?

### Step 3: Provider Implementation Comparison
1. Compare provider implementations side-by-side
2. Check for DRY violations: common code copy-pasted across providers
3. Check: subprocess call patterns — consistent or varied?
4. Check: error handling — consistent across providers?
5. Check: return types — same shapes from all providers?

### Step 4: Dependency Direction Check
1. For both packages, verify import direction
2. Intel should import from core/entities, not from cli/ or daemon/
3. Providers should implement a protocol from core, not depend on callers
4. Check: who calls intel? Who calls providers? Is it through abstractions?

### Step 5: Rule-by-Rule Evaluation

## Expected Findings from Research

1. **Provider protocol pattern** — likely good CA-SOLID focus. Check if formally declared.
2. **No test coverage** — both intel and providers have zero behavioral tests. Note for AU-09 reference.
3. **intel/read_doc.py** — may have unbounded file reads (IC-SCALE-3 risk).
4. **Provider DRY** — common subprocess patterns may be duplicated across provider files.
5. **IC-HDR FAIL:** Systemic (reference AU-00).
6. **PP-ORTH likely PASS:** Each provider is independent, intel is independent.
7. **CA-SOLID-3 (LSP):** Verify providers are truly interchangeable.

## Output Format

```markdown
# AU-07 Intel + Providers Audit Results

## Intel Architecture
[Knowledge management model, document lifecycle]

## Provider Interface
[Protocol/interface, method signatures, implementation comparison]

## Filled Checklist

### Clean Architecture
| Rule | Status | Evidence |
|------|--------|----------|
| DEP-1 | YES/NO/N/A | [specific evidence] |
...

### Pragmatic Programmer (subset)
...

### Implementation Coding Core (subset)
...

## Findings

| # | Rule | Severity | Affected Files | Description | Remediation |
|---|------|----------|----------------|-------------|-------------|
...

## Strengths
...
```
