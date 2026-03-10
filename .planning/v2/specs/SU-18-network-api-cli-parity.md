# SU-18: Network API CLI Parity — Handlers and Sys-Lead Gaps

**Wave:** 6 (depends on SU-17)
**Requirements:** 5.1 (minus composite key)
**Dependencies:** SU-17
**Dependents:** SU-22

---

## Purpose

Bring the network API to parity with the CLI by adding handlers for ~10 missing commands, verifying GET /who filtering, addressing 6 sys-lead review gaps, and resolving scaling endpoints (based on SU-17's decision).

## Requirements Traceability

- **5.1 (Network API Evolution):** "CLI parity with network API — ~10 missing commands, GET /who filtering, 6 sys-lead gaps, scaling endpoints."
- **Deferred:** Composite agent key (host/project/name) deferred to v3.

## Dependencies

- **SU-17 (Dead Code):** Must know whether scaling endpoints are wired or removed before adding new endpoints.

## Behavior

### Missing CLI-to-API Mappings

**Audit method:** Compare `src/minion/cli/*.py` command list to `src/minion/network/handlers/*.py` + `routes.py` endpoint list. Identify CLI commands without network equivalents.

**Expected missing handlers (from research):**

| CLI Command | Expected API Endpoint | HTTP Method |
|-------------|----------------------|-------------|
| `minion cold-start` | `POST /agents/{name}/cold-start` | POST |
| `minion refresh` | `POST /agents/{name}/refresh` | POST |
| `minion fenix-down` | `POST /agents/{name}/fenix-down` | POST |
| `minion set-context` | `PUT /agents/{name}/context` | PUT |
| `minion poll` | `GET /agents/{name}/poll` | GET (long-poll) |
| `minion task complete-phase` | `POST /tasks/{id}/complete-phase` | POST |
| `minion task result` | `POST /tasks/{id}/result` | POST |
| `minion task review` | `POST /tasks/{id}/review` | POST |
| `minion task test` | `POST /tasks/{id}/test` | POST |
| `minion install-hooks` | N/A (local-only) | — |

**For each missing handler:**
- Create handler module in `src/minion/network/handlers/`
- Follow existing handler pattern: parse request, call core logic, return JSON response
- Register route in `routes.py`
- Handle authentication (API key or agent class check)

### GET /who Filtering

**Current:** `GET /who` likely returns all agents.
**Target:** Support query parameters for filtering:
- `?class=coder` — filter by agent class
- `?status=active` — filter by status
- `?project=<path>` — filter by project
- Return 200 with filtered list, or 200 with empty list if no matches

### 6 Sys-Lead Review Gaps

| Gap | Description | Target |
|-----|-------------|--------|
| Lineage | No API for task lineage/DAG history | `GET /tasks/{id}/lineage` |
| Overview | overview.py exists but may be incomplete | Verify and complete |
| Alerts | No API for alert/warning aggregation | `GET /alerts` — aggregate warnings from all agents |
| Query params | Endpoints lack filtering/pagination | Add `?limit`, `?offset`, `?since` to list endpoints |
| DB policy | No DB health/stats endpoint | `GET /db/stats` — size, row counts, WAL status |
| Full agent view | No single endpoint for complete agent state | `GET /agents/{name}/full` — agent + tasks + claims + messages |

### Scaling Endpoints (from SU-17)

- If SU-17 wired them: verify they work correctly, add tests
- If SU-17 removed them: no work needed here

### Inputs/Outputs

All new endpoints follow the existing pattern:
- **Input:** HTTP request with JSON body (POST/PUT) or query params (GET)
- **Output:** JSON response with `{"status": "ok", ...}` or `{"error": "..."}`
- **Auth:** Require valid agent name in request (header or body) — checked against DB

## Constraints

- Must follow existing handler pattern (consistency with other handlers)
- Must not introduce new dependencies
- All new endpoints must be tested
- install-hooks is local-only — no API equivalent needed
- poll over HTTP is complex (long-polling or WebSocket) — may be deferred or simplified to a "check for messages" endpoint

## Edge Cases

1. **Long-poll over HTTP:** `poll` as a long-running HTTP request is problematic. Consider: (a) short-poll that checks and returns immediately, or (b) document as "local CLI only."
2. **API authentication:** Currently unclear how API auth works. If it's API key, new endpoints must respect it. If none, document the gap.
3. **Concurrent API access:** Multiple agents calling API simultaneously. SQLite WAL handles this, but verify no handler holds a connection too long.
4. **Large response payloads:** `/agents/{name}/full` could return a lot of data. Support `?include=tasks,claims` to control what's included.

## Current State

- Handlers exist for: core, projects, backlog, requirements, flows, overview, scaling, compat
- routes.py registers existing endpoints
- ~10 CLI commands lack API equivalents
- overview.py partially implemented

## Test Contract

- **Test 1:** For each new endpoint: send HTTP request, assert 200 response with correct JSON structure.
- **Test 2:** `GET /who?class=coder` returns only agents with class "coder".
- **Test 3:** `GET /tasks/{id}/lineage` returns task DAG history.
- **Test 4:** `GET /db/stats` returns DB size and row counts.
- **Test 5:** All new routes registered — `GET /routes` (or test via routes.py inspection) shows all endpoints.
