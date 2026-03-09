# AU-06: Network API Deep Dive

## Purpose

Line-by-line audit of the network API — HTTP server using stdlib http.server (NOT FastAPI). Security surface, auth model, routing, response format. AI-First API rules evaluated as aspirational (per UF-001).

## Scope

| Directory/File | Description |
|----------------|-------------|
| `src/minion/network/__init__.py` | Package exports |
| `src/minion/network/server.py` | HTTP server (stdlib http.server) |
| `src/minion/network/router.py` | URL router ({param} matching) |
| `src/minion/network/auth.py` | Auth mixin (defined but NOT wired) |
| `src/minion/network/client.py` | Network client (CLI's client for API) |
| `src/minion/network/discovery.py` | Peer discovery |
| `src/minion/network/project_db.py` | Network-level DB operations |
| `src/minion/network/handlers/` | Request handlers (subdirectory) |
| Plus any other files in `src/minion/network/` |

Read ALL files in `src/minion/network/` including `handlers/` subdirectory.

## Skills to Evaluate

### AI-First API (all 37 rules — ASPIRATIONAL per UF-001)

Evaluate as "what SHOULD be there" for a mature API. The current API uses stdlib http.server, so many rules will be N/A or aspirational NO. Distinguish between:
- **N/A (architectural):** Rule requires FastAPI/framework features that don't apply to stdlib
- **NO (aspirational):** Rule represents a gap that should be addressed if API matures
- **NO (current deficiency):** Rule represents a gap that matters even at current maturity

#### URL Prefix Routing (ROUTE-1 through ROUTE-6)
- Check: does the router use verb-prefix routing (/search, /read, /list)?
- Expected: NO — current routing is resource-based, not verb-prefix

#### Confidence-Based Response (CONF-1 through CONF-5)
- Expected: N/A — no search/semantic matching in current API

#### Token Budget (TOK-1 through TOK-6)
- Expected: N/A — no token budget management

#### Self-Serving CLI (CLI-1 through CLI-6)
- Expected: N/A — CLI is separate, not served by API

#### API Specification (SPEC-1 through SPEC-4)
- **SPEC-1:** OpenAPI spec at /openapi.json — check if exists
- **SPEC-4:** /health endpoint — check if exists
- Expected: mostly NO

#### Infrastructure (INFRA-1 through INFRA-5)
- Check: docker-compose, Makefile, .env.example
- Expected: partially applicable

#### Documentation (DOC-1 through DOC-6)
- Check: README quick start, bootstrap auth, examples

#### Planning Discipline (PLAN-1 through PLAN-4)
- N/A for retrospective audit

### CS Foundations — Communication (CS-COMM, selected rules)
- **COMM-2:** Integration points — network API is an integration point. What contracts? What failure modes?
- **COMM-4:** API style — REST-like with custom router
- **COMM-5:** Serialization — JSON everywhere?

### CS Foundations — Security (CS-SEC, all 5 rules)
- **SEC-1:** Trust boundaries — network API is the untrusted boundary
  - **How to check:** Read server.py. Where does trusted meet untrusted?
- **SEC-2:** Authentication — Bearer token mechanism
  - **How to check:** Read auth.py and server.py. Is auth.py actually wired?
  - **Known finding:** AuthMixin defined but NOT wired. server.py uses inline _check_token.
- **SEC-3:** Authorization — per-endpoint or binary (has token or not)?
  - **How to check:** Check each handler for authorization checks.
- **SEC-4:** Secrets management — MINION_CLUSTER_TOKEN handling
- **SEC-5:** Input validation — request body validation
  - **Known finding:** Manual body.get() with no validation. No length limits. No sanitization.

### CS Foundations — Error & Failure Modes (CS-ERR, selected rules)
- **ERR-1:** What error patterns does the network API use?
- **ERR-5:** Observability — server.py has one structured log line

### Clean Architecture (selected rules)
- **CA-DEP-1:** Dependencies inward — network/ imports
- **CA-BOUND-3:** Data crossing boundaries — what shapes cross the HTTP boundary?

### Pragmatic Programmer (selected rules)
- **PP-CRAFT-1:** No programming by coincidence — HTTP handling intentional
- **PP-DECOUPLE-1:** No train wrecks — handler method chains
- **PP-DECOUPLE-5:** Config externalized — network config (port, token)

### Implementation Coding Core (selected rules)
- **IC-HDR-1 through IC-HDR-5:** Reference AU-00 systemic finding
- **IC-DATA-1 through IC-DATA-5:** Schema validation at HTTP boundary
  - **How to check:** Read each handler. Is request body validated? Are response shapes defined?

## Audit Procedure

### Step 1: Server Architecture
1. Read `server.py` in full — understand the HTTP server setup
2. Read `router.py` in full — understand URL routing mechanism
3. Map: how does a request flow from socket to handler to response?

### Step 2: Auth Analysis
1. Read `auth.py` in full — the AuthMixin
2. Read server.py `_check_token` inline implementation
3. Compare: what's in auth.py vs what's actually used in server.py?
4. Check: is no-token mode documented? Is it secure?
5. Check: Bearer token comparison (timing-safe? or simple string compare?)

### Step 3: Handler Walk
1. Read every file in `handlers/` subdirectory
2. For each handler:
   a. What endpoint does it serve?
   b. Does it validate input?
   c. Does it handle errors?
   d. What does it return? (JSON? Consistent format?)
   e. Does it check authorization?

### Step 4: Input Validation Assessment
1. For each handler, check: request body parsing
2. Check: are required fields validated?
3. Check: are types validated?
4. Check: are there length/size limits?
5. Check: SQL injection protection (parameterized queries?)
6. Check: what happens with malformed JSON body?

### Step 5: Response Format Consistency
1. For each handler, check response format
2. Check: consistent JSON structure?
3. Check: error response format consistent?
4. Check: HTTP status codes appropriate?

### Step 6: Client-Side Check (Boundary B-04)
1. Read `client.py` — how does CLI talk to network API?
2. Check: does client match server's endpoint contracts?
3. Check: error handling in client (timeout, connection error, bad response)

### Step 7: Rule-by-Rule Evaluation

## Expected Findings from Research

1. **AuthMixin NOT wired** — server.py uses inline _check_token instead. Auth code exists but isn't used. Major finding.
2. **No request validation** — handlers do body.get() with no schema validation. SEC-5 FAIL.
3. **Bearer token optional** — no token = all requests pass (dev mode). Security gap for production.
4. **Consistent JSON responses** — good pattern, strength.
5. **No OpenAPI, no docs endpoint** — SPEC rules FAIL (aspirational).
6. **No middleware** — stdlib http.server has no middleware concept. Each handler is standalone.
7. **IC-DATA FAIL:** No schema validation at HTTP boundary.
8. **Boundary B-04:** client.py and server.py may have inconsistent endpoint contracts.

## Output Format

```markdown
# AU-06 Network API Audit Results

## Server Architecture
[Request flow: socket -> router -> handler -> response]

## Auth Model
[Token mechanism, AuthMixin status, security assessment]

## Endpoint Inventory
| Endpoint | Handler | Validates Input? | Auth Check? | Response Format |
|----------|---------|-------------------|-------------|-----------------|
...

## Filled Checklist

### AI-First API (aspirational)
| Rule | Status | Evidence | Aspirational? |
|------|--------|----------|---------------|
| ROUTE-1 | YES/NO/N/A | | Yes/No |
...

### CS Foundations — Security
| Rule | Status | Evidence |
|------|--------|----------|
...

### CS Foundations — Communication (subset)
...

### CS Foundations — Error & Failure Modes (subset)
...

### Clean Architecture (subset)
...

### Pragmatic Programmer (subset)
...

### Implementation Coding Core (subset)
...

## Findings

| # | Rule | Severity | Affected Files | Description | Remediation |
|---|------|----------|----------------|-------------|-------------|
...

## Strengths
...

## Boundary Check: B-04 (CLI Client <-> Network API)
[Endpoint contract consistency assessment]
```
