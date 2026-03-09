# AU-08: Prompts + Missions Deep Dive

## Purpose

Audit of the prompts system and missions system. Mostly content/template files (.md, .yaml) with thin Python loaders. Lower code complexity but important for correctness (prompt content drives agent behavior).

## Scope

| Directory/File | Description |
|----------------|-------------|
| `src/minion/prompts/__init__.py` | Package exports |
| `src/minion/prompts/*.py` | Python loader files (~5 files) |
| `src/minion/prompts/*.md` | Markdown prompt templates (~12 files) |
| `src/minion/missions/__init__.py` | Package exports |
| `src/minion/missions/*.py` | Python mission loaders |
| `missions/` | YAML mission templates (project root) |

Read ALL files in `src/minion/prompts/`, `src/minion/missions/`, and `missions/`.

**Note per UF-002:** IC-HDR rules apply only to .py files, not to .md or .yaml templates.

## Skills to Evaluate

### Implementation Coding Core (selected rules — .py files ONLY)
- **IC-HDR-1 through IC-HDR-5:** File headers on .py files only (not .md/.yaml per UF-002)
  - **How to check:** Read each .py file in prompts/ and missions/. Check for formal headers.
  - **Note:** Reference AU-00 systemic finding for Python files.

### Pragmatic Programmer (selected rules)
- **PP-DRY-1:** Single authoritative representation — are prompts defined once?
  - **How to check:** Check for duplicated prompt content across .md files. Check for hardcoded prompt text in .py loaders.
- **PP-DRY-2:** No inter-developer duplication — similar prompts have shared structure?
- **PP-ORTH-1:** Components self-contained — prompts/ and missions/ independent
- **PP-CRAFT-5:** Names reveal intent — prompt file names descriptive of content
- **PP-REQ-3:** Policy is metadata — are prompt templates parameterized or hardcoded?
  - **How to check:** Read .md templates. Do they use template variables? Or are they static text?

### Clean Architecture (selected rules)
- **CA-COMP-4:** Classes that change together in same component — missions load prompts, so they're grouped
- **CA-COMP-5:** Classes used together in same component
- **CA-SCRM-2:** File names communicate content — can you tell what each prompt is for from the filename?

## Audit Procedure

### Step 1: Prompt Template Survey
1. Read ALL .md files in `src/minion/prompts/`
2. Catalog each prompt: name, purpose, whether it uses template variables
3. Check: naming convention consistent?
4. Check: prompt content up-to-date with codebase capabilities?

### Step 2: Prompt Loader Analysis
1. Read ALL .py files in `src/minion/prompts/`
2. Check: how are prompts loaded? (file read? template rendering? f-string?)
3. Check: error handling on missing prompt file?
4. Check: are loaders thin (just load) or fat (logic embedded)?

### Step 3: Mission Template Survey
1. Read ALL .yaml files in `missions/`
2. Read ALL .py files in `src/minion/missions/`
3. Check: mission structure (what fields? what types?)
4. Check: do missions reference prompts? How?
5. Check: YAML schema validation on mission load?

### Step 4: Content-Code Boundary
1. Check: is prompt content cleanly separated from loading logic?
2. Check: can you change a prompt without changing Python code?
3. Check: can you add a mission without changing Python code?

### Step 5: Rule-by-Rule Evaluation

## Expected Findings from Research

1. **Mostly content files** — low Python code complexity.
2. **IC-HDR on .py files only** — per UF-002, markdown templates exempt.
3. **PP-DRY risk:** Potential prompt duplication across role files.
4. **PP-REQ-3:** Prompts should be parameterized, not hardcoded. Check template variable usage.
5. **No test coverage** — prompts and missions have zero behavioral tests. Note for AU-09 reference.
6. **CA-SCRM-2 likely PASS:** File names are typically descriptive for prompt/mission files.

## Output Format

```markdown
# AU-08 Prompts + Missions Audit Results

## Prompt Inventory
| File | Purpose | Template Variables? |
|------|---------|---------------------|
...

## Mission Inventory
| File | Purpose | References Prompts? |
|------|---------|---------------------|
...

## Filled Checklist

### Implementation Coding Core (.py files only)
| Rule | Status | Evidence |
|------|--------|----------|
...

### Pragmatic Programmer (subset)
...

### Clean Architecture (subset)
...

## Findings

| # | Rule | Severity | Affected Files | Description | Remediation |
|---|------|----------|----------------|-------------|-------------|
...

## Strengths
...
```
