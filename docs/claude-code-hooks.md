# Claude Code Hook Integration

Auto-inject minion inbox messages into Claude Code agent context via PostToolUse hooks. Replaces manual `minion poll` for Claude Code sessions.

## How It Works

```
Agent registers → .work/.minion-agents/<name> created (roster file)
Every tool call → PostToolUse hook fires
Hook reads roster → calls check-inbox --silent for each agent
Messages found → injected as additionalContext into Claude's context
No messages → hook exits silently, zero overhead
```

## Setup (per machine)

### 1. Create the hook script

```bash
mkdir -p ~/.claude/hooks
cat > ~/.claude/hooks/minion-inbox-poll.sh << 'SCRIPT'
#!/bin/bash
AGENTS_DIR=".work/.minion-agents"
[ -d "$AGENTS_DIR" ] || exit 0

output=""
for agent_file in "$AGENTS_DIR"/*; do
  [ -f "$agent_file" ] || continue
  agent=$(basename "$agent_file")
  msgs=$(minion comms check-inbox --agent "$agent" --silent 2>/dev/null)
  [ -n "$msgs" ] && output="${output}${msgs}\n"
done

[ -z "$output" ] && exit 0

printf '%s' "$output" | jq -Rs '{hookSpecificOutput:{hookEventName:"PostToolUse",additionalContext:.}}'
SCRIPT
chmod +x ~/.claude/hooks/minion-inbox-poll.sh
```

### 2. Register the hook in Claude Code settings

Add to `~/.claude/settings.json` (create if it doesn't exist):

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "/Users/<you>/.claude/hooks/minion-inbox-poll.sh"
          }
        ]
      }
    ]
  }
}
```

**Use the full absolute path** — Claude Code settings don't expand `~`.

If `settings.json` already has other hooks, merge the `PostToolUse` entry into the existing `hooks` object.

### 3. Prerequisites

- `minion` CLI installed: `uv tool install git+https://github.com/ai-janitor/minion-factory.git`
- `jq` installed: `brew install jq` (macOS) or `apt install jq` (Linux)
- `.work/` initialized in the project: `minion init`

## Agent Roster

Agents are discovered via `.work/.minion-agents/` — one file per agent:

```
.work/.minion-agents/
├── coder-python      ← agent_class: coder, zone: backend
├── coder-cpp         ← agent_class: coder, zone: gpu
└── leader            ← agent_class: lead, zone: all
```

- `minion agent register` creates the roster file automatically
- `minion agent deregister` / `stand_down` removes it
- `spawn-party` creates roster files for all crew members
- Agents inactive 6+ hours are auto-pruned from the coordinator DB

## Non-agent sessions

If `.work/.minion-agents/` doesn't exist (no agents registered), the hook is a no-op — exits immediately with no output. Safe as a global install.

## Silent inbox check

`minion comms check-inbox --agent X --silent`:
- Prints raw `[sender] message content` lines if messages exist
- Prints nothing if inbox is empty (exit 0, zero stdout)
- Marks messages as read on retrieval
- Designed for high-frequency calls (~50-100 per session)

## Troubleshooting

| Symptom | Check |
|---------|-------|
| Hook not firing | Verify `~/.claude/settings.json` has the PostToolUse entry |
| No messages arriving | Is `.work/.minion-agents/` populated? Run `ls .work/.minion-agents/` |
| `minion: command not found` | Reinstall: `uv tool install git+https://github.com/ai-janitor/minion-factory.git` |
| `jq: command not found` | Install jq: `brew install jq` |
| Messages arriving but not injected | Check hook output: `bash ~/.claude/hooks/minion-inbox-poll.sh` from the project dir |
