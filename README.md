# minion-factory

Unified multi-agent coordination framework. RPG raid party metaphor over SQLite.

## Install

```bash
curl -sSL https://raw.githubusercontent.com/ai-janitor/minion-factory/main/scripts/install.sh | bash
```

Removes old packages (minion-comms, minion-swarm, minion-tasks), installs `minion` CLI via uv/pipx/pip cascade, and deploys shared daemon contracts to `~/.minion_work/docs/`.

## Quick Start

```bash
minion spawn-party --crew ff1 --project-dir .
```
