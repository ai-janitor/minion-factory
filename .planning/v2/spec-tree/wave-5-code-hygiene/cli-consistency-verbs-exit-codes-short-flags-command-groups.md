# SU-15: CLI Consistency — Verbs, Exit Codes, Short Flags, Command Groups

**Wave:** 5 (parallel within wave)
**Requirements:** 4.3
**Dependencies:** None
**Dependents:** None

## Domain Preamble

CLI surface has four consistency issues: verb vocabulary inconsistencies across command groups, exit code inconsistency (mix of 0/1/3 conventions), ~244 of 250 CLI options lack short flags, and top-level command leaks (deregister, rename, interrupt, resume exposed at root instead of proper command groups). All are CLI surface polish touching the same cli/ files. Splitting would create merge conflicts.

## Scope

- Audit and standardize verb vocabulary across command groups
- Standardize exit codes: 0=success, 1=error, 2=usage
- Add short flags to high-frequency CLI options
- Move top-level command leaks into proper command groups

## Affected Files

- `src/minion/cli/*.py`

## Boundary Edges

- B-02 (internal): CLI command names ↔ help text (renamed commands must update all references)
