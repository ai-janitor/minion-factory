# Crews — Spawn & Lifecycle

A crew is a YAML file that defines a party of agents — who they are, what they do, and what provider runs them.

## Crew YAML Structure

```yaml
project_dir: .

lead:
  name: cloud
  agent_class: lead
  transport: terminal          # interactive session
  system: |
    You are cloud, party leader...
    ON STARTUP:
    1. minion register --name cloud --class lead --transport terminal
    2. minion set-context --agent cloud --context "just started"
    3. minion check-inbox --agent cloud
    4. minion set-status --agent cloud --status "ready for orders"
    5. minion who

agents:
  tifa:
    role: coder                # agent class
    zone: "Implementation"     # work zone
    provider: claude           # AI provider
    model: claude-sonnet-4-6   # model override
    permission_mode: bypassPermissions
    system: |
      You are tifa (coder class)...
      ON STARTUP:
      1. minion register --name tifa --class coder --transport daemon
      ...

  redxiii:
    role: recon
    provider: gemini
    allowed_tools: "Read,Glob,Grep,Bash,WebSearch,WebFetch"
    system: |
      ...
```

## Agent Fields

| Field | Required | Description |
|-------|----------|-------------|
| `role` | yes | Agent class: lead, coder, builder, oracle, recon |
| `zone` | no | Work zone description |
| `provider` | yes | claude, codex, gemini, opencode |
| `model` | no | Model override (provider default if omitted) |
| `transport` | no | `daemon` (default), `daemon-ts`, or `terminal` |
| `permission_mode` | no | `bypassPermissions` for daemon agents |
| `allowed_tools` | no | Comma-separated tool whitelist |
| `system` | yes | System prompt with ON STARTUP boot sequence |

## Transport Types

| Transport | How It Runs |
|-----------|-------------|
| `terminal` | Interactive Claude Code session (lead) |
| `daemon` | Python daemon runner — forked process with poll loop |
| `daemon-ts` | TypeScript SDK daemon — `npx tsx` process |

## Spawn

```bash
minion spawn-party --crew ff7 --project-dir .
```

What happens:
1. Reads `crews/ff7.yaml`
2. Runs `install-docs` (deploys contracts to `~/.minion_work/docs/`)
3. Auto-registers all agents in SQLite
4. Clears `stand_down` and `moon_crash` flags
5. Creates tmux session `crew-ff7`
6. For each daemon agent: creates tmux pane (tail -f log), forks daemon process
7. For terminal agents (lead): opens interactive session
8. Each agent runs ON STARTUP boot commands

### Selective Spawn

Spawn only specific agents:

```bash
minion spawn-party --crew ff7 --project-dir . --agents tifa,barret
```

## Stand Down

Dismiss the entire party:

```bash
minion stand-down --agent cloud --crew ff7
```

What happens:
1. Sets `stand_down` flag in SQLite
2. Stops all daemon processes (SIGTERM via PID from state files)
3. Kills tmux session
4. Daemons see flag on next poll, exit with code 3

Without `--crew`, dismisses ALL active crews.

## Retire Single Agent

Remove one agent without affecting the party:

```bash
minion retire-agent --agent tifa --requesting-agent cloud
```

What happens:
1. Sets `agent_retire` record
2. Deregisters agent (releases file claims)
3. Daemon sees retire flag, exits gracefully

## Hand Off Zone

Transfer a work zone between agents:

```bash
minion hand-off-zone --from tifa --to barret,aerith --zone "backend"
```

Updates agent zones, logs high-priority raid entry.

## Crew Files

| Crew | File | Description |
|------|------|-------------|
| ff1 | `crews/ff1.yaml` | Classic party — 7 agents |
| ff7 | `crews/ff7.yaml` | Midgar party — 6 agents |

### Create Your Own

1. Create `crews/myteam.yaml`
2. Define lead + agents with roles, providers, system prompts
3. `minion spawn-party --crew myteam --project-dir .`

## Tmux Layout

Each crew gets a tmux session named `crew-{name}`. Each daemon agent gets a pane showing `tail -f` of its log file. Panes are color-coded by role and labeled with agent name + provider.

```bash
tmux attach -t crew-ff7    # attach to see all agent logs
```
