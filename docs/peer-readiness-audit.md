# Peer-to-Peer Readiness Audit — Network Tier

Assessment of whether the current network tier (`src/minion/network/`) can support a peer-to-peer gossip model where multiple machines each run `minion network serve`.

## 1. Can ANY machine run `minion network serve`?

**Yes.** No hardcoded paths, IPs, or machine-specific config in `serve()`. The server binds `0.0.0.0`, uses `~/.minion/network.db` (local to each machine), and reads `MINION_CLUSTER_TOKEN` from env. Any machine with minion installed can start a server.

## 2. Singleton assumptions — is there a "one central server" assumption?

**Yes — in the client and routing, not the server.**

| Component | Singleton assumption | Detail |
|-----------|---------------------|--------|
| `client.py` | `MINION_NETWORK_URL` is a single URL | Client connects to exactly one server. No concept of multiple peers. |
| `comms.py` routing | Falls through to one API GLOBAL endpoint | `send_global()` calls `net.send()` against one URL. If the target agent is on a different server, delivery fails. |
| `polling.py` | Checks one network inbox | `net.check_inbox()` calls one server. Messages on a different server are invisible. |
| `register()` in `comms.py` | Registers on one network server | `net.register()` hits one URL. Agent is unknown to other servers. |

**The server itself has zero singleton assumptions.** Each instance is independent with its own `network.db`. The bottleneck is entirely client-side routing.

## 3. Could a second server discover agents from the first?

**Not today.** There is no:
- Peer discovery protocol
- Server-to-server registration or sync
- Gossip mechanism for propagating agent registries
- `/peers` endpoint for listing known servers

Each server's `agents` table is isolated. Agent "test-mac" registered on Server A is invisible to Server B.

## 4. Could agent registries merge?

**Schema supports it, but no merge logic exists.**

The `agents` table schema:
```sql
name TEXT PRIMARY KEY, agent_class TEXT, host TEXT, project_path TEXT, machine_id TEXT, registered_at TEXT, last_seen TEXT
```

- `name` is the PK — collision on same-name agents across servers
- `machine_id` and `host` fields exist and could disambiguate
- No `origin_server` or `source_peer` column to track where a record came from
- No vector clock or timestamp-based conflict resolution

**What works:** UPSERT on `name` means a naive merge (bulk INSERT OR REPLACE) would work for non-conflicting names. `last_seen` could serve as a "latest wins" tiebreaker.

**What would break:** Two servers both have an agent named "napoleon" from different machines — one would overwrite the other. Need either namespacing (`machine_id:name`) or a conflict resolution policy.

## 5. Threading/state assumptions that would break with multiple servers

| Issue | Detail |
|-------|--------|
| `_DB_LOCK` is process-local | Each server has its own threading lock. Fine for single-server, irrelevant for multi-server (each has its own DB). |
| `_Handler.db_path` is a class variable | Set once at startup. Would need to be instance-level for running multiple servers in one process (unlikely need). |
| Message IDs are `AUTOINCREMENT` per server | Server A and Server B both have message ID 1. Merging message tables would collide. Need UUIDs or `(server_id, local_id)` composite keys. |
| `read_flag` is server-local | Agent reads message on Server A — Server B still thinks it's unread. No read-state sync. |

## Summary: What works today for P2P

| Aspect | Status |
|--------|--------|
| Any machine can run a server | Works |
| Server code is stateless per-request | Works |
| Agent schema has machine identity fields | Works |
| TLS works per-server independently | Works |
| Auth token can be shared across a cluster | Works |

## What needs to change for P2P gossip

| Change | Effort | Priority |
|--------|--------|----------|
| **Client supports multiple peer URLs** — `MINION_NETWORK_PEERS=url1,url2,...` instead of single URL. Client queries all peers for /who and /inbox, sends to the peer that owns the target agent. | Medium | High |
| **Peer sync endpoint** — `POST /sync` accepts a batch of agent registrations + messages from another server. Merges into local DB with conflict resolution. | Medium | High |
| **Message UUIDs** — Replace `AUTOINCREMENT` IDs with UUIDs so messages can merge across servers without collision. | Low | High |
| **Agent namespacing** — Either enforce globally unique names (current approach) or namespace as `machine:name`. Current unique-name enforcement at the coordinator level would need to span all peers. | Low | Medium |
| **Read-state gossip** — When an agent reads a message on Server A, propagate read-flag to Server B. Or accept that read-state is local (simpler, acceptable for small clusters). | Low | Low |
| **Peer discovery** — Background thread that periodically queries known peers for their peer lists, building a mesh. Or static config (`MINION_NETWORK_PEERS`). | Medium | Medium |
| **Routing table** — Cache which agent lives on which peer, so sends go directly to the right server instead of querying all. Invalidated on agent re-registration. | Medium | Medium |

## Recommendation

The current design is **hub-and-spoke** — one coordinator, N clients. This is correct for the immediate use case (Mac + one Debian server).

For P2P, the lowest-effort path:
1. Add `MINION_NETWORK_PEERS` (comma-separated URLs) to the client
2. Client queries all peers for /who, builds a local routing cache
3. Send routes to the peer that owns the target agent
4. Switch message IDs to UUIDs
5. Skip full gossip/sync — let each server be authoritative for its local agents

This gives multi-server routing without the complexity of bidirectional sync. Each server owns its agents. Clients know about all servers.
