# Network API Reference

The network server (`src/minion/network/server.py`) is the API GLOBAL coordinator — a stdlib-only Python HTTP server that handles cross-machine agent communication and will serve the unified dashboard UI.

**Binding:** `0.0.0.0:8377` (default)
**Database:** `~/.minion/network.db` (SQLite, WAL mode)
**TLS:** On by default (`~/.minion/tls/cert.pem` + `key.pem`). Opt-out: `MINION_NETWORK_INSECURE=1`

## Agent Identity — Composite Key

Agents are uniquely identified by the composite key `(machine_id, project_path, name)`, displayed as `host/project/name` — e.g., `macbook/minion-factory/cloud`.

**Why:** A bare `name` PRIMARY KEY causes collisions when the same agent name is used across machines or projects.

**Short name resolution** (when `to` field in `/send` doesn't contain `/`):
1. Same `machine_id` + same `project_path` as sender → exact match
2. Same `machine_id`, any `project_path` → use if unique, error if ambiguous
3. Any `machine_id` globally → use if unique, error if ambiguous with suggestions

**Full path format:** All responses include an `fqn` field (e.g., `"fqn": "macbook/minion-factory/cloud"`). The `to_agent`/`from_agent` fields in the messages table store full paths for unambiguous routing.

---

## Authentication

All API endpoints (except `GET /`) require a Bearer token:

```
Authorization: Bearer <MINION_CLUSTER_TOKEN>
```

- Token is read from `MINION_CLUSTER_TOKEN` env var at startup
- If no token is set, auth is disabled (dev only)
- The dashboard HTML at `GET /` is served without auth — the embedded JS validates the token client-side via `/who`

## Current Endpoints

### GET /

**Auth:** None
**Response:** HTML dashboard page (from `minion.network.dashboard`)

Serves an inline single-page dashboard. The JS prompts for the cluster token, stores it in `localStorage`, and uses it for subsequent API calls.

---

### GET /health

**Auth:** Bearer token
**Response:**
```json
{"status": "ok", "timestamp": "2026-03-04T00:45:00.000000"}
```

---

### GET /who

**Auth:** Bearer token

**Query params:**
- `?class=coder` — filter by agent class
- `?project=minion-factory` — filter by project name (derived from project_path)
- `?status=online` — filter by presence (`online`, `stale`, `offline`)
- `?available=true` — only agents that are online, HP >25%, and not blocked

**Response:**
```json
{
  "agents": [
    {
      "name": "claude-opus",
      "agent_class": "lead",
      "host": "10.0.1.5",
      "project_path": "/Users/hung/projects/minion-factory",
      "project_name": "minion-factory",
      "machine_id": "macbook-pro",
      "registered_at": "2026-03-04T00:38:00",
      "last_seen": "2026-03-04T00:45:00",
      "presence": "online",
      "availability": "busy",
      "current_task": {"id": 2, "title": "Add read-only dashboard endpoints", "status": "assigned"},
      "model": "opus",
      "capabilities": ["code", "review", "investigate", "delegate"],
      "crew_name": "core",
      "local_lead": null,
      "machine_specs": {"gpu": null, "ram_gb": 32, "cpu_cores": 10},
      "runtimes": ["python3.13", "node22"],
      "os_platform": "darwin-arm64",
      "session_count": 5,
      "compaction_count": 2,
      "crash_rate": 0.05,
      "total_input_tokens": 450000,
      "total_output_tokens": 120000,
      "last_task_completed_at": "2026-03-04T00:44:00",
      "autonomous_delegation": true,
      "heartbeat_latency_ms": 12
    }
  ],
  "source": "network"
}
```

**Presence thresholds** (computed from `last_seen`):
- `online`: last_seen < 5 minutes ago
- `stale`: last_seen 5-30 minutes ago
- `offline`: last_seen > 30 minutes ago

**Availability** (computed from presence + HP + task state):
- `idle`: online, no current task
- `busy`: online, has assigned task
- `blocked`: online, current task is blocked
- `critical`: HP < 25%

**Enrichment:** `current_task` and HP data are read from per-project `.work/minion.db` via `project_path`. If the project DB is unreachable, `current_task` is `null` and availability falls back to presence-based.

Lists all agents registered on the network coordinator. The `project_path` field is key for multi-project dashboard support — it tells the server where each project's `.work/minion.db` lives.

---

### GET /messages/recent

**Auth:** Bearer token
**Response:**
```json
{
  "messages": [
    {
      "id": 1,
      "from_agent": "claude-opus",
      "to_agent": "sys-lead",
      "content": "Sitrep: ...",
      "timestamp": "2026-03-04T00:45:00",
      "read_flag": 0
    }
  ]
}
```

Returns the 20 most recent messages from the network coordinator DB (cross-machine messages only, not project-local ones).

---

### GET /inbox/{agent}

**Auth:** Bearer token
**Response:**
```json
{
  "messages": [...],
  "agent": "claude-opus"
}
```

Fetches unread messages for the given agent and marks them as read. Updates the agent's `last_seen` timestamp.

---

### POST /register

**Auth:** Bearer token
**Request body:**
```json
{
  "name": "claude-opus",
  "agent_class": "lead",
  "host": "10.0.1.5",
  "project_path": "/Users/hung/projects/minion-factory",
  "machine_id": "macbook-pro",
  "model": "opus",
  "capabilities": ["code", "review", "investigate", "delegate"],
  "crew_name": "core",
  "local_lead": null,
  "machine_specs": {"gpu": null, "ram_gb": 32, "cpu_cores": 10},
  "runtimes": ["python3.13", "node22"],
  "os_platform": "darwin-arm64",
  "autonomous_delegation": true,
  "session_count": 5,
  "compaction_count": 2,
  "crash_rate": 0.05,
  "total_input_tokens": 450000,
  "total_output_tokens": 120000,
  "last_task_completed_at": "2026-03-04T00:44:00"
}
```

**Required fields:** `name`
**Optional fields (core):** `agent_class` (default: "coder"), `host`, `project_path`, `machine_id`
**Optional fields (identity):** `model`, `capabilities` (JSON array), `crew_name`, `local_lead`
**Optional fields (environment):** `machine_specs` (JSON object), `runtimes` (JSON array), `os_platform` — reported once at registration
**Optional fields (trust/history):** `session_count`, `compaction_count`, `crash_rate`, `total_input_tokens`, `total_output_tokens`, `last_task_completed_at` — updated per heartbeat
**Optional fields (routing):** `autonomous_delegation` (bool)

**Response:**
```json
{"status": "registered", "agent": "claude-opus"}
```

Upserts the agent. On conflict, updates all provided fields and `last_seen`. Backward compatible — existing agents that don't send new fields continue to work (new fields default to `null`).

---

### POST /send

**Auth:** Bearer token
**Request body:**
```json
{
  "from": "claude-opus",
  "to": "sys-lead",
  "message": "Sitrep: all clear"
}
```

**Required fields:** `from`, `to`, `message`

**Response:**
```json
{"status": "sent", "from": "claude-opus", "to": "sys-lead"}
```

Delivers a message. Verifies the target agent exists. Updates sender's `last_seen`.

---

## Network DB Schema

```sql
CREATE TABLE agents (
    -- Core (existing)
    name                  TEXT PRIMARY KEY,
    agent_class           TEXT NOT NULL DEFAULT 'coder',
    host                  TEXT,
    project_path          TEXT,
    machine_id            TEXT,
    registered_at         TEXT,
    last_seen             TEXT,

    -- Identity & Capability (new)
    model                 TEXT,            -- opus/sonnet/haiku
    capabilities          TEXT,            -- JSON array: ["code","build","test"]
    crew_name             TEXT,
    local_lead            TEXT,

    -- Environment (reported at registration)
    machine_specs         TEXT,            -- JSON: {"gpu":"A100","ram_gb":64,"cpu_cores":16}
    runtimes              TEXT,            -- JSON array: ["python3.13","node22","cuda12"]
    os_platform           TEXT,            -- e.g. "darwin-arm64"

    -- Trust & History (updated per heartbeat)
    session_count         INTEGER,
    compaction_count      INTEGER,
    crash_rate            REAL,            -- timeout+crash / total invocations
    total_input_tokens    INTEGER,
    total_output_tokens   INTEGER,
    last_task_completed_at TEXT,

    -- Routing
    autonomous_delegation INTEGER DEFAULT 0,  -- 1 = accepts direct tasks, 0 = needs lead relay
    heartbeat_latency_ms  INTEGER
);

CREATE TABLE messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    from_agent  TEXT NOT NULL,
    to_agent    TEXT NOT NULL,
    content     TEXT NOT NULL,
    timestamp   TEXT NOT NULL,
    read_flag   INTEGER DEFAULT 0
);

CREATE INDEX idx_msg_to_unread ON messages(to_agent, read_flag);
```

---

## Proposed Dashboard Endpoints

These endpoints will read from per-project `.work/minion.db` files, discovered via `project_path` from the network coordinator's `agents` table.

### Multi-Project Discovery

The network server already stores `project_path` for each registered agent. To serve dashboard data:

1. Query `SELECT DISTINCT project_path FROM agents WHERE project_path IS NOT NULL` from `network.db`
2. For each project, open `<project_path>/.work/minion.db` in read-only mode
3. Route requests by project via URL prefix: `/projects/<project_name>/api/...`
4. Project name derived from the last path component (e.g., `/Users/hung/projects/foo` → `foo`)
5. Cache open DB connections via LRU cache: max 10 open connections, 5-minute TTL, read-only mode (`sqlite3.connect("file:...?mode=ro", uri=True)`). Evict least-recently-used when capacity is reached. Close connections on TTL expiry

### GET /projects

**Auth:** Bearer token
**Response:**
```json
{
  "projects": [
    {
      "name": "minion-factory",
      "path": "/Users/hung/projects/minion-factory",
      "agents": 3,
      "has_db": true
    }
  ]
}
```

Lists all discovered projects from registered agents.

---

### GET /projects/{name}/agents

**Auth:** Bearer token
**Source DB:** `<project_path>/.work/minion.db`

Returns agents from the project-local DB with full detail: `name`, `agent_class`, `model`, `status`, `hp_current`, `hp_max`, `transport`, `context_summary`, `current_zone`, `current_role`. Computes HP percentage and includes current task assignment.

Also includes per-agent operational metrics from `invocation_log` and `compaction_log`:
- `invocation_count`: total invocations for this agent
- `total_input_tokens`, `total_output_tokens`: cumulative token burn
- `compaction_count`: how many times context was compacted
- `last_invocation`: timestamp of most recent invocation
- `session_history`: last 10 invocations with `started_at`, `ended_at`, `exit_code`, `input_tokens`, `output_tokens`, `compacted`

**invocation_log schema:**
```sql
invocation_log (id, agent_name, pid, model, generation, rss_bytes,
  input_tokens, output_tokens, exit_code, timed_out, interrupted,
  compacted, started_at, ended_at)
```

**compaction_log schema:**
```sql
compaction_log (id, agent_name, model, pid, rss_pre_bytes, rss_post_bytes,
  tokens_pre, tokens_post, generation, compacted_at)
```

Equivalent to `ui/server.js` → `GET /api/agents` (extended with invocation/compaction data).

---

### GET /projects/{name}/tasks

**Auth:** Bearer token
**Source DB:** `<project_path>/.work/minion.db`

Returns tasks from the project-local DB: `id`, `title`, `status`, `task_type`, `assigned_to`, `progress`, `zone`, `blocked_by`, `blocked_reason`, `requirement_path`, timestamps.

**Query params:**
- `?status=open` — filter by status (`open`, `assigned`, `in_progress`, `closed`, etc.)
- `?assigned_to=claude-opus` — filter by assignee
- `?limit=50` — max results (default: 100)
- `?offset=0` — pagination offset

Equivalent to `ui/server.js` → `GET /api/tasks`.

---

### GET /projects/{name}/tasks/{id}/lineage

**Auth:** Bearer token
**Source DB:** `<project_path>/.work/minion.db`

Returns the task detail plus its full `task_history` (status transitions with agent and timestamp). Includes flow stage info.

Equivalent to `ui/server.js` → `GET /api/task-lineage/:id`.

---

### GET /projects/{name}/messages

**Auth:** Bearer token
**Source DB:** `<project_path>/.work/minion.db`

Returns messages from the project-local DB. Messages store content on disk via `content_file` — the endpoint reads the file and returns inline content. Fields: `id`, `from_agent`, `to_agent`, `content`, `timestamp`, `is_cc`, `cc_original_to`.

**Query params:**
- `?from=claude-opus` — filter by sender
- `?to=sys-lead` — filter by recipient
- `?limit=50` — max results (default: 100)

Equivalent to `ui/server.js` → `GET /api/messages`.

---

### GET /projects/{name}/raid-log

**Auth:** Bearer token
**Source DB:** `<project_path>/.work/minion.db`

Returns raid log entries. Each entry has an `entry_file` path — the endpoint reads file content from disk and returns it inline.

Equivalent to `ui/server.js` → `GET /api/raid-log`.

---

### GET /projects/{name}/flows/{type}

**Auth:** Bearer token
**Source:** `<project_path>/task-flows/<type>.yaml` (or built-in flow definitions)

Returns the parsed flow DAG: stages, transitions, worker restrictions, terminal states. Resolves YAML inheritance chains.

Equivalent to `ui/server.js` → `GET /api/flows/:type`.

---

### GET /projects/{name}/requirements

**Auth:** Bearer token
**Source DB:** `<project_path>/.work/minion.db`

Returns all requirements with stage tracking: `id`, `file_path`, `origin`, `stage`, `flow_type`, `parent_id`, timestamps. Includes linked task counts and completion percentage.

**Query params:**
- `?stage=investigating` — filter by current stage
- `?flow_type=requirement` — filter by flow type (`requirement`, `requirement-lite`)

*New endpoint — not in ui/server.js.*

---

### GET /projects/{name}/backlog

**Auth:** Bearer token
**Source DB:** `<project_path>/.work/minion.db`

Returns backlog items: `id`, `file_path`, `type`, `title`, `priority`, `status`, `source`, `promoted_to`, timestamps.

**Query params:**
- `?priority=high` — filter by priority (`high`, `medium`, `low`)
- `?status=open` — filter by status (`open`, `promoted`, `killed`, `deferred`)

*New endpoint — not in ui/server.js.*

---

### GET /projects/{name}/requirements/{id}/lineage

**Auth:** Bearer token
**Source DB:** `<project_path>/.work/minion.db`

Returns the full requirement DAG history — every stage transition with timestamp and who advanced it. Includes the requirement's current stage, linked tasks, and child requirements (recursive tree).

**Response:**
```json
{
  "requirement": {
    "id": 1,
    "file_path": "features/ui-dashboard",
    "stage": "tasked",
    "flow_type": "requirement"
  },
  "stage_history": [
    {"from_stage": null, "to_stage": "seed", "advanced_by": "backlog-promote", "timestamp": "..."},
    {"from_stage": "seed", "to_stage": "itemizing", "advanced_by": "claude-opus", "timestamp": "..."},
    {"from_stage": "itemizing", "to_stage": "itemized", "advanced_by": "claude-opus", "timestamp": "..."},
    {"from_stage": "itemized", "to_stage": "investigating", "advanced_by": "claude-opus", "timestamp": "..."},
    {"from_stage": "investigating", "to_stage": "findings_ready", "advanced_by": "claude-opus", "timestamp": "..."},
    {"from_stage": "findings_ready", "to_stage": "decomposing", "advanced_by": "claude-opus", "timestamp": "..."},
    {"from_stage": "decomposing", "to_stage": "tasked", "advanced_by": "claude-opus", "timestamp": "..."}
  ],
  "children": [...],
  "linked_tasks": [...],
  "completion_pct": 0
}
```

Stage history is derived from `requirements.updated_at` deltas and the `transition_log` table (if available). Tracks: seed → itemizing → itemized → investigating → findings_ready → decomposing → tasked → in_progress → completed.

*New endpoint — not in ui/server.js.*

---

### GET /overview

**Auth:** Bearer token
**Source:** All project DBs + network coordinator DB

System-wide summary across all registered projects. This is the primary view for sys-lead.

**Response:**
```json
{
  "projects": 3,
  "backlog": {"open": 5, "promoted": 8, "killed": 1, "deferred": 2},
  "requirements": {
    "seed": 2, "itemizing": 0, "itemized": 1, "investigating": 1,
    "findings_ready": 0, "decomposing": 0, "tasked": 3, "in_progress": 2, "completed": 5
  },
  "tasks": {"open": 4, "assigned": 3, "in_progress": 6, "closed": 12, "blocked": 1},
  "agents": {
    "total": 8,
    "by_hp": {"healthy": 5, "wounded": 2, "critical": 1},
    "by_class": {"lead": 2, "coder": 4, "recon": 1, "oracle": 1}
  },
  "alerts": [...]
}
```

Aggregates counts from all discovered project DBs. HP tiers: healthy (>60%), wounded (30-60%), critical (<30%).

---

### GET /alerts

**Auth:** Bearer token
**Source:** All project DBs + network coordinator DB

Returns actionable alerts for sys-lead monitoring.

**Response:**
```json
{
  "alerts": [
    {
      "type": "stalled_requirement",
      "severity": "warning",
      "project": "minion-factory",
      "detail": "features/ui-dashboard stuck at 'investigating' for 2h15m",
      "requirement_id": 1
    },
    {
      "type": "hp_critical",
      "severity": "critical",
      "project": "minion-factory",
      "detail": "Agent 'viper' at 15% HP",
      "agent": "viper"
    },
    {
      "type": "unread_messages",
      "severity": "warning",
      "project": "minion-factory",
      "detail": "Agent 'torvalds' has 3 unread messages (oldest: 45m ago)",
      "agent": "torvalds"
    },
    {
      "type": "missing_flow_hint",
      "severity": "info",
      "project": "minion-factory",
      "detail": "Backlog item 'refactor-auth' has no flow_hint set",
      "backlog_id": 7
    }
  ]
}
```

**Alert types:**
- `stalled_requirement` — requirement in same stage for >1 hour
- `hp_critical` — agent HP below 30%
- `unread_messages` — agent has unread messages older than 30 minutes
- `missing_flow_hint` — backlog item has no `flow_hint` set (can't be promoted without one)

Can also be folded into `/overview` response under the `alerts` key.

---

## Elastic Scaling Endpoints

### POST /spawn

**Auth:** Bearer token (lead-class agents only)
**Request body:**
```json
{
  "class": "coder",
  "capabilities": ["python", "test"],
  "crew": "engineers",
  "target_machine": "gpu-server",
  "task_id": 42,
  "project_path": "/Users/hung/projects/target-project"
}
```

**Required fields:** `class`
**Optional fields:** `capabilities`, `crew` (search all if omitted), `target_machine` (auto-select if omitted), `task_id` (assign on boot), `project_path`

**Response:**
```json
{
  "status": "spawning",
  "agent": "gpu-server/target-project/viper",
  "machine": "gpu-server",
  "estimated_boot_time_s": 15
}
```

Spawns an agent daemon from a crew definition. Selects the best fit character by class → capabilities → model → machine capacity. Agent boots, cold-starts, and picks up the assigned task.

**Constraints:**
- Max concurrent agents per machine: `MINION_MAX_AGENTS` env var (default: 5)
- Spawn cooldown: 30 seconds minimum between spawns on same machine
- HP budget: won't spawn if estimated task token cost exceeds budget
- Remote spawn: requires SSH access + minion installed on target

---

### GET /capacity

**Auth:** Bearer token
**Response:**
```json
{
  "machines": [
    {
      "machine_id": "macbook-pro",
      "running_agents": 3,
      "max_agents": 5,
      "available_slots": 2,
      "specs": {"ram_gb": 32, "cpu_cores": 10}
    }
  ]
}
```

Shows which machines have room to spawn new agents.

---

### Auto-Teardown

Spawned agents auto-tear down when idle:
1. Agent completes task, no more work in queue
2. Idle timeout: 10 minutes (configurable) with no new assignment
3. Agent calls fenix-down, deregisters, daemon exits
4. Agent removed from `/who`

---

## Auth Model for Dashboard

The current cluster token approach works for API-to-API auth. For the dashboard UI:

1. **Option A (recommended):** Keep using the cluster token directly. The dashboard HTML prompts for it and stores in `localStorage`. This is already how the existing `GET /` dashboard works.

2. **Option B:** Add a `POST /auth/login` endpoint that validates the cluster token and issues a short-lived session token. This adds complexity but allows token rotation without disrupting active dashboard sessions.

Recommendation: Start with Option A. The current inline dashboard already uses this pattern successfully.

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `MINION_CLUSTER_TOKEN` | Bearer token for API auth | (none — auth disabled) |
| `MINION_NETWORK_INSECURE` | Set to `1` to disable TLS | (TLS on) |
| `MINION_NETWORK_PORT` | Override listen port | `8377` |
| `MINION_NETWORK_DB` | Override network DB path | `~/.minion/network.db` |

## Startup

```bash
# Generate TLS certs (first time only)
minion network gen-cert

# Start the server
MINION_CLUSTER_TOKEN=my-secret-token minion network serve

# Or insecure for local dev
MINION_NETWORK_INSECURE=1 minion network serve
```
