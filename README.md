# minion-factory

Unified multi-agent coordination framework. RPG raid party metaphor over SQLite.

## Install

```bash
# Remove old packages if present
uv tool uninstall minion-comms 2>/dev/null
pipx uninstall minion-comms 2>/dev/null
pipx uninstall minion-swarm 2>/dev/null
pipx uninstall minion-tasks 2>/dev/null

# Install minion-factory (replaces all of the above)
uv tool install git+https://github.com/ai-janitor/minion-factory.git

# Copy contract docs + protocol files to ~/.minion_work/docs/
minion install-docs
```

Installs the `minion` CLI globally. `install-docs` copies shared daemon contracts (boot sequence, rules, inbox templates, config defaults, state schema, compaction markers) so both Python and TS daemons read from the same source of truth.

## Quick Start

```bash
minion spawn-party --crew ff1 --project-dir .
```
