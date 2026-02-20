# Daemon — Agent Runtime

The daemon runner manages agent processes: boot, poll loop, HP tracking, compaction recovery.

## Boot Sequence

When a daemon agent starts, it runs 3 commands (defined in `docs/contracts/boot-sequence.json`):

```bash
1. minion --compact register --name {agent} --class {role} --transport daemon
2. minion set-context --agent {agent} --context "just started"
3. minion set-status --agent {agent} --status "ready for orders"
```

No `check-inbox` at boot — the daemon's watcher handles all inbox reads.

After boot, the agent enters the poll loop.

## Poll Loop

```
┌──────────────┐
│  poll inbox   │◄──────────────────────┐
└──────┬───────┘                        │
       │                                │
  messages?                        sleep 30s
       │                                │
   ┌───┴───┐                            │
   │  yes  │    no ─────────────────────┘
   └───┬───┘
       │
  build prompt
  (rules + inbox)
       │
  invoke agent
  (claude/codex/gemini)
       │
  update HP
       │
  back to poll ─────────────────────────┘
```

## HP (Health Points)

Token budget tracking. Agents consume context window as they work.

```
HP% = 100 - (used_tokens / context_window * 100)

> 50%   = Healthy
25-50%  = Wounded
< 25%   = CRITICAL
```

Sources:
- Daemon measures token usage from provider stream responses
- Agent self-reports via `minion set-context --hp 78`
- `party-status` shows HP for all agents

## Compaction & Recovery

When an agent hits context window limits, the provider compacts history. The daemon detects compaction markers (defined in `docs/contracts/compaction-markers.json`).

### Fenix-Down Protocol

Before context death, agent dumps knowledge:

```bash
minion fenix-down --agent alice \
  --files "src/auth.py,docs/decisions.md" \
  --manifest "WIP: fixing login flow, auth middleware pattern uses JWT"
```

### Cold-Start Recovery

On restart, agent reads fenix-down records:

```bash
minion cold-start --agent alice
```

Returns unconsumed fenix-down records (files + manifest), marks them consumed. Agent resumes with prior context.

## Daemon Rules

Defined in `docs/contracts/daemon-rules.json`. Injected into every agent prompt.

### Common Rules (all agents)
- No `AskUserQuestion` — blocks in headless mode
- Route questions to lead via `minion send`
- One summary message when done
- Task governance: check inbox, don't re-register

### Lead Rules
- Create tasks, define scope, review results
- Own the battle plan

### Non-Lead Rules
- Execute assigned tasks
- Forward ideas to lead

## State Files

Each daemon writes state to `{project}/.minion-swarm/state/{agent}.json`:

```json
{
  "agent": "tifa",
  "provider": "claude",
  "pid": 12345,
  "status": "idle",
  "updated_at": "2026-02-20T14:30:00Z",
  "consecutive_failures": 0,
  "resume_ready": true
}
```

Used for stop/restart (PID), health checks (status), and resume decisions.

## Logs

Each agent logs to `{project}/.minion-swarm/logs/{agent}.log`. Errors go to `{agent}.error.log`.

```bash
# View logs in tmux
tmux attach -t crew-ff7

# Or directly
tail -f .minion-swarm/logs/tifa.log
```

## Config Defaults

Defined in `docs/contracts/config-defaults.json`:

| Setting | Default |
|---------|---------|
| max_history_tokens | 100,000 |
| max_prompt_chars | 120,000 |
| no_output_timeout_sec | 600 |
| retry_backoff_sec | 30 |
| retry_backoff_max_sec | 300 |
| max_console_stream_chars | 12,000 |
| default_context_window | 200,000 |

## Source Files

| File | What |
|------|------|
| `src/minion/daemon/runner.py` | `AgentDaemon` class — main loop |
| `src/minion/daemon/config.py` | `SwarmConfig`, `AgentConfig` |
| `src/minion/daemon/watcher.py` | `CommsWatcher` — SQLite file watcher |
| `src/minion/daemon/buffer.py` | `RollingBuffer` — token-limited history |
| `src/minion/daemon/contracts.py` | Contract JSON loader |
| `src/minion/daemon/__main__.py` | Entry point for forked daemons |
