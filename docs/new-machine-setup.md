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

This adds a `Stop` hook entry to `~/.claude/settings.json` pointing to `scripts/poll-on-stop.sh`. Safe to run multiple times — it merges without clobbering existing hooks.

**What it does:** After every agent response, the hook checks the agent's inbox. If unread messages exist, it blocks the stop and forces the agent to poll. This makes the poll loop mechanical instead of relying on agents remembering.

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
- **Fail-open:** If the `minion` CLI fails or inbox check errors, the hook allows the stop (never bricks the session).

## Environment Variables

| Variable | Set By | Purpose |
|----------|--------|---------|
| `MINION_AGENT_NAME` | spawn (terminal/daemon) | Identifies which agent's inbox to check |
| `MINION_PROJECT_DIR` | spawn (terminal/daemon) | Project root for `-C` flag on minion commands |
| `MINION_HOOKS_BYPASS` | human (manual) | Kill switch — set to `1` to disable enforcement |
