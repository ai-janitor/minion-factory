# New Machine Setup

Steps to set up minion-factory on a fresh machine.

## 1. Install

```bash
uv tool install git+https://github.com/ai-janitor/minion-factory.git
```

## 2. Install Claude Code Hooks

The Stop hook enforces polling discipline — agents cannot go idle when messages are waiting.

```bash
minion install-hooks
```

This copies `poll-on-stop.sh` to `~/.minion/hooks/` and adds a `Stop` hook entry to `~/.claude/settings.json` pointing there. Safe to run multiple times — replaces old entries, doesn't clobber other hooks.

**What it does:** After every agent response, the hook blocks the stop and forces the agent back into `minion poll`. The agent never goes idle — it's always either working or blocked inside poll waiting for the next message.

**Re-run after updates:** If the hook script changes (bug fixes, behavior changes), run `minion install-hooks` again to copy the updated version to `~/.minion/hooks/`.

**Gating:** Only activates when `MINION_AGENT_NAME` env var is set. Regular (non-agent) claude-code sessions are unaffected.

## 3. Verify

```bash
# Check hook is installed
cat ~/.claude/settings.json | jq '.hooks.Stop'

# Should show the poll-on-stop.sh command entry
```

## 4. Dependencies

- `jq` — used by the hook script to parse JSON. Install via `brew install jq` (macOS) or `apt install jq` (Linux).
- `minion` CLI must be on PATH (installed by step 1).

## Safety

- **Kill switch:** Set `MINION_HOOKS_BYPASS=1` env var to disable all hook enforcement instantly.
- **Loop prevention:** The `stop_hook_active` field prevents infinite loops — hooks allow stop on the second cycle.
- **Fail-open:** If the hook script errors, Claude Code allows the stop (never bricks the session).

## Cross-Project Agents

Agents can run from any directory — even parent directories above repos (e.g., `~/projects/`). The system auto-initializes `.work/` at any location:

1. `resolve_db_path()` walks up from cwd looking for existing `.work/minion.db`
2. If none found, falls back to `cwd/.work/minion.db`
3. `init_db()` creates the DB with full schema on first CLI call
4. `touch_coordinator_activity()` registers the agent's `project_path` in the global coordinator
5. Other agents can reach it via `minion comms send global`

The stop hook uses the same walk-up logic with cwd fallback — cross-project agents stay enforced.

## Environment Variables

| Variable | Set By | Purpose |
|----------|--------|---------|
| `MINION_AGENT_NAME` | spawn (terminal/daemon) | Identifies which agent's inbox to check |
| `MINION_PROJECT_DIR` | spawn (terminal/daemon) | Project root for `-C` flag on minion commands |
| `MINION_HOOKS_BYPASS` | human (manual) | Kill switch — set to `1` to disable enforcement |
