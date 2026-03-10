# SU-22: Dashboard UI Consolidation — Merge and Sys-Lead Views

**Wave:** 6 (depends on SU-18)
**Requirements:** 5.5
**Dependencies:** SU-18
**Dependents:** None

---

## Purpose

Consolidate the dashboard subsystem: define its purpose, complete the merge into the network server, and add sys-lead operational views for monitoring agent health, task pipeline, and system status.

## Requirements Traceability

- **5.5 (Dashboard and UI):** "Dashboard sys-lead operational views. Define purpose and scope. Merge UI into network server."

## Dependencies

- **SU-18 (Network API Parity):** Dashboard views call API endpoints. The API must be stable and complete before building views on top.

## Behavior

### Dashboard Purpose and Scope

**Definition:**
- The dashboard is a web-based operational view for sys-lead and human operators
- It is NOT an agent-facing interface — agents use the CLI
- It provides read-only views of system state: agent health, task pipeline, message flow, HP dashboard
- It runs as part of the network server (not a separate process)

### Dashboard Merge

**Current state:**
- `src/minion/dashboard/` — standalone dashboard package with loop.py, queries.py, render.py
- `src/minion/network/dashboard.py` — network server integration point (may be stub or partial)

**Target:**
- Dashboard renders HTML templates served by the network server
- Routes: `/dashboard/` (main view), `/dashboard/agents`, `/dashboard/tasks`, `/dashboard/health`
- Dashboard queries use the same DB as the network API (no separate connection)
- Static assets (CSS, minimal JS) served from `src/minion/network/static/` or inline

### Sys-Lead Operational Views

**View 1: Agent Health Dashboard (`/dashboard/agents`)**
- Table of all registered agents
- Columns: name, class, status, HP, last_seen, current task, unread messages
- Color coding: green (healthy), yellow (warning), red (critical/stale)
- Auto-refresh every 30 seconds (meta refresh or minimal JS)

**View 2: Task Pipeline (`/dashboard/tasks`)**
- Kanban-style view of tasks by status
- Columns: open, assigned, in_progress, fixed, qe, verify, closed
- Each card shows: task ID, title, assigned agent, time in current status
- Filter by: agent, flow type, priority

**View 3: System Health (`/dashboard/health`)**
- DB stats: size, row counts per table, WAL status
- Agent stats: total registered, active (last seen < 5 min), stale
- Message stats: total, unread, average delivery time
- Battle plan status: active plan name and progress

**View 4: Message Flow (`/dashboard/messages`)**
- Recent messages (last 50)
- Columns: timestamp, from, to, msg_type, read_flag
- Filter by: agent, msg_type, read status

### Template System

- Use Jinja2 (already a Python dependency or easily added)
- Templates in `src/minion/network/templates/dashboard/`
- Minimal CSS — no heavy framework. Use system fonts, simple table styling.
- No JavaScript framework — plain HTML with optional minimal JS for auto-refresh

### Integration with Network Server

- Dashboard routes registered in routes.py alongside API routes
- Dashboard endpoints return HTML (Content-Type: text/html), not JSON
- Shared DB connection with API handlers
- Dashboard is optional — if template files are missing, routes return 404

## Constraints

- Dashboard is read-only — no mutations through the dashboard
- Must not add heavy frontend dependencies (no React, no Node.js)
- Must work in any modern browser without JavaScript (JS enhances but is not required)
- Must not slow down the network server (dashboard queries should be fast — <100ms)
- Template rendering must not block API endpoints

## Edge Cases

1. **No agents registered:** Dashboard shows empty tables with "No agents registered" message.
2. **Large number of tasks:** Task pipeline with >100 tasks should paginate or truncate to last 50 per status.
3. **Stale data:** Dashboard data is point-in-time. Auto-refresh mitigates but does not eliminate staleness.
4. **Network server not running:** Dashboard is only available when the network server is running. CLI-only deployments have no dashboard.
5. **Multiple browser tabs:** Each tab makes independent requests. No WebSocket state sharing needed.
6. **Mobile/small screens:** Use responsive CSS (min-width tables, stack on mobile). No complex responsive framework needed.

## Current State

- dashboard/ package exists with basic rendering
- network/dashboard.py exists (status unclear)
- Network server handles API requests
- No Jinja2 templates or HTML views currently

## Test Contract

- **Test 1:** `GET /dashboard/` returns 200 with HTML content.
- **Test 2:** `GET /dashboard/agents` returns HTML table with registered agents.
- **Test 3:** `GET /dashboard/tasks` returns HTML with task pipeline view.
- **Test 4:** `GET /dashboard/health` returns HTML with DB stats and agent counts.
- **Test 5:** Dashboard with no registered agents returns valid HTML with empty-state message.
