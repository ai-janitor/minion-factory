# Codebase Structure Survey

## File Counts (181 total .py files under src/minion/)

| Package | Files | Notes |
|---|---|---|
| tasks/ | 25 | Largest — DAG, gates, CRUD, engine, rollup |
| cli/ | 21 | One file per command group |
| intel/ | 13 | Knowledge layer |
| (root) | 13 | auth, defaults, fs, output, lifecycle, etc. |
| prompts/ | 11+ | Builders + roles/ and capabilities/ .md files |
| network/ | 11+9 handlers | Server, client, router, auth, db_schema |
| daemon/runner/ | 11 | Mixin pattern: _execution, _polling, _hp, etc. |
| backlog/ | 10 | CRUD + promote, lineage, reindex |
| crew/ | 9 | spawn, recruit, lifecycle, config, logs, tmux |
| db/ | 8 | connection, schema, migrations, agents, messages |
| daemon/ (top) | 7 | config, buffer, contracts, watcher, triggers |
| requirements/ | 6 | crud, decompose, findings, itemize, report |
| providers/ | 6 | Registry + 4 providers |
| comms/ | 6 | inbox, send, register, routing, delivery |
| missions/ | 5 | loader, resolver, party, spawn |
| dashboard/ | 4 | loop, queries, render |
| api/ | 4 | daemon, runner, remotes |

## Dependency Flow

- **Foundation (imported by nearly everything):** db (90 cross-pkg imports), auth (45), defaults (14), fs (10)
- **Mid-tier:** tasks→db/intel/crew, comms→db/fs/network/crew, crew→db/auth/comms/daemon/defaults/prompts
- **Leaf/consumer:** cli fans out to everything (29 packages), daemon is self-contained, network is fully internal
- **Direction is clean:** db/defaults at bottom, cli at top, no circular imports (auth→tasks lazy import handles the one potential cycle)

## Comment Headers

- **No formal PURPOSE/RESPONSIBILITIES headers.** Zero matches.
- **Module-level docstrings instead:** 153 of 161 non-init files (95%) have docstrings
- **Section dividers:** Pervasive `# -----------` blocks
- **PSEUDO comments:** 152 occurrences across 16 files (scaffold-only files)
- **8 files with NO docstring:** providers/cli_provider_protocol.py, providers/claude.py, codex.py, gemini.py, opencode.py, crew/config.py, daemon/buffer.py, daemon/watcher.py

## Naming Conventions

**Strengths:**
- Package names are descriptive (backlog, comms, crew, daemon, intel, missions, etc.)
- Some excellent file names: backlog/path_resolution_and_slug.py, db/timestamp_and_agent_registry.py, tasks/flow_gates_and_validation.py

**Weaknesses:**
- Generic names: db.py (inside tasks/), config.py (in crew/ and daemon/), loader.py (in tasks/ and missions/), crud.py (in requirements/), fs.py (root)
- daemon/runner/ uses terse underscore-prefixed mixins

## Pattern Registry

**None exists.** No formal document declaring one pattern per concern. De facto patterns observed but undocumented.
