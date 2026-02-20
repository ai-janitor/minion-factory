# minion-factory

Unified multi-agent coordination framework. RPG raid party metaphor over SQLite.

## Install

```bash
# Replaces minion-comms — uninstall first if present
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

- **`--human`/`--compact` are global flags** — go BEFORE the command, not after
- **`MINION_CLASS` env var** gates auth per `auth.py`
- All commands are stateless — no persistent server connection

## Per-Project DB

Every project gets its own SQLite DB: `~/.minion_work/<project-name>/minion.db`. The CLI resolves `<project-name>` from `$PWD`.

**When spawning daemons targeting a different project**, the daemons use that project's DB but your CLI still uses the current directory's DB. Messages go to the wrong DB and daemons never see them.

**Fix:** set `MINION_DB_PATH` before sending commands:

```bash
# Spawn to a different project
minion mission spawn bugfix --crew idsoftware --party carmack,romero,hook \
  --project-dir ~/projects/other-project

# Point CLI at that project's DB
export MINION_DB_PATH=~/.minion_work/other-project/minion.db
minion register --name lead --class lead --transport terminal
minion send --from lead --to all --message "GO"
```

Without this, `register`/`send`/`who` hit the wrong DB and daemons poll forever seeing nothing.

## Running Tests

```bash
uv run pytest
```
