# Using minion-factory with Claude Code

Guide for humans using `minion` through Claude Code (CLI or IDE).

## Setup

```bash
# Install minion
curl -sSL https://raw.githubusercontent.com/ai-janitor/minion-factory/main/scripts/install.sh | bash

# Verify
minion --version
```

## Core Workflows

### 1. Spawn a crew and watch them work

```bash
# List available crews
minion list-crews

# Spawn into tmux panes with live dashboard
minion spawn-party --crew ff7 --project-dir .

# Watch the dashboard (terminal)
minion dashboard

# Or in a browser
minion dashboard --web --port 8320
```

### 2. File work into the backlog

Tell Claude: "file a backlog item about X" or use the CLI directly:

```bash
minion backlog add --type <idea|bug|request|smell|debt> \
  --title "Short description" \
  --description "Details" \
  --priority <low|medium|high|critical>
```

### 3. Promote and execute a backlog item

Tell Claude: `/promote-exec-backlog 295`

This promotes a backlog item into the requirement pipeline, spawns a lead agent to decompose it into tasks, spawns workers, and drives through the DAG to completion.

Manual equivalent:

```bash
# Promote
minion backlog promote --agent napoleon --id 295 --flow requirement-lite

# Check status
minion req status --path features/my-requirement
minion sitrep
```

### 4. Monitor running agents

```bash
# Who's registered and what they're doing
minion sitrep

# Live task board (terminal TUI, auto-refreshes)
minion dashboard --watch

# Web dashboard (opens in browser)
minion dashboard --web --port 8320

# Check a specific agent's health
minion agent check-activity --agent tifa
```

### 5. Send messages between agents

```bash
# Local (same repo)
minion comms send local --from you --to tifa --message "focus on task 251"

# Check inbox
minion comms check-inbox --agent tifa
```

### 6. Stand down a crew

```bash
# Dismiss the lead (cascades to crew)
minion stand-down --agent cloud
```

## Slash Commands (Claude Code)

These are Claude Code custom commands. Install by copying from a configured machine's `~/.claude/commands/` or write your own.

| Command | What it does |
|---------|-------------|
| `/napoleon` | Backlog remediation coordinator — triages and drives items |
| `/promote-exec-backlog <id>` | Promote backlog item → spawn lead → execute through DAG |
| `/backlog` | File a new backlog item interactively |
| `/backlog-n-promote` | File + promote in one step |
| `/decompose-backlog` | Research and decompose a backlog item into tasks |
| `/web-dash` | Launch web dashboard on port 8320-8339 |
| `/ship` | Version, commit, build, and deploy |
| `/audit-manifesto` | Audit project against the manifesto |

## Key Concepts

### Flows (DAG lifecycles)

Every piece of work follows a DAG. No skipping stages.

```bash
# See available flows
minion flow list

# See stages for a flow
minion flow show requirement-lite
minion flow show bugfix
minion flow show chore
```

| Backlog type | Default flow |
|-------------|-------------|
| bug | bugfix |
| debt, smell | chore |
| idea, request, feature | requirement-lite |

### Agent Classes

Classes gate what commands an agent can run:

| Class | Role |
|-------|------|
| lead | Decomposes requirements, spawns workers, enforces DAG |
| coder | Writes code, runs tests |
| recon | Investigates, maps codebases, writes findings |
| oracle | Holds zone knowledge, answers questions |
| builder | Builds, tests, verifies |
| auditor | Reviews, audits, signs off |

### The `.work/` Directory

All runtime state lives in `.work/` inside your project:

```
.work/
├── minion.db          # SQLite — agents, messages, tasks
├── backlog/           # Backlog items (filesystem-as-db)
├── requirements/      # Promoted requirements
├── task-specs/        # Task specification files
├── protocols/         # Lead/worker execution protocols
├── intel/             # Scout findings
└── battle-plans/      # Session strategies
```

### Cross-Project Commands

Target a different project's DB from anywhere:

```bash
minion -C ~/projects/other-project sitrep
minion -C ~/projects/other-project dashboard --web
```

## Common Patterns

### "What's happening right now?"

```bash
minion sitrep
```

### "Something looks stuck"

```bash
# Check agent activity
minion agent check-activity --agent tifa

# Check task status
minion task list --status in_progress

# Read agent's last context
minion sitrep  # context_summary field
```

### "I want to work on this myself"

```bash
# Register yourself
minion agent register --name me --class coder --model human

# Claim files before editing
minion file claim --agent me --files src/foo.py

# Mark task done when finished
minion task done --id 251
```

### "Kill everything"

```bash
# Stand down all agents
minion stand-down --agent cloud  # lead cascades to crew

# Or deregister individually
minion agent deregister --name tifa
```

## Tips

- **`minion --help`** and **`minion <command> --help`** are your friends
- **Global flags go BEFORE the command**: `minion --json sitrep` not `minion sitrep --json`
- **`-C <dir>` targets a different project** without changing your cwd
- **`minion docs --output docs/`** regenerates the full CLI reference
- **Daemon agents need reinstall after code changes**: `uv tool install --force -e .`
