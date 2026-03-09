# Research Findings Summary — v1

Key takeaways that affect decomposition and audit approach.

## Critical Finding: Network API is NOT FastAPI

The raw requirements assumed FastAPI for `src/minion/network/`. It's actually stdlib `http.server`. This means:
- **fast-api skill (24 rules):** Mostly N/A — no hexagonal architecture, no DI, no Pydantic, no middleware
- **ai-first-api skill (37 rules):** Partially applicable — routing patterns, health endpoint, docs exist conceptually but implementation is manual
- The audit should evaluate the network API against ai-first-api for what SHOULD be there, and note fast-api as a potential migration path, not a current-state checklist

## Critical Finding: 17 Packages Have Zero Behavioral Tests

Only 10 of 27 packages have behavioral test coverage. 224 test functions exist but are concentrated in backlog, requirements, and tasks. Major gaps: auth, providers, intel, prompts, missions, daemon (beyond contracts), lifecycle, monitoring, output.

## Major Finding: Logging Has No Strategy

Three competing patterns (logging.getLogger: 3 files, print: 23 files, click.echo: 9 files). No centralized config, no log levels, no structured output except one line in server.py. This is the weakest cross-cutting concern.

## Major Finding: Error Handling Has Two Patterns

Dict-return {"error": ...} for CLI/tasks, raise ValueError/FileNotFoundError for config/loaders. No domain exception hierarchy. No custom Exception subclasses. The dict-return pattern works but is fragile — callers must remember to check for "error" key.

## Major Finding: No Formal Comment Headers

CLAUDE.md mandates PURPOSE/RESPONSIBILITIES/NOT RESPONSIBLE FOR/DEPENDENCIES headers. The codebase uses module-level docstrings instead (95% coverage). This is a convention mismatch — the codebase has good documentation but not in the mandated format.

## Moderate Finding: Config Loading Duplicated

crew/config.py (canonical) and daemon/config.py duplicate YAML parsing logic. daemon imports the dataclasses but re-implements all parsing.

## Moderate Finding: No Pattern Registry

No document declares the one chosen pattern per cross-cutting concern. De facto patterns exist but are undocumented. Agents have no reference to follow.

## Strengths (Preserve These)

1. **Clean dependency graph** — db at bottom, cli at top, no circular imports
2. **JSON-default CLI output** — correct for agent consumption, output.py single funnel
3. **Non-interactive CLI** — zero prompts, fully agent-safe
4. **Descriptive package names** — filesystem-as-db mostly followed
5. **95% docstring coverage** — not the mandated format but documentation exists
6. **Auth model is well-designed** — two tiers (local class+scope, network bearer) is intentional
7. **Database pattern is consistent** — get_db(), WAL, Row factory everywhere
8. **Migration system works** — versioned v1-v13, idempotent, transactional

## Impact on Decomposition

1. **Reduce skills to audit:** fast-api is mostly N/A. Focus ai-first-api on aspirational gaps.
2. **Test coverage gap drives priority:** 17 untested packages = high-priority TDD findings
3. **Cross-cutting concerns are the biggest findings:** logging > error handling > config duplication
4. **Comment header convention mismatch** will generate many IC-HDR findings but they're all the same finding repeated — report once, not per-file
