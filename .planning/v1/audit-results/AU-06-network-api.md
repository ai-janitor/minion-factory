# AU-06 Network API Audit Results

**Auditor:** AU-06 (Network API Deep Dive)
**Date:** 2026-03-09
**Scope:** `src/minion/network/` — 20 Python files (server, router, auth, client, handlers/, discovery, project_db, fqn, db_schema, outbox, dashboard)

---

## Server Architecture

### Request Flow

```
Client → TCP socket (0.0.0.0:port)
       → HTTPServer (stdlib http.server.HTTPServer)
       → _Handler (BaseHTTPRequestHandler subclass)
       → do_GET / do_POST
       → TLS check (ssl.SSLContext if certs present, else plain HTTP)
       → Dashboard shortcut: path == "/" → inline HTML response (no auth)
       → Auth check: _check_token(headers, token) → 401 if invalid
       → POST-specific: /api/login bypasses auth (_POST_NO_AUTH set)
       → Router dispatch: _router.route_get(path) / route_post(path)
       → Handler function: fn(handler, db_path, **captured_params)
       → _json_response(status, data) → JSON body to client
       → If no route match: 404 {"error": "Not found: {path}"}
```

### Key Design Decisions

1. **Single-threaded by default** — `HTTPServer` (not `ThreadingHTTPServer`). Each request blocks.
2. **Class-level state** — `_Handler.db_path`, `_Handler.token`, `_Handler._router` are class attributes set once at startup.
3. **_DB_LOCK** — module-level `threading.Lock` guards all network DB writes. Not needed for single-threaded server unless `ThreadingHTTPServer` is used later.
4. **TLS default-on** — falls back to HTTP if certs missing (with warning).
5. **Router** — declarative dispatch table with `{param}` pattern matching via regex.

---

## Auth Model

### Token Mechanism

| Aspect | Current State |
|--------|---------------|
| Token source | `MINION_CLUSTER_TOKEN` env var or `--token` CLI arg |
| Transport | `Authorization: Bearer {token}` header |
| Validation | Simple string equality: `auth == f"Bearer {expected}"` |
| No-token mode | If token is empty string, ALL requests pass auth (dev mode) |
| Timing safety | **NO** — uses `==` comparison, not `hmac.compare_digest()` |
| Per-endpoint auth | Binary: has-valid-token or not. No role/scope/per-endpoint |
| AuthMixin status | **Defined in auth.py but NOT wired** — server.py uses inline `_check_token()` |
| Dashboard | Served without auth at `/`; JS uses localStorage token for API calls |
| Login bridge | `/api/login` POST accepts password == cluster_token, returns token |

### AuthMixin vs _check_token Discrepancy

- `auth.py` exports `check_token()` (standalone function) and `AuthMixin` (mixin class with `require_auth()` method)
- `server.py` defines its own `_check_token()` — identical logic, different location
- `_Handler` does NOT inherit from `AuthMixin`
- Result: auth.py is dead code — defined, documented, but never imported by server.py

### Security Assessment

- **No-token mode is documented** — prints warning at startup: "auth: NONE (set MINION_CLUSTER_TOKEN for security)"
- **Token returned in /api/login response** — the actual cluster token is sent back to the client. If the token leaks from localStorage, it's game over.
- **No token rotation** — single shared secret, no expiry
- **No rate limiting** on auth attempts

---

## Endpoint Inventory

| Endpoint | Method | Handler | Validates Input? | Auth? | Response Format |
|----------|--------|---------|------------------|-------|-----------------|
| `/` | GET | (inline) | N/A | No | HTML |
| `/health` | GET | core.handle_health | N/A | Yes | JSON |
| `/who` | GET | core.handle_who | Query params parsed | Yes | JSON |
| `/messages/recent` | GET | core.handle_recent_messages | N/A | Yes | JSON |
| `/inbox/{agent}` | GET | core.handle_inbox | Agent from URL | Yes | JSON |
| `/register` | POST | core.handle_register | name required, others optional | Yes | JSON |
| `/send` | POST | core.handle_send | from/to/message required | Yes | JSON |
| `/projects` | GET | projects.handle_list_projects | N/A | Yes | JSON |
| `/projects/{name}/agents` | GET | projects.handle_project_agents | N/A | Yes | JSON |
| `/projects/{name}/tasks` | GET | projects.handle_project_tasks | Query params parsed | Yes | JSON |
| `/projects/{name}/tasks/{id}/lineage` | GET | projects.handle_task_lineage | task_id validated int | Yes | JSON |
| `/projects/{name}/messages` | GET | projects.handle_project_messages | Query params parsed | Yes | JSON |
| `/projects/{name}/raid-log` | GET | projects.handle_project_raid_log | N/A | Yes | JSON |
| `/projects/{name}/flows/{type}` | GET | flows.handle_get_flow | flow_type sanitized regex | Yes | JSON |
| `/projects/{name}/requirements` | GET | requirements.handle_list_requirements | Query params parsed | Yes | JSON |
| `/projects/{name}/requirements/{id}/lineage` | GET | requirements.handle_requirement_lineage | id validated int | Yes | JSON |
| `/projects/{name}/backlog` | GET | backlog.handle_list_backlog | Query params parsed | Yes | JSON |
| `/overview` | GET | overview.handle_overview | N/A | Yes | JSON |
| `/alerts` | GET | overview.handle_alerts | N/A | Yes | JSON |
| `/capacity` | GET | scaling.handle_capacity | N/A | **Not registered** | N/A (stub) |
| `/spawn` | POST | scaling.handle_spawn | N/A | **Not registered** | N/A (stub) |
| `/api/login` | POST | compat.handle_api_login | password from body | **No** | JSON |
| `/api/agents` | GET | compat → project_agents | Delegates | Yes | JSON |
| `/api/tasks` | GET | compat → project_tasks | Delegates | Yes | JSON |
| `/api/task-lineage/{id}` | GET | compat → task_lineage | Delegates | Yes | JSON |
| `/api/messages` | GET | compat → project_messages | Delegates | Yes | JSON |
| `/api/raid-log` | GET | compat → project_raid_log | Delegates | Yes | JSON |
| `/api/flows/{type}` | GET | compat → get_flow | Delegates | Yes | JSON |
| `/api/sprint` | GET | compat.handle_api_sprint | N/A | Yes | JSON |
| `/api/logs` | GET | compat.handle_api_logs | N/A | Yes | JSON |
| `/api/logs/{agent}` | GET | compat.handle_api_agent_log | agent sanitized regex | Yes | JSON |

**Total: 30 endpoints (28 active, 2 stub/not-registered)**

---

## Filled Checklist

### AI-First API (aspirational per UF-001)

| Rule | Status | Evidence | Aspirational? |
|------|--------|----------|---------------|
| ROUTE-1 | NO | Routes are resource-based (`/projects/{name}/agents`, `/health`, `/register`), not verb-prefix (`/search`, `/read`, `/list`) | Yes |
| ROUTE-2 | NO | All responses are `application/json` (except `/` HTML). No prefix-based Content-Type | Yes |
| ROUTE-3 | NO | Single `Router` class, not per-prefix routers. Routes registered per-domain module, not per-prefix | Yes |
| ROUTE-4 | NO | No `/search` or `/read` endpoints returning `text/markdown` | Yes |
| ROUTE-5 | NO | All endpoints return JSON but not via `/list` or `/push` prefixes | Yes |
| ROUTE-6 | NO | No `/pull` endpoint returning binary | Yes |
| CONF-1 | N/A | No search/semantic matching in current API — pure CRUD/query | Yes |
| CONF-2 | N/A | No confidence scoring | Yes |
| CONF-3 | N/A | No multi-option responses | Yes |
| CONF-4 | N/A | No fallback content | Yes |
| CONF-5 | YES | Endpoints return useful data in one call (e.g., `/who` returns enriched agents with presence, availability, current_task) | No |
| TOK-1 | NO | No documented token budgets | Yes |
| TOK-2 | NO | No response truncation (messages truncated to 200 chars in `/projects/{name}/messages` — partial) | Yes |
| TOK-3 | NO | No smart truncation | Yes |
| TOK-4 | NO | No pointers to full content | Yes |
| TOK-5 | NO | No X-Token-Count headers | Yes |
| TOK-6 | NO | `/messages/recent` hardcoded LIMIT 20; `/projects/{name}/tasks` caps at 500. Partial. | Yes |
| CLI-1 | NO | No `/install/cli` endpoint | Yes |
| CLI-2 | NO | No self-serving CLI generation | Yes |
| CLI-3 | NO | CLI is a separate package, not served by API | Yes |
| CLI-4 | NO | No auto-generated CLI from routes | Yes |
| CLI-5 | NO | No version check against `/health` | Yes |
| CLI-6 | NO | No self-update mechanism | Yes |
| SPEC-1 | NO | No `/openapi.json` endpoint — stdlib http.server, not FastAPI | Yes |
| SPEC-2 | NO | No `/docs` Swagger UI | Yes |
| SPEC-3 | NO | No ENDPOINTS dict — routes registered per-module via `register(router)` pattern. Route table is implicit. | No (current deficiency) |
| SPEC-4 | YES | `/health` endpoint exists, returns `{"status": "ok", "timestamp": "..."}`. Missing version field. | No |
| INFRA-1 | NO | No docker-compose.yml | Yes |
| INFRA-2 | NO | No Makefile with standard commands | Yes |
| INFRA-3 | NO | No .env.example | No (current deficiency) |
| INFRA-4 | NO | Config via `os.environ.get()` directly, not pydantic-settings | Yes |
| INFRA-5 | NO | No Docker configs | Yes |
| DOC-1 | YES | CLAUDE.md has install instructions and dev reference | No |
| DOC-2 | NO | No bootstrap auth guide. Bearer token setup undocumented for first-time network users | No (current deficiency) |
| DOC-3 | YES | CLI examples in CLAUDE.md cover first request patterns | No |
| DOC-4 | NO | No interactive docs (none exist) | Yes |
| DOC-5 | YES | Top workflows documented (agent lifecycle, polling protocol, crew management) | No |
| DOC-6 | N/A | Not verified in audit | Yes |
| PLAN-1 | N/A | Retrospective audit — not evaluating planning discipline | N/A |
| PLAN-2 | YES | Implementation roadmap exists (iterative decomposition DAG) | N/A |
| PLAN-3 | N/A | Not observable in retrospective audit | N/A |
| PLAN-4 | N/A | Not observable in retrospective audit | N/A |

**Summary: YES: 5, NO: 26 (6 current deficiency, 20 aspirational), N/A: 6**

---

### CS Foundations — Security (CS-SEC)

| Rule | Status | Evidence |
|------|--------|----------|
| SEC-1 Trust boundaries | YES | Two clear boundaries: (1) CLI is trusted local, (2) Network API is untrusted boundary with bearer token. Dashboard at `/` is unauthenticated but read-only HTML. `/api/login` POST is intentionally unauthenticated. |
| SEC-2 Authentication | NO | Auth mechanism exists (bearer token) but: (a) `auth.py` AuthMixin NOT wired — server.py uses inline `_check_token()`; (b) token comparison uses `==` not `hmac.compare_digest()` (timing attack vector); (c) `/api/login` returns the actual cluster token in response body |
| SEC-3 Authorization | NO | Binary authorization only — has valid token or doesn't. No per-endpoint, per-role, or per-agent authorization. Any authenticated caller can `/register`, `/send`, read all projects, all messages, all agents. No RBAC. |
| SEC-4 Secrets management | YES | Token in env var (`MINION_CLUSTER_TOKEN`), not in code. TLS key at `~/.minion/tls/key.pem` with `chmod 0o600`. Adequate for local/dev. |
| SEC-5 Input validation | NO | **Critical gap.** (a) `_read_body()` reads `Content-Length` bytes with no upper bound — attacker can set Content-Length: 10GB; (b) `_parse_json_body()` parses without size limit; (c) `handle_register` does `body.get()` for 20+ fields with no type validation; (d) `handle_send` only checks empty strings, no length limits on message content; (e) Query params parsed via `parse_qs` with no validation — `int()` casts can raise but are caught by bare `except`; (f) Path params like `{agent}` in `/inbox/{agent}` are passed directly to SQL as parameterized queries (safe from injection) but no format validation; (g) No Content-Type validation on incoming requests |

---

### CS Foundations — Communication (CS-COMM, subset)

| Rule | Status | Evidence |
|------|--------|----------|
| COMM-2 Integration points | YES | Integration points well-documented: network API ↔ project-local SQLite DBs, network API ↔ filesystem (log files, sprint.json, raid-log entries, message content_files). Failure modes handled (file not found → "(file not found)", DB missing → 404). |
| COMM-4 API style | YES | REST-like HTTP with custom router. Resource-based URLs (`/projects/{name}/agents`). Consistent GET=read, POST=write. |
| COMM-5 Serialization | YES | JSON everywhere for API responses. `application/json` Content-Type consistently set. HTML only for dashboard root. |

---

### CS Foundations — Error & Failure Modes (CS-ERR, subset)

| Rule | Status | Evidence |
|------|--------|----------|
| ERR-1 Failure taxonomy | NO | No formal taxonomy. Three implicit patterns: (1) `_json_response(4xx, {"error": "..."})` for client errors; (2) `_json_response(500, {"error": f"DB query failed: {e}"})` for server errors; (3) bare `except Exception: pass` that silently swallows errors (overview.py:98, alerts.py:201, core.py:117). No custom exception hierarchy. |
| ERR-5 Observability | NO | One structured log line in `_Handler.log_message()` — JSON with ts, level, component, client, message. But: (a) only logs HTTP request metadata, not business events; (b) no logging of errors, auth failures, or handler exceptions; (c) handler errors caught by `except Exception: pass` are invisible; (d) no request ID for correlation; (e) print() used for startup messages, not logging module |

---

### Clean Architecture (subset)

| Rule | Status | Evidence |
|------|--------|----------|
| CA-DEP-1 Dependencies inward | YES | network/ imports from business logic (tasks, backlog, requirements tables via SQL), not the reverse. cli/ imports network/client.py. No outward dependency violations. |
| CA-BOUND-3 Data crossing boundaries | NO | Dicts cross the HTTP boundary everywhere. No formal DTOs, no response schemas, no request schemas. Handler functions return raw `dict(row)` from SQLite — all columns exposed including internal ones. Example: `/who` returns every column from the agents table including `crash_rate`, `total_input_tokens`, `heartbeat_latency_ms`. No filtering of internal-only fields. |

---

### Pragmatic Programmer (subset)

| Rule | Status | Evidence |
|------|--------|----------|
| PP-CRAFT-1 No programming by coincidence | YES | HTTP handling is intentional. Router is deliberately designed with PSEUDO comments preserved. Handler modules have clear purpose docstrings. TLS setup is documented. |
| PP-DECOUPLE-1 No train wrecks | YES | No significant method chains. Handler functions receive `handler` and `db_path` directly. Dict access chains (`body.get()`, `dict(row)`) are appropriate for the data shape. |
| PP-DECOUPLE-5 Config externalized | NO | Partially. Token from env var (good). Port from CLI arg (good). But: (a) `_PRESENCE_ONLINE_MINS = 5` and `_PRESENCE_STALE_MINS = 30` are hardcoded in core.py; (b) `MAX_CACHED_CONNECTIONS = 10` and `CONNECTION_TTL_SECONDS = 300` hardcoded in project_db.py; (c) HP tier thresholds (60%, 30%) hardcoded in overview.py and alerts.py; (d) message limit (20) hardcoded in `/messages/recent`; (e) client timeout (10s) hardcoded in client.py |

---

### Implementation Coding Core (subset)

| Rule | Status | Evidence |
|------|--------|----------|
| IC-HDR-1 PURPOSE header | NO | 0/20 files use mandated `PURPOSE:` format. All files have module-level docstrings instead. router.py has closest to scaffold format. Reference SF-01. |
| IC-HDR-2 RESPONSIBILITIES header | NO | 0/20 files. Some docstrings describe responsibility informally. Reference SF-01. |
| IC-HDR-3 NOT RESPONSIBLE FOR | NO | 0/20 files. Reference SF-01. |
| IC-HDR-4 DEPENDENCIES header | NO | router.py has partial scaffold (`Implementation order: 3rd`). 0 formal DEPENDENCIES headers. Reference SF-01. |
| IC-HDR-5 Headers permanent | YES | PSEUDO comments preserved in router.py, discovery.py, project_db.py, db_schema.py, fqn.py, overview.py, requirements.py, backlog.py, scaling.py. These are the blueprints per project philosophy. |
| IC-DATA-1 Schemas defined | NO | No defined schemas for any request or response. Handlers use manual `body.get()`. Response shapes are implicit (whatever `dict(row)` returns from SQLite). |
| IC-DATA-2 Runtime validation | NO | No runtime schema validation. JSON parsed directly from body. Only validation: `name` required in `/register`, `from`/`to`/`message` required in `/send`. Types never checked. |
| IC-DATA-3 Validation errors | NO | No expected-vs-received error messages. Errors are generic: "Invalid JSON body", "name is required". No indication of what type was expected. |
| IC-DATA-4 Central schemas | NO | No central schema definitions. Each handler independently decides what fields to extract from body and what to return. |
| IC-DATA-5 Integration tests | NO | `test_network_api_route_integrity.py` tests route existence and handler callability, not payloads. No tests verify request/response schemas match actual behavior. |

---

## Findings

| # | Rule(s) | Severity | Affected Files | Description | Remediation |
|---|---------|----------|----------------|-------------|-------------|
| F-01 | SEC-2 | **Major** | `server.py:37-42`, `auth.py:18-34` | **AuthMixin defined but NOT wired.** `server.py` defines its own `_check_token()` instead of using `auth.py`'s `check_token()` or `AuthMixin.require_auth()`. Two implementations of identical logic exist. `auth.py` is dead code. | Wire `AuthMixin` into `_Handler` inheritance or remove `auth.py` and keep `_check_token`. One canonical auth path. |
| F-02 | SEC-2 | **Major** | `server.py:42`, `auth.py:33` | **Token comparison uses `==` (timing-unsafe).** Both `_check_token()` and `check_token()` compare tokens with `==`. An attacker can use timing side-channel to extract the token byte-by-byte. | Replace with `hmac.compare_digest(auth, f"Bearer {expected}")` in both locations. |
| F-03 | SEC-5 | **Critical** | `server.py:72-74` | **No Content-Length limit on request body.** `_read_body()` reads exactly `Content-Length` bytes. Attacker can send `Content-Length: 10737418240` (10GB) and the server will attempt to allocate and read that much memory. | Add a maximum body size check (e.g., 10MB) before `rfile.read(length)`. Return 413 if exceeded. |
| F-04 | SEC-5, IC-DATA-1 | **Major** | `handlers/core.py:225-316` | **No input validation on /register.** Accepts 20+ fields via `body.get()` with no type checking, no length limits, no enum validation. `agent_class` is not validated against known classes. `capabilities`, `machine_specs`, `runtimes` are JSON-serialized without schema validation. Any string can be stored. | Define a schema (dataclass or dict with type+required+max_length). Validate before writing. |
| F-05 | SEC-5 | **Major** | `handlers/core.py:319-354` | **No message content length limit on /send.** `content = body.get("message", "").strip()` — unlimited message size. Can fill the DB with arbitrarily large messages. | Add `max_length` check on message content (e.g., 100KB). Return 400 if exceeded. |
| F-06 | SEC-3 | **Moderate** | `server.py:93-136` | **No per-endpoint authorization.** All authenticated users have full access to all endpoints: register agents, send messages as anyone, read all projects' data. No role or scope restrictions at the network tier. | For multi-user/multi-team deployment: add role-based access. For current single-team usage: acceptable risk, document as intentional. |
| F-07 | ERR-1, ERR-5 | **Moderate** | `handlers/overview.py:98`, `handlers/overview.py:201`, `handlers/core.py:116-117` | **Silent error swallowing.** Multiple `except Exception: pass` blocks that discard errors without logging. In `handle_overview`, if a project DB query fails, it's silently skipped. In `_get_current_task`, project DB failures are invisible. | At minimum, log the exception. Better: return partial results with error annotations. |
| F-08 | PP-DRY-1, CA-BOUND-3 | **Moderate** | `handlers/projects.py:35-48`, `handlers/requirements.py:25-35`, `handlers/backlog.py:46-53` | **`_resolve_or_404` duplicated.** Three handler modules define their own `_resolve_or_404()` helper with identical logic (resolve project path, get DB, send 404). Backlog doesn't even use a helper — it inlines the logic. | Extract to a shared utility in `handlers/__init__.py` or a `handlers/_common.py` module. |
| F-09 | IC-SCALE-2 | **Moderate** | `server.py:156` | **No timeout on openssl subprocess call.** `gen_cert()` calls `subprocess.run(["openssl", ...], check=True)` with no timeout. If openssl hangs, the server startup blocks forever. | Add `timeout=30` to `subprocess.run()`. |
| F-10 | SEC-5 | **Moderate** | `handlers/compat.py:152-164` | **Unbounded file read in /api/sprint.** `handle_api_sprint` reads entire `sprint.json` file with no size limit. If the file is large, server memory spikes. Similarly, `/api/logs` reads all `.log` files (capped at last 200 lines each, but no file count limit). | Add file size check before reading. Cap number of log files scanned. |
| F-11 | SEC-5 | **Low** | `handlers/projects.py:226-229` | **Unbounded file read in message content_file.** `handle_project_messages` reads `content_file` from filesystem and truncates to 200 chars — good truncation, but the file is fully read into memory first. | Use `f.read(201)` instead of `f.read()` + truncate. |
| F-12 | SEC-5 | **Low** | `handlers/projects.py:256-259` | **Unbounded file read in raid-log entry_file.** `handle_project_raid_log` reads entire `entry_file` with no truncation or size limit. | Add size limit or truncation. |
| F-13 | SPEC-4 | **Low** | `handlers/core.py:37-39` | **/health missing version field.** Returns `{"status": "ok", "timestamp": "..."}` but no `version` field for clients to verify compatibility. | Add `"version": "0.1.0"` (or read from `pyproject.toml`). |
| F-14 | PP-DECOUPLE-5 | **Low** | `handlers/core.py:52-53`, `project_db.py:29-30`, `handlers/overview.py:62` | **Magic numbers hardcoded.** Presence thresholds (5/30 min), cache limits (10 connections, 300s TTL), HP tier boundaries (60%/30%), message limits (20/50/200/500) are all hardcoded constants with no configuration path. | Extract to a config module or make overridable via env vars. |
| F-15 | CONSIST-4 | **Low** | `handlers/core.py:260-312` | **Register upsert not idempotent for all fields.** `ON CONFLICT DO UPDATE SET agent_class = COALESCE(NULLIF(excluded.agent_class, 'coder'), agents.agent_class)` — if agent re-registers with class "coder" (the default), it preserves the old class. This is intentional but non-obvious. If an agent actually IS class "coder", re-registration won't update it. | Document the COALESCE behavior. Consider using NULLIF only for the empty string, not for the default value. |
| F-16 | COMM-2 | **Low** | `handlers/scaling.py:25-26` | **Scaling endpoints registered as pass (no-op).** `register()` does `pass` — `handle_spawn` and `handle_capacity` exist but are never wired to the router. They raise `NotImplementedError` if somehow called. | Either register with 501 responses or remove until implemented. Current state is confusing — code exists but is unreachable. |
| F-17 | IC-HDR-1 through IC-HDR-4 | **Major (systemic)** | All 20 files | **No formal comment headers.** Zero files use mandated PURPOSE/RESPONSIBILITIES/NOT RESPONSIBLE FOR/DEPENDENCIES format. Module docstrings exist on all files. Reference SF-01 from AU-00. | Systemic — same finding as SF-01. Address across entire codebase. |

---

## Strengths

1. **Consistent JSON response pattern.** Every handler uses `handler._json_response(status, data)` — uniform Content-Type, Content-Length, encoding. No handler writes raw bytes or forgets headers.

2. **Parameterized SQL everywhere.** All SQL queries use `?` placeholders — zero string interpolation in SQL. No SQL injection vectors despite the lack of input validation. Critical security strength.

3. **PSEUDO comments preserved.** router.py, discovery.py, project_db.py, db_schema.py, fqn.py, overview.py, requirements.py, backlog.py all retain PSEUDO comments documenting the intended logic flow. This is the scaffold-first discipline working as designed.

4. **TLS default-on.** Server defaults to HTTPS with self-signed cert, requiring explicit opt-out (`MINION_NETWORK_INSECURE=1`) for plain HTTP. Good security posture for a network API.

5. **Project DB connection cache.** `project_db.py` implements a proper LRU cache with TTL (5 min), max size (10), read-only connections (`?mode=ro`), and thread-safe eviction. Well-engineered for the use case.

6. **Declarative routing with pattern matching.** Router uses `{param}` syntax compiled to regex with named groups. Clean separation: routes registered per-module, dispatch is centralized. First-match-wins with duplicate detection in tests.

7. **Client mirrors server 1:1.** `client.py` has a method for every server endpoint. Client method signatures match server URL patterns. The `_request` helper handles TLS skip, bearer auth, JSON encode/decode, and error wrapping consistently.

8. **Error dict return pattern in client.** `NetworkClient._request()` never raises — returns `{"error": "..."}` for all failure modes (HTTP errors, network unreachable, generic exceptions). Callers don't need try/except.

9. **Migration system for schema evolution.** `db_schema.py` handles fresh installs (`init_db`), column additions (`migrate_db`), and PK migration (`migrate_to_composite_pk`) with create-copy-swap pattern. All idempotent.

10. **Dashboard served inline.** Single HTML file with inline CSS/JS — zero external dependencies, no build step, no CORS issues. Token auth via localStorage is pragmatic for a dev tool.

11. **Composite PK migration is well-designed.** `migrate_to_composite_pk()` uses create-copy-swap with COALESCE backfill for NULL machine_id/project_path. Idempotent (checks `_has_composite_pk` first).

12. **FQN resolution with 3-tier fallback.** `fqn.py` provides intelligent agent name resolution: exact FQN match → same machine+project → same machine → global. Returns structured errors with match suggestions for ambiguous names.

---

## Boundary Check: B-04 (CLI Client <-> Network API)

### Endpoint Contract Consistency

| Client Method | Server Endpoint | Match? | Notes |
|---------------|-----------------|--------|-------|
| `register()` | `POST /register` | YES | Client sends name, agent_class, host, project_path, machine_id. Server accepts all. |
| `send()` | `POST /send` | YES | Client sends from, to, message. Server expects from, to, message. |
| `check_inbox()` | `GET /inbox/{agent}` | YES | Agent name in URL path. |
| `who()` | `GET /who` | YES | No params needed. |
| `health()` | `GET /health` | YES | No params needed. |
| `list_projects()` | `GET /projects` | YES | Direct match. |
| `project_agents()` | `GET /projects/{name}/agents` | YES | Name in URL path. |
| `project_tasks()` | `GET /projects/{name}/tasks` | YES | Filters as query params via `_build_query_string`. |
| `task_lineage()` | `GET /projects/{name}/tasks/{id}/lineage` | YES | task_id in URL path. |
| `project_messages()` | `GET /projects/{name}/messages` | YES | Filters as query params. |
| `project_raid_log()` | `GET /projects/{name}/raid-log` | YES | Direct match. |
| `project_flow()` | `GET /projects/{name}/flows/{type}` | YES | flow_type in URL path. |
| `project_requirements()` | `GET /projects/{name}/requirements` | YES | Filters as query params. |
| `requirement_lineage()` | `GET /projects/{name}/requirements/{id}/lineage` | YES | requirement_id in URL path. |
| `project_backlog()` | `GET /projects/{name}/backlog` | YES | Filters as query params. |
| `overview()` | `GET /overview` | YES | Direct match. |
| `alerts()` | `GET /alerts` | YES | Direct match. |
| `capacity()` | `GET /capacity` | **MISMATCH** | Client has method, but server endpoint is NOT registered (scaling.py register() does `pass`). Client call will get 404. |

### Client Error Handling

- Timeout: `urlopen(req, timeout=10)` — 10 second timeout on all requests. **Good.**
- Connection error: `urllib.error.URLError` caught → `{"error": "Network unreachable: ..."}`. **Good.**
- HTTP errors: `urllib.error.HTTPError` caught, body parsed for JSON error. **Good.**
- TLS: `_insecure` flag disables cert verification for self-signed certs. **Good.**
- No retry/backoff: Client makes one attempt, returns error dict. **Acceptable for CLI, noted in SF-07.**

### Assessment

Client-server contract alignment is excellent — 17/18 endpoints match perfectly. The only mismatch is `capacity()` where the client has a method for an unregistered server endpoint (F-16). The client's error handling is thorough and non-throwing.
