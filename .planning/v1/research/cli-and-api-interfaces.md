# CLI and Network API Interface Survey

## CLI (Click-based)

### Structure
- Root group in main.py, 18 command modules + 1 aliases module
- Registration: each *_cmds.py exports register_commands(cli)
- Noun-verb pattern: minion agent register, minion task create, minion comms send local

### Output
- Single output() function in output.py handles JSON/human/compact
- JSON is DEFAULT (correct for agent consumption) — no --json flag needed
- --human flag for human-readable, --compact for terse agent injection
- No --quiet flag (--silent on check-inbox is closest)

### Help
- --help at every level (Click automatic)
- Good help text with \b literal blocks for examples
- minion docs command generates CLI reference from Click introspection

### Interactive Prompts
- ZERO — fully non-interactive, designed for agents

### Exit Codes
- Partial: 0=success, 1=error (all errors), poll has 0/1/3, task check-work has 0/1
- Gap: no distinction between auth failure vs not found vs validation

### Config Cascade
- flags > env vars > hardcoded defaults
- No config file layer (no ~/.minionrc or minion.toml)
- Env vars: MINION_DB_PATH, MINION_CLASS, MINION_AGENT_NAME, etc.

### Minor Issues
- Some top-level commands break noun-verb: deregister, rename, interrupt, resume on root
- Hidden legacy aliases in aliases.py for backward compat

## Network API (stdlib http.server — NOT FastAPI)

### Architecture
- stdlib HTTPServer + BaseHTTPRequestHandler — zero external deps
- Custom Router class with {param} pattern matching
- Port 8377 default, optional TLS (self-signed)
- SQLite with WAL + threading.Lock

### Endpoints
- GET /health — liveness (status + timestamp)
- GET /who — agent list with presence
- GET /inbox/{agent}, POST /register, POST /send — core ops
- GET /projects, /projects/{name}/agents, /tasks, /messages — project queries
- GET /overview, /alerts — system-wide aggregation
- /api/* compat routes — React frontend bridge

### Auth
- Bearer token from MINION_CLUSTER_TOKEN env
- No token configured = all requests pass (dev mode)
- AuthMixin defined but NOT wired — server.py still uses inline _check_token

### Missing vs FastAPI
- No OpenAPI/docs endpoint
- No request validation (manual body.get())
- No dependency injection
- No Pydantic models
- No async support
- No middleware stack

### What's Good
- Consistent JSON responses: _json_response(status, dict)
- Structured request logging (JSON with ts, component, client)
- Declarative route registration with path params
