# SU-15: CLI Consistency — Verbs, Exit Codes, Short Flags, Command Groups

**Wave:** 5 (parallel within wave)
**Requirements:** 4.3
**Dependencies:** None
**Dependents:** None

---

## Purpose

Four CLI surface consistency fixes: standardize verb vocabulary, standardize exit codes, add short flags to high-frequency options, and move leaked top-level commands into proper groups.

## Requirements Traceability

- **4.3 (CLI Consistency):** "Verb vocabulary inconsistencies, exit code inconsistency, ~244 of 250 options lack short flags, top-level command leaks."

## Dependencies

None.

## Behavior

### 4.3.1 — Verb Vocabulary Standardization

**Target verb inventory:**

| Action | Standard Verb | Currently Used Alternatives |
|--------|--------------|---------------------------|
| Create a new entity | `create` | `add`, `define`, `register` |
| Read/show an entity | `get` | `show`, `list`, `view` |
| List multiple entities | `list` | `ls`, `show-all` |
| Update an entity | `update` | `set`, `edit`, `modify` |
| Delete an entity | `close` / `remove` | `delete`, `deregister`, `stand-down` |
| Move through workflow | `complete-phase` | `advance`, `transition` |

**Rules:**
- `create` for new entities, `register` for agent registration specifically (domain term)
- `list` for collections, `get` for single entity by ID
- Keep domain verbs where they add clarity (e.g., `promote` for backlog, `spawn` for agents)
- CLAUDE.md and help text must be updated for any renamed commands
- Old command names should be kept as hidden aliases for backward compatibility during transition

### 4.3.2 — Exit Code Standardization

**Convention:**
| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error (operation failed) |
| 2 | Usage error (bad arguments, missing required params) |
| 3 | Stand-down/retire signal (poll-specific) |

**Current state:** Mix of 0/1/3 conventions. Need to audit all `sys.exit()` and Click `ctx.exit()` calls.

**Target:** Every CLI command exits with the correct code per this convention. Click's built-in UsageError already uses code 2.

### 4.3.3 — Short Flags for High-Frequency Options

**Priority options (used in nearly every session):**

| Long Flag | Short Flag | Command(s) |
|-----------|-----------|------------|
| `--agent` | `-a` | Most commands |
| `--message` | `-m` | comms send |
| `--from` | `-f` | comms send |
| `--to` | `-t` | comms send |
| `--status` | `-s` | task update, task list |
| `--name` | `-n` | agent register |
| `--class` | `-c` | agent register |
| `--reason` | `-r` | task block, complete-phase |
| `--file` | `-F` | claim-file |
| `--context` | `-x` | set-context |
| `--hp` | (already short) | set-context |

**Rules:**
- Only add short flags to options used frequently (>5 times per session estimated)
- Don't add short flags that conflict with global flags (`-C` is taken for project-dir)
- Click supports both: `@click.option("--agent", "-a")`

### 4.3.4 — Top-Level Command Leak Cleanup

**Current leaks:** `deregister`, `rename`, `interrupt`, `resume` are exposed at the CLI root level instead of under proper command groups.

**Target moves:**

| Command | From | To |
|---------|------|----|
| `deregister` | root | `agent deregister` |
| `rename` | root | `agent rename` |
| `interrupt` | root | `agent interrupt` |
| `resume` | root | `agent resume` |

**Backward compatibility:** Keep root-level commands as hidden aliases that delegate to the grouped version. Print deprecation warning on use.

## Constraints

- CLAUDE.md must be updated for any command name/location changes
- All existing workflows must continue working (aliases preserve backward compat)
- Short flags must not conflict with each other within the same command
- Exit codes are a contract — changing them may affect scripts that check exit codes

## Edge Cases

1. **Scripts depending on old command names:** The hidden alias pattern preserves backward compatibility. Aliases should be removed in v3.
2. **Short flag conflicts:** `-c` for `--class` may conflict with `-c` for `--compact`. Check per command — flags are scoped to their command, not global (except global flags like `-C`).
3. **Verb rename breaking muscle memory:** Keep old verbs as aliases. Don't force immediate migration.
4. **Exit code 3 for poll:** Poll uses exit code 3 for stand_down/retire signals. This is a documented contract for minion-swarm. Preserve it.

## Current State

- ~244 of 250 options lack short flags
- Some commands are at root that should be in groups
- Exit codes inconsistent
- Verb vocabulary not audited

## Test Contract

- **Test 1:** `minion agent deregister --help` works (command moved to group).
- **Test 2:** `minion deregister --help` still works (backward-compat alias) with deprecation warning.
- **Test 3:** `minion comms send -f sys-lead -t coder -m "test"` works (short flags).
- **Test 4:** CLI exit code audit: every command exits 0 on success, 1 on error, 2 on usage error.
