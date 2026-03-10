# Research: Tools and Skills Survey

## Skills Checked
- `~/.skills/` contains 241 skills. Relevant ones for minion-factory remediation:

### Directly Applicable
- **pragmatic-programmer** — Referenced in DAG.md stage gate cross-references. PP-CRAFT, PP-CONTRACT, PP-DRY, PP-ORTH rules apply.
- **clean-architecture** — CA-COMP, CA-BOUND, CA-DEP rules in DAG.md cross-references.
- **implementation-coding-core** — IC-LAY, IC-HDR, IC-SCALE, IC-DATA rules for scaffolding/implementation.
- **test-driven-development** — TDD-CYC, TDD-COV, TDD-QUAL rules for test coverage work.
- **cs-foundations** — CS-SEP, CS-DATA, CS-COMM, CS-CONSIST, CS-SCALE, CS-SEC, CS-ERR rules for decomposition.
- **ai-first-cli** — Applicable to CLI consistency work (WS4.3).
- **ai-first-api** — Applicable to network API evolution (WS5.1).
- **architecture-decision-records** — For documenting pattern registry decisions (WS2.9).
- **agent-delegation** — For cross-project coordination patterns (WS5.2).

### Partially Applicable
- **atomic-skill-packaging** — Naming conventions may inform filesystem-as-db compliance.
- **agent-safety** — Relevant to auth scope narrowing (WS5.4).

## Existing Codebase Patterns

### Established Conventions (preserve)
1. **Comment headers** — Purpose/Rationale/Responsibility/Organization on every file
2. **Dict-return at CLI boundary** — Functions return `{"error": "..."}` or `{"status": "..."}` for JSON output
3. **Exception hierarchy** — MinionError base with typed subclasses (exceptions.py)
4. **WAL-mode connections** — All DB access through connection.py connect() function
5. **Filesystem-as-DB naming** — Descriptive file/folder names (mostly followed)
6. **Trigger word detection** — scan_triggers() on message send
7. **Staleness checking** — Per-class staleness thresholds in defaults.py
8. **Scope-based auth** — Class + scope for permission narrowing

### Patterns Needing Documentation (WS2.9 pattern registry)
1. Error handling convention (raise vs return dict)
2. DB access pattern (get_db() + cursor + try/finally conn.close())
3. Config resolution (defaults.py resolvers)
4. Logging setup (logging_setup.py)
5. Auth decoration (require_class + require_scope)
6. Message delivery pattern (filesystem content + DB metadata)
