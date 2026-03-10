# Worker Checklist — tui-fixer

## Problem
The TUI dashboard shows "waiting for work" and stale "last seen" for agents that are actually active as subagents (spawned via Claude Code Agent tool). These agents register via `minion agent register` but never update their heartbeat or status during execution, so the dashboard shows stale data.

## Goal
Make the dashboard more useful for agents that registered but don't heartbeat frequently. Two fixes:

1. **Stale agent detection** — if an agent's `last_seen` is old but they registered recently, show a different status indicator (e.g. "no heartbeat" instead of the registered status)
2. **Agent status from context** — the `set-context` command updates `last_seen`. The dashboard query should use the most recent of `last_seen` or registration time.

## Files to modify:
- src/minion/dashboard/queries.py — agent query needs to include registered_at, context_updated_at, and use COALESCE for effective last_seen
- src/minion/dashboard/render.py — render logic for stale vs active vs no-heartbeat agents

## Approach:
- Schema has: registered_at, last_seen, context_updated_at columns on agents table
- Query: add registered_at to SELECT, compute effective_last_seen as COALESCE(last_seen, context_updated_at, registered_at)
- Render: compute staleness from effective_last_seen; agents registered <10min ago with no heartbeat get "active (no hb)" dim indicator; truly stale agents (>5min) get red indicator
- Keep existing ANSI color scheme

## Verify:
- Read the rendered output logic to confirm the change
- `uv run pytest` passes

- [yes] Implemented
- [yes] Tested
- [ ] Changes committed
