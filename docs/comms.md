# Comms — Agent Messaging

How minions talk to each other. All messaging goes through the `minion` CLI and SQLite.

## Core Flow

```
Agent A                    SQLite                   Agent B
   │                         │                        │
   ├── check-inbox ─────────►│                        │
   │◄── [] (empty) ─────────│                        │
   │                         │                        │
   ├── send --to B ─────────►│ INSERT message         │
   │                         │                        │
   │                         │       poll/check-inbox ─┤
   │                         │ SELECT unread ─────────►│
   │                         │ UPDATE read_flag=1      │
   │                         │                        │
```

## Send a Message

```bash
minion send-local --from alice --to bob --message "auth module is ready for review"
```

With CC (copies go to charlie, lead gets auto-CC'd):
```bash
minion send-local --from alice --to bob --message "auth fix done" --cc charlie
```

### Rules

1. **Inbox discipline** — sender must call `check-inbox` before sending. If unread messages exist, send is blocked.
2. **Battle plan required** — no sends without an active battle plan.
3. **Context freshness** — if agent hasn't called `set-context` within their class timeout, send is blocked.
4. **Auto-CC lead** — unless sender IS lead or recipient IS lead, the lead gets a CC copy automatically.
5. **moon_crash blocks** — if the moon_crash flag is set, all communication is restricted.

## Check Inbox

```bash
minion check-inbox --agent bob
```

Returns all unread messages, marks them as read. Output:

```json
{
  "messages": [
    {
      "id": 42,
      "from": "alice",
      "content": "auth module is ready for review",
      "timestamp": "2026-02-20T14:30:00",
      "is_cc": false
    }
  ]
}
```

## Broadcast

Send to all registered agents at once:

```bash
minion send-local --from leo --to all --message "everyone focus on the auth module"
```

Broadcast tracking prevents agents from seeing the same broadcast twice — uses `broadcast_reads` table.

## Poll (Daemon Mode)

Daemon agents don't call `check-inbox` directly. The daemon runner polls:

```bash
minion poll --agent alice --interval 5
```

Returns messages + tasks in one shot. The daemon builds an inline prompt with the inbox contents and invokes the agent.

## Message History

Read recent messages across all agents:

```bash
minion get-history --count 20
```

Purge old messages:

```bash
minion purge-inbox --agent alice --older-than-hours 2
```

## Context Updates

Agents must periodically report what they're doing:

```bash
minion set-context --agent alice --context "working on login flow" --hp 78
```

### Staleness Timeouts

| Class | Must update every |
|-------|-------------------|
| coder | 5 min |
| builder | 5 min |
| recon | 5 min |
| lead | 15 min |
| oracle | 30 min |

If stale, `send` is blocked until context is refreshed.

## Status

Agents can set a human-readable status:

```bash
minion set-status --agent alice --status "reviewing PR #42"
```

## Who's Online

```bash
minion who
```

Returns all registered agents with class, status, last_seen, transport.

## Trigger Words

Messages are scanned for trigger words on send. Include the word in any message and the system acts automatically:

| Trigger | Effect |
|---------|--------|
| `moon_crash` | Sets flag — blocks all task assignments, signals all daemons to exit |
| `stand_down` | Sets flag — daemons exit gracefully on next poll |
| `fenix_down` | Signal to dump session knowledge before context death |
| `sitrep` | Request status report (no auto-effect) |
| `rally` | Focus on target/zone (no auto-effect) |
| `retreat` | Pull back and reassess (no auto-effect) |
| `hot_zone` | Area is dangerous, proceed with caution (no auto-effect) |
| `recon` | Investigate before acting (no auto-effect) |

Example — emergency shutdown:

```bash
minion send-local --from leo --to all --message "moon_crash — everyone fenix_down NOW"
```

Clear emergency after resolution:

```bash
minion clear-moon-crash --agent leo
```

## Global Routing — Cross-Repo Messaging

Agents in different projects communicate via the coordinator DB as a router.

### Architecture

```
Coordinator DB (~/.minion/coordinator.db)
  Role: Address book. Maps agent name → project_path.
  NOT a message store. Zero message rows. Ever.

Local DB (<project>/.work/minion.db)
  Role: Message store + agent roster for one project.
  poll watches this DB only. All messages live here.
```

### How Global Send Works

```
gui-coder (parakeet-app)              coordinator              gpu-coder (parakeet-gpu)
         │                                 │                              │
         ├── send global --to gpu-coder ──►│                              │
         │                                 │ lookup project_path          │
         │                                 │ = /parakeet-gpu              │
         │                                 │                              │
         ├── sqlite3.connect(parakeet-gpu/.work/minion.db) ──────────────►│
         │   INSERT INTO messages (to=gpu-coder, content_file=...)        │
         │   write .work/inbox/gpu-coder/msg.md                           │
         │                                                                │
         │                                 │       poll (local DB only) ──┤
         │                                 │       sees new row, wakes up │
```

1. Sender runs `minion comms send global --from A --to B --message "..."`
2. CLI checks sender guards (inbox discipline, staleness) against sender's local DB
3. CLI looks up B's `project_path` in coordinator DB
4. CLI opens B's `.work/minion.db` directly and INSERTs the message
5. CLI writes message body to B's `.work/inbox/B/` filesystem
6. B's poll (watching only local DB) sees the new row and wakes up

### CWD Collection — How the Coordinator Learns project_path

Every CLI operation heartbeats the coordinator via `touch_coordinator_activity()`, which UPSERTs the agent with `os.getcwd()` as project_path.

| Entry Point | Local DB | Coordinator DB |
|---|---|---|
| `agent register` | INSERT/UPSERT | UPSERT with `os.getcwd()` |
| `send` (local) | auto-register | heartbeat via `touch_coordinator_activity` |
| `send global` | auto-register | heartbeat (on successful delivery) |
| `check-inbox` | UPDATE last_seen | heartbeat |
| `set-context` | UPDATE context | heartbeat |

### Locality Check

`send local` cross-checks the coordinator: if the target's `project_path` differs from the sender's `os.getcwd()`, the send is rejected with a suggestion to use `send global`. This prevents messages landing in dead local inboxes.

### Global Commands

```bash
# Send cross-repo
minion comms send global --from minion-coder --to gui-coder --message "..."

# List all agents across all projects
minion global who

# Prune stale agents from coordinator
minion global prune --older-than 6h

# Deregister from coordinator
minion global deregister --agent napoleon
```

### Auto-Prune

Agents inactive for 6+ hours are auto-pruned from the coordinator DB (checked at most once per 10 minutes during any `touch_coordinator_activity` call). Local `.work/minion.db` agents are pruned on the same threshold.

### WAL Snapshot Isolation

Since sender and recipient are different processes writing/reading the same SQLite file in WAL mode, statement ordering matters. All SELECTs in `check-inbox` and `_fetch_messages` run before any UPDATEs/INSERTs. An UPDATE starts an implicit transaction whose read snapshot would miss messages committed after the snapshot was taken.

### Invariants

- Every message has exactly one home: the recipient's local DB
- The coordinator DB stores zero messages (no messages table)
- poll never queries the coordinator — everything it needs is in `.work/`
- An agent can receive messages from any project without knowing about the sender's project
- Agent names are globally unique across all projects (enforced at registration)

## DB Tables

```sql
-- Agent registry
agents (name PK, agent_class, model, status, context_summary,
        transport, last_seen, last_inbox_check, context_updated_at,
        hp_input_tokens, hp_output_tokens, hp_tokens_limit, ...)

-- Messages
messages (id, from_agent, to_agent, content_file, timestamp,
          read_flag, is_cc, cc_original_to)

-- Broadcast dedup
broadcast_reads (agent_name, message_id)

-- Emergency flags
flags (key PK, value, set_by, set_at)
  -- keys: moon_crash, stand_down
```

## Common Patterns

### Agent-to-Agent

```bash
# Alice finishes work, reports to lead
minion check-inbox --agent alice
minion send-local --from alice --to leo --message "task #5 complete, auth module fixed"
```

### Lead Assigns Work via Message

```bash
minion send-local --from leo --to alice --message "pick up task #7, frontend auth form"
```

### Agent Asks Oracle for Help

```bash
minion send-local --from alice --to donnie --message "what's the auth middleware pattern in this codebase?"
```

### Broadcast Status Update

```bash
minion send-local --from leo --to all --message "rally — everyone focus on the deploy pipeline"
```
