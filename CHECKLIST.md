# Fix: naive/aware timestamp comparison bug

## Bug
Daemon writes UTC-aware ISO timestamps (`datetime.now(timezone.utc).isoformat()`) into `last_seen` and `context_updated_at`.
Reader code parses them with `fromisoformat()` (preserves tzinfo) then compares against `datetime.now()` (naive local).
This either raises `TypeError` or produces wrong staleness values (hours off).

## Fix Strategy
If parsed datetime is timezone-aware, convert to local then strip tzinfo.
All comparisons become naive-local vs naive-local via `datetime.now()`.

## Files to fix
- [x] `src/minion/db/agents.py` — `enrich_agent_row()` lines 68-69, 79-80
- [x] `src/minion/db/agents.py` — `staleness_check()` lines 118, 124
- [x] `src/minion/monitoring.py` — `sitrep()` lines 142-143
- [x] `src/minion/monitoring.py` — `file_staleness_check()` line 225

## Helper
Add a `_to_naive_local(dt)` helper that:
- If dt.tzinfo is not None: `dt.astimezone().replace(tzinfo=None)`
- If naive: return as-is

## Validation
- [ ] `uv run pytest` passes
- [ ] Commit
