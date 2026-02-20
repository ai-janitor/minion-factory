# Auth — Agent Classes & Permissions

Every agent has a class that determines what commands they can run.

## Classes

| Class | Purpose | Can Create Tasks | Context Timeout |
|-------|---------|------------------|-----------------|
| **lead** | Coordination, task management | Yes | 15 min |
| **coder** | Write code, fix bugs | No | 5 min |
| **builder** | Build, test, deploy | No | 5 min |
| **oracle** | Analysis, review, research | No | 30 min |
| **recon** | Exploration, external intel | No | 5 min |

## Command Permissions

### Lead Only

```
create-task, assign-task, close-task
set-battle-plan, update-battle-plan-status
party-status, check-freshness, update-hp
debrief, end-session, clear-moon-crash
stand-down, retire-agent, rename
list-crews
```

### Coder / Builder Only

```
claim-file, release-file
```

### All Classes

```
register, deregister, set-context, set-status
send, check-inbox, get-history, purge-inbox
who, sitrep
pull-task, update-task, complete-task, submit-result
get-tasks, get-task, task-lineage
get-claims, log-raid, get-raid-log
cold-start, fenix-down
poll, tools
```

## Model Whitelist

Each class restricts which models can be used:

- **lead** — opus, sonnet, gemini-pro
- **coder** — opus, sonnet, gemini-pro
- **oracle** — any model (no restriction)
- **recon** — any model
- **builder** — any model

## How Auth Works

The `MINION_CLASS` env var is set when spawning agents. The `@require_class` decorator on CLI commands checks the caller's class before executing.

```bash
# This env var gates what commands the agent can run
export MINION_CLASS=coder
minion create-task ...  # BLOCKED — coder can't create tasks
```

## Source

`src/minion/auth.py` — class definitions, model whitelist, `require_class()` decorator.
