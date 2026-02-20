# minion-factory

Unified multi-agent coordination framework. RPG raid party metaphor over SQLite.

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

## Crews

| Crew | Lead | Agents | Description |
|------|------|--------|-------------|
| ff1 | redmage | fighter, whitemage, blackmage, thief, redmage-jr, blackbelt, whitewizard | Classic party — 7 daemons, mixed providers |
| ff7 | cloud | tifa, cid, barret, aerith, redxiii, yuffie | Midgar party — claude, codex, gemini, haiku |

Crew files live in `crews/`. Create your own YAML to define custom parties.
