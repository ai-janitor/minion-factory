# minion-factory

Unified multi-agent coordination framework. RPG raid party metaphor over SQLite.

Stateless CLI commands, no persistent server. All state lives in SQLite.

## Install

```bash
curl -sSL https://raw.githubusercontent.com/ai-janitor/minion-factory/main/scripts/install.sh | bash
```

Removes old packages (minion-comms, minion-swarm, minion-tasks), installs `minion` CLI via uv/pipx/pip cascade, and deploys shared daemon contracts to `~/.minion_work/docs/`.

## Quick Start

```bash
# Spawn a crew in your project directory
minion spawn-party --crew ff7 --project-dir .

# List available crews
minion list-crews

# Check party health
minion party-status

# Stand down (dismiss all agents)
minion stand-down --agent cloud
```

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    minion CLI                        │
│  register · send · create-task · spawn-party · ...  │
└──────────────┬──────────────────────┬───────────────┘
               │                      │
       ┌───────▼───────┐    ┌────────▼────────┐
       │   SQLite DB    │    │  Daemon Runner   │
       │  agents        │    │  poll/watcher    │
       │  messages      │    │  boot · HP · log │
       │  tasks         │    └────────┬────────┘
       │  file_claims   │             │
       │  battle_plan   │    ┌────────▼────────┐
       │  raid_log      │    │   Providers      │
       │  flags         │    │  claude · codex  │
       └───────────────┘    │  gemini · opencode│
                             └─────────────────┘
```

| Doc | What It Covers |
|-----|----------------|
| [Comms](docs/comms.md) | Messaging, inbox discipline, broadcasts, triggers |
| [Tasks & DAG](docs/tasks.md) | Task lifecycle, YAML flows, DAG-routed completion |
| [Providers](docs/providers.md) | Multi-model support, provider config, sandbox |
| [Crews](docs/crews.md) | Crew YAML, spawn lifecycle, stand-down, retire |
| [Daemon](docs/daemon.md) | Boot sequence, HP tracking, compaction, fenix-down |
| [Auth](docs/auth.md) | Agent classes, permissions, model whitelist |
| [CLI Reference](docs/cli-reference.md) | All 48 commands — usage, options, examples |

## Crews

| Crew | Lead | Agents | Providers |
|------|------|--------|-----------|
| ff1 | redmage | fighter, whitemage, blackmage, thief, redmage-jr, blackbelt, whitewizard | claude, codex, gemini |
| ff7 | cloud | tifa, cid, barret, aerith, redxiii, yuffie | claude, codex, gemini, haiku |

Crew files live in `crews/`. Create your own YAML to define custom parties.

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
| Daemon runner | `src/minion/daemon/` |
| Providers (model/runtime config) | `src/minion/providers/` |
| Task flows (YAML) | `task-flows/` |
| Shared contracts (JSON) | `docs/contracts/` |
| Tests | `tests/` |

## Running Tests

```bash
uv run pytest
```
