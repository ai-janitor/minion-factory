# AU-01: CLI Layer Deep Dive

## Purpose

Line-by-line audit of the CLI layer against applicable skill checklists. The CLI is the primary interface — consumed by AI agents, not humans.

## Scope

| Directory/File | Description | File Count |
|----------------|-------------|------------|
| `src/minion/cli/` | All CLI command modules | 17 files |
| `src/minion/output.py` | Output formatting (JSON/text funnel) | 1 file |
| `src/minion/main.py` | Entry point (if exists) | 1 file |
| `src/minion/cli/__init__.py` | CLI group registration | 1 file |

**Files to read (exhaustive):**
- `src/minion/cli/__init__.py`
- `src/minion/cli/agent.py`
- `src/minion/cli/backlog.py`
- `src/minion/cli/comms.py`
- `src/minion/cli/crew.py`
- `src/minion/cli/daemon.py`
- `src/minion/cli/dash.py`
- `src/minion/cli/intel.py`
- `src/minion/cli/lifecycle.py`
- `src/minion/cli/mission.py`
- `src/minion/cli/network.py`
- `src/minion/cli/poll.py`
- `src/minion/cli/requirements.py`
- `src/minion/cli/sitrep.py`
- `src/minion/cli/task.py`
- `src/minion/cli/who.py`
- `src/minion/cli/triggers.py`
- `src/minion/output.py`
- Check for `src/minion/__main__.py` or `src/minion/main.py`
- Check `setup.py` or `pyproject.toml` for entry_points console_scripts

## Skills to Evaluate

### AI-First CLI (all 19 rules — PRIMARY)

#### Command Hierarchy (CMD)
- **CMD-1:** Verb-noun structure (mycli get users, not mycli users)
  - **How to check:** Read each command module. Map the command tree. Is it `minion get agent` (verb-noun) or `minion agent register` (noun-verb)?
  - **Known finding from research:** minion uses noun-verb (minion agent register). This is a FAIL against the skill but may be intentional (kubectl-style). Note as finding with rationale.
- **CMD-2:** Max 2 subcommand levels
  - **How to check:** Map the full command tree from cli/__init__.py. Count nesting depth.
- **CMD-3:** Both long and short flags (--output / -o)
  - **How to check:** Grep for `@click.option` in all CLI files. Check each option for both long and short forms.
- **CMD-4:** Consistent verb vocabulary across all commands
  - **How to check:** List all command names. Check for synonyms (create vs add, delete vs remove, list vs show).

#### Output Formatting (OUT)
- **OUT-1:** Human-readable table/text by default
  - **Known finding:** JSON is default output, not human. This is INVERTED from the skill expectation. Check output.py for the default behavior.
- **OUT-2:** --json flag returns valid JSON
  - **How to check:** Check if --json flag exists OR if JSON is always default. Verify JSON validity.
- **OUT-3:** --quiet flag returns pipe-friendly output
  - **How to check:** Grep for `--quiet` or `-q` flag across CLI files.
- **OUT-4:** All three modes return the same underlying data
  - **How to check:** Read output.py. Check if format modes share the same data structure.

#### Progressive Disclosure (DISC)
- **DISC-1:** --help works at every level
  - **How to check:** Click provides this by default. Verify group and subcommand help text exists.
- **DISC-2:** Error messages include actionable hints
  - **How to check:** Grep for error/exception handling in CLI files. Check error message content.
- **DISC-3:** Unknown command suggests closest match
  - **How to check:** Check Click configuration for fuzzy matching or Did You Mean plugin.

#### Configuration Cascade (CFG)
- **CFG-1:** Precedence: flags > env > project config > user config > defaults
  - **How to check:** Read defaults.py and CLI option definitions. Map the precedence chain.
- **CFG-2:** Environment variables use consistent prefix (MINION_*)
  - **How to check:** Grep for os.environ in CLI files and defaults.py. Check prefix consistency.
- **CFG-3:** Config file locations documented in --help
  - **How to check:** Read --help output at root level.

#### Agent Integration (AGENT)
- **AGENT-1:** No interactive prompts (works without TTY)
  - **Known finding:** CLI is fully non-interactive. This should PASS.
- **AGENT-2:** Agent rules file generated or generatable
  - **How to check:** Check for rules file generation capability.
- **AGENT-3:** Deterministic output (same input = same output)
  - **How to check:** Review command implementations for non-deterministic elements.
- **AGENT-4:** Exit codes are meaningful (0=success, 1=error, 2=usage)
  - **Known finding:** Only 0/1 implemented, no 2=usage. Check output.py and error handling.
- **AGENT-5:** Shell completions available
  - **How to check:** Check for Click shell completion setup.

### Pragmatic Programmer (selected rules)
- **PP-CRAFT-5:** Names reveal intent — check command and option names
- **PP-DECOUPLE-1:** No train wrecks — check method chaining in CLI handlers
- **PP-DECOUPLE-5:** Configuration externalized — check for hardcoded values in CLI
- **PP-CONTRACT-2:** Crash early — check error handling (sys.exit vs silent failure)
- **PP-DRY-1:** Single authoritative representation — check for duplicated logic between CLI commands
- **PP-DRY-2:** No inter-developer duplication — check for similar patterns in different command files
- **PP-ORTH-1:** Components self-contained — each CLI module is independent

### Clean Architecture (selected rules)
- **CA-SCRM-1:** Top-level directories communicate use cases — cli/ subdirectory naming
- **CA-SCRM-2:** Stranger understands domain from tree — cli/ file names descriptive
- **CA-COMP-4:** Classes that change together in same component — CLI commands grouped logically
- **CA-COMP-5:** Classes used together in same component

### Implementation Coding Core (selected rules)
- **IC-HDR-1 through IC-HDR-5:** File headers — check all 17+ CLI files for PURPOSE/RESPONSIBILITIES/NOT RESPONSIBLE FOR/DEPENDENCIES headers
  - **Known finding:** Codebase uses docstrings, not formal headers. Reference AU-00 systemic finding. Note domain-specific details only.
- **IC-VER-1 through IC-VER-4:** Verification — does the CLI build/test/import correctly

## Audit Procedure

### Step 1: Map the Command Tree
1. Read `src/minion/cli/__init__.py` — extract all registered command groups
2. Read each command module — extract all commands and their options
3. Produce a command tree showing: group > command > options/flags
4. Check for top-level command leaks (commands registered on root that should be in groups)

### Step 2: Output Format Analysis
1. Read `src/minion/output.py` in full — understand the output funnel
2. Check: is JSON default? Is human-readable available? Is --quiet supported?
3. For each command, trace the output path: command handler -> output.py -> stdout

### Step 3: Error Handling Walk
1. For each CLI module, check error handling patterns
2. Check: exit codes, error message quality, actionable hints
3. Check: does output.py handle the "error" key in dict-return pattern?

### Step 4: Configuration Check
1. Read `src/minion/defaults.py` — the canonical config source
2. In each CLI file, grep for `os.environ` direct reads (bypassing defaults.py)
3. Map: which configs come from flags, which from env, which from defaults

### Step 5: Rule-by-Rule Evaluation
For each rule in the skills above, evaluate YES/NO/N/A with specific evidence.

## Expected Findings from Research

1. **CMD-1 FAIL:** noun-verb pattern (minion agent register), not verb-noun
2. **OUT-1 FAIL:** JSON is default output (inverted — correct for agents but violates skill letter)
3. **OUT-2 PASS or N/A:** JSON is already default, --json flag may not exist separately
4. **OUT-3 likely FAIL:** --quiet flag probably missing
5. **AGENT-4 FAIL:** Exit codes only 0/1, no 2=usage error
6. **Top-level command leaks:** deregister, rename, interrupt may be registered on root (not under agent group)
7. **IC-HDR-* FAIL:** Systemic — no formal headers (reference AU-00)
8. **PP-DECOUPLE-5 partial:** Some CLI files read os.environ directly instead of through defaults.py

## Output Format

```markdown
# AU-01 CLI Layer Audit Results

## Filled Checklist

### AI-First CLI
| Rule | Status | Evidence |
|------|--------|----------|
| CMD-1 | YES/NO/N/A | [specific evidence] |
...

### Pragmatic Programmer (CLI-applicable subset)
| Rule | Status | Evidence |
|------|--------|----------|
...

### Clean Architecture (CLI-applicable subset)
...

### Implementation Coding Core (CLI-applicable subset)
...

## Findings

| # | Rule | Severity | Affected Files | Description | Remediation |
|---|------|----------|----------------|-------------|-------------|
| F001 | CMD-1 | Minor | All cli/*.py | noun-verb not verb-noun | Document as intentional OR migrate |
...

## Strengths
- [patterns the CLI gets right — preserve these]
```
