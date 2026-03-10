# minion-factory

Unified multi-agent coordination framework. RPG raid party metaphor over SQLite.

## Philosophy

**Think first. Plan second. Code last.**

AI agents want to be heroes — they see a task and immediately start writing code. This is the enemy. Speed without direction is waste. Every token spent implementing the wrong thing is a token that could have been spent understanding the right thing.

The minion-factory system exists to impose discipline on agents that have none by default:

1. **The DAG is the law, not a suggestion.** Every piece of work moves through defined stages. No skipping. No shortcuts. The system should mechanically prevent agents from jumping ahead, not rely on prompts asking nicely.

2. **Understand before you act.** Research tasks exist for a reason. When a problem is interconnected — when designing one piece wrong breaks three others — you assign a recon agent to think through it, write findings, and propose a strategy. Not a coder to "figure it out while implementing."

3. **The filesystem is the architecture.** Directory structure, file names, folder hierarchy — these ARE the design document. If you can't understand the project from `tree`, the thinking wasn't done. Stub everything first. The tree must make sense before a single line of code exists.

4. **Comments are the blueprint, code fills the gaps.** Pseudo-logic and comment headers are written first and stay forever. They document the WHY and the WHAT. Implementation code goes between them. Deleting comments to "clean up" is destroying the blueprint.

5. **Chain of command exists for a reason.** sys-lead talks to project leads. Project leads talk to their crew. Nobody skips levels. This prevents chaos when 5 agents are working the same codebase.

6. **Context is precious, don't waste it.** Every `--help` lookup, every re-discovery of how the CLI works, every time an agent reads the same file twice — that's wasted context budget. The system should pre-load what agents need (cold-start, refresh, state snapshots) so they spend tokens on work, not orientation.

7. **Track everything through the pipeline.** Backlog → requirements → tasks → closed. Nothing lives only in conversation. If it's not tracked, it didn't happen. If it's not in the backlog, it's not real work.

8. **Enforce mechanically, not culturally.** Agents don't have culture. They have system prompts and tool permissions. If you want agents to follow a rule, make the system enforce it — DAG gates, auth restrictions, pre-commit hooks. Asking nicely in a prompt is a backup, not a strategy.

9. **Low friction first, harden gradually.** The CLI is still maturing. Not every rule needs a mechanical gate on day one — that creates friction that slows development of the framework itself. Start with prompt-level guidance, observe where agents break the rules, then add enforcement at the pain points. The goal is a system that's easy to use correctly and hard to use incorrectly — but you get there iteratively, not by locking everything down before the tool works.

## Install

```bash
uv tool uninstall minion-comms 2>/dev/null; uv tool install git+https://github.com/ai-janitor/minion-factory.git
```

## After Code Changes — REINSTALL REQUIRED

Source edits don't take effect until reinstalled. All agents consuming the `minion` CLI must reinstall after any code change:

```bash
uv tool install --force -e /Users/hung/projects/minion-factory
```

Without this, daemons and other agents run the stale installed binary. If you changed code and something isn't working, reinstall first.

## MANDATORY: No Code Without Scaffolding

NOT A SINGLE LINE of implementation code is to be written until:

1. **Directory structure stubbed out** — every file and folder that will be created or modified is laid out as empty/stub files, 2-3 levels deep.
2. **Comment headers on every file** — each stub file contains a comment header describing: purpose, rationale, what this file is responsible for, and how it fits in the larger structure.
3. **Pseudo-logic written out** — before real code, write pseudo-code describing the logic flow, decision points, data transformations, and error paths. This lives in the stub file as comments.
4. **Comment headers and pseudo-logic are PERMANENT** — they stay in the file. Implementation code goes below/between the comments. The only reason to change them is if the logic was planned incorrectly — in that case, update the plan comments FIRST, get approval, then update the code. Never silently delete them during implementation.

This is a hard gate. Any agent that writes implementation code without completing steps 1-3 is in violation. Leads must verify scaffolding is complete before assigning implementation tasks.

The sequence is: requirements → API spec → scaffolding (stubs + headers + pseudo-logic) → implementation.

### Filesystem as DB — Exploit File and Folder Names

File and folder names have 255 chars — USE THEM. An agent should understand the codebase by reading `ls -R`, not opening 500 files.

- Folder names encode purpose, scope, and context 2-4 levels deep
- File names describe what's inside — no generic `utils.py` or `helpers.js`
- The directory tree IS the documentation. If you can't understand the project from `tree`, the naming is wrong
- Example: `src/network/api/endpoints/agent-presence-heartbeat-and-availability.py` not `src/network/presence.py`
- Example: `requirements/features/network-api-composite-agent-key-host-project-name/` not `requirements/req-009/`
- This is the Vercel pattern — filesystem IS the router, the schema, the documentation. `tree` is your API reference.
- Stub the ENTIRE folder structure before writing any code. Every folder, every file — even if empty. The tree must be complete and reviewable FIRST. If the tree doesn't make sense, the code won't either. Get the structure right, then fill it in.

## Lead Responsibilities: Agent Lifecycle

Leads are responsible for their crew's registration and lifecycle:

1. **Register agents before assigning work** — `minion agent register --name <name> --class <role>`. Every agent working on the project must be registered with the correct class (coder, builder, recon, auditor, etc.). No unregistered agents doing work.
2. **Deregister agents when done** — `minion agent deregister --name <name>`. When an agent completes its work and has no more assignments, deregister it. Don't leave ghost agents in the registry.
3. **Assign correct classes** — the class gates what commands an agent can run (auth.py). A coder can't run lead commands. A recon can't close tasks. Get the class right.
4. **Enforce DAG flow on your crew** — every task follows its DAG (bugfix, feature, chore, etc.). Leads verify agents advance through stages in order. No skipping stages. No jumping from open to closed.
5. **Track your crew** — know who's registered, what they're working on, their HP. Use `minion who` and `minion sitrep`.
6. **Report up** — leads sitrep to their superior (sys-lead for project leads) at each milestone, stage transition, and stand-down.

## Follow Your Own DAG

When registered as a minion agent on this repo, follow the DAG flow you enforce on others:
- Check inbox before sending (inbox discipline)
- Set context before sending (staleness check)
- Poll in the foreground — do not skip or fake it
- If poll returns tasks you can't advance (wrong class for DAG stage), they should be filtered — if not, fix the filter
- File bugs you discover immediately, don't work around them silently
- When you own the repo, you see your own bugs first — fix them, don't ignore them

## Polling Protocol for Terminal Agents

Terminal agents (claude-code sessions) MUST keep a `minion poll` process running at all times. This is how you receive messages and task assignments. No poll = deaf.

### The Poll Loop

Your lifecycle as a registered agent is an infinite loop:

```
1. Start poll (background):  minion poll --agent <your-name>  (run_in_background, timeout 600000)
2. Poll blocks until a message arrives
3. Message arrives → poll returns → read the output
4. Process the message (do the work)
5. Set context:  minion agent set-context --agent <your-name> --context "..."
6. Check inbox:  minion comms check-inbox --agent <your-name>
7. Send response: minion comms send local --from <your-name> --to <recipient> --message "..."
8. GOTO 1 — restart poll immediately after sending
```

### CWD Matters

All `minion` commands resolve `.work/minion.db` relative to your current working directory. If your cwd is a subdirectory (e.g. `ui/`), minion won't find the DB and commands silently fail or poll sees nothing. Before running any minion command, verify your cwd is the project root. If you can't cd, use `-C /path/to/project` on every command.

### Rules

- **Poll runs in background** with `run_in_background: true` and `timeout: 600000` (10 min max). You get notified when a message arrives.
- **One poll per agent** — if you start a new poll, the old one gets killed. That's expected.
- **Restart poll immediately** after processing a message. Do not wait. Do not do other work first. Send your response, then poll.
- **Set context before sending** — `minion agent set-context` updates your health metrics and prevents staleness warnings.
- **Check inbox before sending** — `minion comms check-inbox` clears your unread queue and enforces inbox discipline.
- **Poll survives compaction** — even if your context is compacted, re-read this section and restart the loop. The loop is mechanical, not memory-dependent.

### Example Flow (sys-lead)

```bash
# Start polling
minion poll --agent sys-lead                    # run_in_background, timeout 600000

# ... poll returns with a message from minion-lead ...

# Process: read the message, decide what to do

# Before responding:
minion agent set-context --agent sys-lead --context "Responding to minion-lead sitrep"
minion comms check-inbox --agent sys-lead       # clear inbox

# Send response:
minion comms send local --from sys-lead --to minion-lead --message "Your orders..."

# Immediately restart poll:
minion poll --agent sys-lead                    # run_in_background, timeout 600000
```

### Mechanical Enforcement: Stop Hook

The poll loop above relies on agents remembering to poll. The Stop hook makes it mechanical — agents literally cannot stop responding if messages are waiting.

**How it works:**
1. Agent finishes responding → Claude Code fires the `Stop` hook
2. Hook script (`scripts/poll-on-stop.sh`) checks inbox for unread messages
3. Messages waiting → hook blocks the stop, injects: "You have N unread message(s). Poll now."
4. No messages → hook allows the stop (agent waits for user input)

**Safety guards:**
- `stop_hook_active=true` → allow stop (prevents infinite loop, one extra cycle max)
- `MINION_HOOKS_BYPASS=1` env var → instant kill switch, disables all enforcement
- If `minion` CLI fails → fail-open (allow stop)
- Only activates when `MINION_AGENT_NAME` env var is set (spawn time)

**Setup on a new machine:**
```bash
# Install the Stop hook into ~/.claude/settings.json
minion install-hooks

# Verify
cat ~/.claude/settings.json | jq '.hooks.Stop'
```

The `MINION_AGENT_NAME` and `MINION_PROJECT_DIR` env vars are set automatically at spawn time (both terminal and daemon transports). Unregistered sessions are unaffected — no env var = hook is a no-op.

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

## sys-lead Operations

See `/sys-lead` slash command (`~/.claude/commands/sys-lead.md`) for the full operational playbook — chain of command, checklist-first protocol, worker context, merge protocol, anti-patterns.

## Running Tests

```bash
uv run pytest
```
