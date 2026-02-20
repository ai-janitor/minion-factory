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

## Missions — Capability-Driven Team Composition

Missions declare required capabilities. The resolver finds the minimum crew.

```bash
# List available missions
minion mission list

# See what slots a bugfix needs and who's eligible
minion mission suggest bugfix

# Filter to one crew's roster
minion mission suggest bugfix --crew idsoftware

# Spawn a party for a mission
minion mission spawn bugfix --crew idsoftware --party carmack,romero,hook
```

### Three-Layer Model

```
Mission   →  what you WILL do   (required capabilities)
Class     →  what you CAN do    (capabilities, permissions)
Character →  who you ARE         (system prompt, skills, personality)
```

### Mission Templates

| Mission | Requires | Min Slots |
|---------|----------|-----------|
| prototype | manage, code, build | lead + builder |
| dependency-upgrade | manage, code, test, build, review | lead + builder |
| code-audit | manage, review, investigate | lead + recon |
| security-review | manage, investigate, review | lead + recon |
| documentation | manage, investigate, review | lead + recon |
| bugfix | manage, investigate, code, test, review | lead + builder + recon |
| migration | manage, plan, code, test, build | lead + builder + planner |
| bd-research | manage, investigate, review, plan | lead + recon + planner |
| competitive-analysis | manage, investigate, plan | lead + recon + planner |
| incident-response | manage, investigate, code, test, build, review | lead + builder + recon |
| new-feature | manage, plan, code, test, build, review | lead + builder + recon + planner |

Mission templates live in `missions/`. Resolver: `src/minion/missions/resolver.py`.

### Cross-Project Spawning

Each project gets its own SQLite DB at `~/.minion_work/<project-name>/minion.db`. When spawning a mission targeting a different project, the daemons use that project's DB — but your CLI defaults to the current directory's DB.

**You must set `MINION_DB_PATH` to talk to daemons in another project:**

```bash
# Spawn scouts on a different project
minion mission spawn documentation --crew scouts \
  --party cartographer,viper,torvalds,blueprint,watchtower \
  --project-dir ~/projects/whisper-dictation-gpu

# Now point your CLI at that project's DB to send orders
export MINION_DB_PATH=~/.minion_work/whisper-dictation-gpu/minion.db
minion register --name commander --class lead --transport terminal
minion send --from commander --to all --message "GO"
```

Without `MINION_DB_PATH`, your messages go to the wrong DB and the daemons never see them.

## Crews

| Crew | Theme | Characters | Purpose |
|------|-------|------------|---------|
| ff1 | Final Fantasy I | redmage, fighter, whitemage, blackmage, thief, redwizard, blackbelt, whitewizard | General-purpose |
| ff7 | Final Fantasy VII | cloud, tifa, cid, barret, aerith, redxiii, yuffie | General-purpose |
| ateam | The A-Team | murdock, hannibal, face, ba, decker | General-purpose |
| idsoftware | id Software legends | carmack, abrash, romero, hook, cloud | GPU/compute specialist |
| scouts | Forward recon | cartographer, viper, pixel, blueprint, torvalds, watchtower | Codebase documentation |

### Specialist Crews

**idsoftware** — GPU debugging and optimization. Each persona primes MoE routing for domain-specific reasoning:

| Character | Class | Domain |
|-----------|-------|--------|
| carmack | lead | First-principles architecture, memory hierarchy, task decomposition |
| abrash | coder | GPU kernels, shader optimization, cycle-counting, profiling-first |
| romero | builder | Build toolchains, benchmarks, CI, cross-platform GPU detection |
| hook | recon | Driver forensics, vendor quirks, spec-vs-implementation gaps |
| cloud | auditor | Race conditions, memory models, numerical correctness, synchronization |

**scouts** — Forward recon party. Pure analysis, zero fixes. Documents a codebase for the team that follows:

| Character | Class | Domain | Writes to |
|-----------|-------|--------|-----------|
| cartographer | lead | Coordination, synthesis | `.minion-comms/CODE_MAP.md` |
| viper | recon | Python — imports, patterns, deps, testing | `.minion-comms/intel/python.md` |
| pixel | recon | TS/frontend — components, state, bundling | `.minion-comms/intel/frontend.md` |
| blueprint | recon | Architecture — boundaries, coupling, data flow | `.minion-comms/intel/architecture.md` |
| torvalds | recon | GPU/compute — kernels, hardware traps, drivers | `.minion-comms/intel/gpu-compute.md` |
| watchtower | recon | Infra — Docker, CI, deploy, config, secrets | `.minion-comms/intel/infrastructure.md` |

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
| Mission system | `src/minion/missions/` |
| Mission templates (YAML) | `missions/` |
| Task flows (YAML) | `task-flows/` |
| Shared contracts (JSON) | `docs/contracts/` |
| Tests | `tests/` |

## Running Tests

```bash
uv run pytest
```
