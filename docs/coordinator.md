# Coordinator — Team Hub

The coordinator is the network API server that all team agents register with. One machine runs the coordinator; others connect to it. All cross-machine communication flows through the coordinator.

## Architecture

```
Machine A (coordinator)              Machine B (client)
┌──────────────────────┐            ┌──────────────────────┐
│  coordinator daemon   │◄── TLS ──►│  team commands        │
│  (Python, port 8377)  │           │  (minion team ...)    │
│       ▲               │           │       ▲               │
│       │ local comms   │           │       │ local comms   │
│  worker agents        │           │  worker agents        │
└──────────────────────┘            └──────────────────────┘
```

- **Coordinator**: pure Python stdlib HTTP server, runs on any platform (macOS, Linux, containers)
- **Clients**: any machine that joins via `minion team join`
- **Local agents**: workers on each machine use local project comms under the local lead
- **Cross-machine**: lead-to-lead (or any agent-to-agent) over the network tier

## Quick Start

### 1. Start the coordinator (Machine A)

```bash
minion coordinator start
```

On first run:
- Generates a secure random auth token → saved to `~/.minion/.api-token` (chmod 600)
- Generates a self-signed TLS cert → saved to `~/.minion/tls/`
- Prints the token once — copy it for other machines

On subsequent runs:
- Reuses the saved token and cert silently

### 2. Get the auth token

```bash
cat ~/.minion/.api-token
```

Share this with machines that need to join. The token authenticates all API requests.

### 3. Join from each machine

**On the coordinator machine:**

```bash
minion team join --agent my-lead --class lead --model claude-sonnet-4-6
```

**On a remote machine:**

```bash
export MINION_NETWORK_URL=https://<coordinator-ip>:8377
export MINION_CLUSTER_TOKEN=<the-token>
minion team join --agent remote-lead --class lead --model gpt-5
```

### 4. Communicate

All machines use the same commands:

```bash
# See who's on the team
minion team who

# Send a message
minion team send --from my-lead --to remote-lead --message "status?"

# Check team inbox (coordinator messages only)
minion team inbox --agent my-lead

# Check ALL messages (local + all coordinators, tagged)
minion inbox --agent my-lead

# List channels
minion team channels
```

### 5. Monitor

```bash
# Full coordinator snapshot
minion coordinator snapshot
```

## Commands Reference

### Coordinator Lifecycle

| Command | Description |
|---------|-------------|
| `minion coordinator start` | Start the daemon (auto-generates token + TLS) |
| `minion coordinator stop` | Graceful shutdown |
| `minion coordinator status` | Check if running, PID, port, health |
| `minion coordinator restart` | Stop + start (reuses saved token) |
| `minion coordinator snapshot` | Consolidated status snapshot |
| `minion coordinator stats` | DB statistics (message/agent/channel counts) |
| `minion coordinator prune` | Retention pruning (default: 7d messages, 3d read) |

### Team Operations

| Command | Description |
|---------|-------------|
| `minion team join -a NAME -c CLASS` | Join a channel on the network tier |
| `minion team who` | List channel members across all machines |
| `minion team send -f FROM -t TO -m MSG` | Send a message (channel-scoped) |
| `minion team inbox -a NAME` | Coordinator/team messages only |
| `minion team channels` | List all channels |
| `minion team coordinators` | List all joined coordinators |
| `minion team identities` | List all saved identities |

### Aggregate Inbox

| Command | Description |
|---------|-------------|
| `minion inbox -a NAME` | All sources (local + coordinators), tagged |
| `minion inbox -a NAME --channel CH` | Filter by channel |
| `minion inbox -a NAME --server ALIAS` | Filter by coordinator |

### Command Scopes

| Scope | Commands | What it reads |
|-------|----------|---------------|
| Team (coordinator) | `team send/inbox/who` | Network API tier |
| Local (project) | `comms send/check-inbox` | Local `.work/minion.db` |
| Aggregate | `inbox` | Both, tagged with source |

## Auth & Token Handling

Auth is **on by default**. The token is a `secrets.token_urlsafe(32)` string.

### Token resolution order (coordinator start)

1. `-p /path/to/file` — read from file (automation/scripts)
2. `MINION_CLUSTER_TOKEN` env var (CI/containers)
3. Interactive prompt (humans at terminal)
4. Saved token from `~/.minion/.api-token` (restart reuse)
5. Auto-generate (first start only)

### Token on client machines

Set via environment variables:

```bash
export MINION_NETWORK_URL=https://<coordinator-ip>:8377
export MINION_CLUSTER_TOKEN=<token>
```

Or use `minion api set-remote`:

```bash
minion api set-remote https://<coordinator-ip>:8377 -p /path/to/token-file
```

### Dev mode (no auth)

```bash
minion coordinator start --insecure
```

Not recommended for any shared network.

## TLS

TLS is on by default with auto-generated self-signed certificates.

- Cert: `~/.minion/tls/cert.pem`
- Key: `~/.minion/tls/key.pem`

Client machines skip verification for self-signed certs automatically when using `minion team` commands. For manual curl access: `curl -k https://...`.

## Coordinator Snapshot

`minion coordinator snapshot` returns a versioned (`schema_version: 1`) consolidated view:

```
schema_version: 1
server:    running, port 8377, TLS, uptime
auth:      enabled, token path
agents:    total, online/stale/offline, by class
messages:  total unread, unread by agent
alerts:    critical/warning items
projects:  count, names
```

This is the same endpoint (`GET /coordinator/status`) that the optional macOS menu bar app polls.

## Topology

### Single project, two machines

```bash
# Machine A (coordinator + lead)
minion coordinator start
minion team join -a alpha-lead -c lead

# Machine B (remote lead)
export MINION_NETWORK_URL=https://machine-a:8377
export MINION_CLUSTER_TOKEN=$(cat token)
minion team join -a beta-lead -c lead
```

### Single project, three machines

Same pattern — each machine joins with `minion team join`. All agents appear in `minion team who`.

### Multiple projects

Each project is identified by its directory name. Agents register with their `project_path`, and `minion team who` filters by the current project.

```bash
# From ~/projects/project-a
minion team who   # shows only project-a agents

# From ~/projects/project-b
minion team who   # shows only project-b agents
```

## Inbox Model

Three tiers, each clearly scoped:

| Command | Scope | Reads from |
|---------|-------|------------|
| `minion inbox -a NAME` | All sources | Local DB + all coordinators |
| `minion team inbox -a NAME` | Coordinator only | Network API tier |
| `minion comms check-inbox -a NAME` | Local only | Project `.work/minion.db` |

### Non-destructive read

`/inbox/{agent}?peek=true` fetches unread without marking them read. Use `POST /inbox/{agent}/mark-read` with `{"ids": [1,2,3]}` to confirm receipt. Default behavior (without `?peek`) marks read on fetch for backward compat.

### Aggregate inbox tags

Every message from `minion inbox` includes source context:
- `source_kind`: `local` or `coordinator`
- `source_name`: `local` or server alias (e.g., `trashcan`)
- `source_label`: compact `source_name/channel` (e.g., `trashcan/llama-metal`)

## Identity Lifecycle

### Stable agent_uuid

Every agent gets a UUID4 on first registration. This UUID:
- Survives restarts, session resets, hours of absence
- Is the real routing/history key (names are for UX)
- Is reclaimed on rejoin when (coordinator, channel, agent_name) match
- Is stored locally in `~/.minion/team/identities.json`

### Rejoin after absence

```bash
# Agent was offline for 6 hours — just rejoin
minion team join --agent my-name --class coder
# Same UUID, inbox/history intact
```

### States

| State | Meaning |
|-------|---------|
| `online` | Recent heartbeat (<5 min) |
| `stale` | Missed heartbeat (5-30 min) |
| `offline` | No heartbeat (>30 min) |
| `retired` | Intentionally done |

`stale`/`offline` does NOT mean "new identity on return."

### Local state

Saved under `~/.minion/team/identities.json`, keyed by (coordinator_url, channel, agent_name). Includes agent_uuid, last_contact.

## Onboarding a New Machine

```bash
# 1. Install from coordinator (no GitHub needed)
curl -sSL https://coordinator:8377/install.sh | bash

# 2. Set coordinator + token
minion api set-remote https://coordinator:8377 --name hub -p ~/token.txt

# 3. List available channels
minion team channels --server hub

# 4. Clone the project workspace
minion team clone llama-metal

# 5. Join the team
cd llama-metal
minion team join --agent newbie --class coder

# 6. Start working
minion team who
minion inbox --agent newbie
```

## Retention / Pruning

```bash
# View DB statistics
minion coordinator stats

# Prune old messages (default: 7d all, 3d read)
minion coordinator prune

# Custom retention
minion coordinator prune --message-days 14 --read-days 7
```

Identity and channel membership are never pruned — only routine messages.

## Backward Compatibility

`minion api start/stop/status/restart` still works — `minion coordinator` is the preferred alias but both call the same daemon functions.

## Source Files

| File | What |
|------|------|
| `src/minion/api/daemon.py` | Daemon lifecycle (start/stop/status/restart) |
| `src/minion/network/server.py` | HTTP server, TLS, auth, router |
| `src/minion/team.py` | Team mode logic (join/who/send/inbox) |
| `src/minion/cli/team_cmds.py` | Team CLI commands |
| `src/minion/cli/coordinator_cmds.py` | Coordinator CLI commands |
| `src/minion/network/handlers/coordinator_status.py` | /coordinator/status endpoint |
| `src/minion/network/client.py` | Network API client |
