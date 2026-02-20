# minion-factory

Unified multi-agent coordination framework. RPG raid party metaphor over SQLite.

## Install

```bash
uv tool uninstall minion-comms 2>/dev/null; uv tool install git+https://github.com/ai-janitor/minion-factory.git
```

## Agent Bootstrap

Read `AGENTS.md` for the universal agent playbook (boot sequence, classes, HP, hard blocks, crew lifecycle). Everything there applies regardless of runtime.

## Dev Reference

| What | Where |
|------|-------|
| CLI entry point | `src/minion/cli.py` |
| Auth model (class → commands) | `src/minion/auth.py` |
| DB schema (all tables) | `src/minion/db.py` |
| Comms (send, check-inbox, set-context) | `src/minion/comms.py` |
| Crew lifecycle (spawn, stand-down, retire) | `src/minion/crew/` |
| HP + monitoring | `src/minion/monitoring.py` |
| Task management | `src/minion/tasks/` |
| File claims | `src/minion/filesafety.py` |
| War room (battle plans, raid log) | `src/minion/warroom.py` |
| Trigger words | `src/minion/triggers.py` |
| Agent lifecycle (cold-start, fenix-down) | `src/minion/lifecycle.py` |
| Daemon transport | `src/minion/daemon/` |
| Providers (model/runtime config) | `src/minion/providers/` |
| Mission system (resolver, loader, party) | `src/minion/missions/` |
| Mission templates (YAML) | `missions/` |
| Daemon polling | `src/minion/polling.py` |
| Filesystem helpers | `src/minion/fs.py` |
| Shared path defaults | `src/minion/defaults.py` |
| Tests | `tests/` |

## CLI Gotchas

- **`--human`/`--compact`/`-C` are global flags** — go BEFORE the command, not after
- **`-C <dir>` / `--project-dir <dir>`** — target a different project's DB from any directory
- **`MINION_CLASS` env var** gates auth per `auth.py`
- All commands are stateless — no persistent server connection

## Project-Local `.work/` Directory

All runtime data lives in `.work/` inside the project repo:

```
<project>/
└── .work/
    ├── minion.db          # SQLite — agents, messages, tasks, claims
    ├── inbox/             # message files per agent
    ├── battle-plans/      # session strategy files
    ├── raid-log/          # session log entries
    ├── intel/             # scout findings (filesystem-as-db)
    │   ├── lang/          # per-language: python.md, cpp.md
    │   ├── domain/        # per-domain: gpu-compute.md, auth.md
    │   ├── arch/          # architecture: dependency-graph.md
    │   └── infra/         # ops: ci-cd.md, docker.md
    ├── traps/             # issues found (one file per trap)
    │   ├── silent-fail/   # errors swallowed
    │   ├── build/         # build system issues
    │   ├── perf/          # performance traps
    │   ├── security/      # security issues
    │   └── correctness/   # logic bugs
    ├── patterns/          # good patterns worth replicating
    ├── CODE_MAP.md        # master codebase map
    └── CODE_OWNERS.md     # ownership map
```

### Cross-Project Commands

Use `-C` to manage agents in a different project from any directory:

```bash
# Spawn scouts on another project
minion -C ~/projects/other-project spawn-party --crew scouts --agents torvalds,viper

# Send orders from anywhere
minion -C ~/projects/other-project send --from commander --to torvalds --message "analyze C++ code"
```

### System Prompt Injection

Crew YAMLs support `system_prefix:` — a crew-level field prepended to every agent's system prompt at spawn time. Use for scanning rules, output conventions, and behavioral directives.

Claude provider passes system prompts via `--append-system-prompt` (system-level), not `-p` (user-level). This makes directives authoritative.

**Prompting pattern:** Use positive instructions ("ONLY scan src/") not negation ("NEVER scan .venv/"). LLMs ignore negative instructions even at system prompt level.

## Running Tests

```bash
uv run pytest
```
