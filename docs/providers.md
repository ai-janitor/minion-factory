# Providers — Multi-Model Support

Agents can run on different AI providers. Each provider wraps a different CLI tool.

## Available Providers

| Provider | CLI Tool | Models | Sandbox |
|----------|----------|--------|---------|
| `claude` | `claude` | claude-opus-4-6, claude-sonnet-4-6, claude-haiku-4-5 | None (full access) |
| `codex` | `codex` | codex default | `--sandbox workspace-write --add-dir ~/.minion_work` |
| `gemini` | `gemini-cli` | gemini-pro, gemini-2.0-pro | Tool-level path restriction only |
| `opencode` | `opencode` | configurable | None |

## Crew YAML Configuration

Set provider per agent in crew YAML:

```yaml
agents:
  tifa:
    role: coder
    provider: claude
    model: claude-sonnet-4-6
    permission_mode: bypassPermissions

  cid:
    role: coder
    provider: codex
    permission_mode: bypassPermissions

  redxiii:
    role: recon
    provider: gemini
    allowed_tools: "Read,Glob,Grep,Bash,WebSearch,WebFetch"
```

## Provider Details

### Claude

Default provider. Uses `claude` CLI with `--dangerously-skip-permissions` for daemon agents.

- Supports `--resume` for session continuity
- System prompt injected via `--system-prompt`
- Model selected via `--model`
- Permission mode via `--permission-mode`

### Codex

OpenAI's Codex CLI. Runs in a sandboxed shell.

- `--sandbox workspace-write` — restricts file writes to project dir
- `--add-dir ~/.minion_work` — grants access to comms DB and docs
- `-c shell_environment_policy.inherit=all` — passes env vars (MINION_DB_PATH, etc.)
- No resume support

### Gemini

Google's Gemini CLI. Tool-level path restrictions only (shell/CLI unaffected).

- Uses `gemini-cli` binary
- Model configured in gemini's own config
- No sandbox around shell — agents can call `minion` CLI freely

### OpenCode

Generic provider for self-hosted or alternative models.

- Uses `opencode` CLI
- Model configured externally
- No sandbox

## Environment Variables

Providers pass these to agent processes:

| Var | Purpose |
|-----|---------|
| `MINION_DB_PATH` | Path to SQLite DB |
| `MINION_DOCS_DIR` | Path to contract docs |
| `MINION_CLASS` | Agent's class (lead, coder, etc.) |
| `MINION_PROJECT` | Project name |

## Source Files

| File | What |
|------|------|
| `src/minion/providers/__init__.py` | `get_provider()` registry |
| `src/minion/providers/base.py` | `BaseProvider` interface |
| `src/minion/providers/claude.py` | Claude provider |
| `src/minion/providers/codex.py` | Codex provider |
| `src/minion/providers/gemini.py` | Gemini provider |
| `src/minion/providers/opencode.py` | OpenCode provider |
