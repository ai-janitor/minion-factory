# Worker Checklist — tui-stale-debug

## Bug
Dashboard shows "stale" status for agents that were registered/heartbeated seconds ago.
Example: `napoleon` shows "stale" and "15s ago" simultaneously — those contradict. 15s ago is NOT stale.

## Root Cause
Timezone mismatch between timestamp writers and readers:
- `daemon/watcher.py` and `daemon/runner/_constants.py` use `utc_now_iso()` → `datetime.now(timezone.utc).isoformat()` → stores `+00:00` suffix (timezone-aware UTC)
- `db/helpers.py` uses `now_iso()` → `datetime.datetime.now().isoformat()` → stores naive local time (no timezone)
- Both write to the same `last_seen` / `hp_updated_at` columns in the agents table
- Readers (monitoring, network handlers, db/agents enrichment) parse with `fromisoformat()` then subtract `datetime.now()` (naive)
- Python 3.13 raises `TypeError: can't subtract offset-naive and offset-aware datetimes`
- Exception handlers either return "offline"/"stale" (wrong) or propagate the error

## Files
- `src/minion/daemon/watcher.py` — `utc_now_iso()` stores UTC-aware timestamps
- `src/minion/daemon/runner/_constants.py` — duplicate `utc_now_iso()`
- `src/minion/db/helpers.py` — `now_iso()` stores naive local timestamps
- `src/minion/db/agents.py` — `enrich_agent_row()` compares timestamps (catches ValueError, not TypeError)
- `src/minion/monitoring.py` — `_agent_judgment()` same mismatch
- `src/minion/network/handlers/core.py` — `_compute_presence()` same mismatch
- `src/minion/dashboard/render.py` — agent display needs staleness computation
- `src/minion/dashboard/queries.py` — agent query fetches `last_seen`, `hp_updated_at`

## Fix Approach
1. Normalize `utc_now_iso()` to use naive local time (same as `now_iso()`) — all timestamps consistent
2. Fix all `fromisoformat` + `datetime.now()` comparisons to handle both aware and naive timestamps safely
3. Add `_to_naive_local(dt)` helper that strips timezone info for safe comparison with `datetime.now()`

- [x] Root cause identified
- [x] Fix implemented
- [x] Tests pass
- [x] Committed
