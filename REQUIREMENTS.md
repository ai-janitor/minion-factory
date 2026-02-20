# minion-factory — Unified Multi-Agent Framework

## Mission

Merge three repos into one clean package:

| Repo | What it provides |
|------|-----------------|
| **minion-commsv2** | CLI, SQLite DB, messaging, auth, crew lifecycle, HP monitoring, file claims, war room, triggers, polling |
| **minion-swarm** | Daemon runner, tmux spawning, provider abstraction (claude/gemini/codex/opencode), rolling buffer, error filtering |
| **minion-tasks** | DAG-based task flows, YAML pipeline definitions, stage transitions |

## Source Repos (read-only references)

```
/Users/hung/projects/minion-commsv2/   # CLI comms framework
/Users/hung/projects/minion-swarm/     # daemon + providers
/Users/hung/projects/minion-tasks/     # task DAG engine
```

## Target Structure

One installable Python package: `minion`

```
minion-factory/
├── pyproject.toml              # single package, CLI entry point: `minion`
├── CLAUDE.md                   # agent-readable dev reference
├── src/minion/
│   ├── __init__.py
│   ├── cli.py                  # unified CLI (all commands from all 3 repos)
│   ├── db.py                   # single DB schema (comms + tasks tables)
│   ├── auth.py                 # class → command permissions
│   ├── comms.py                # messaging (send, inbox, broadcast)
│   ├── monitoring.py           # HP tracking, activity checks
│   ├── tasks/
│   │   ├── __init__.py
│   │   ├── crud.py             # task create/update/query
│   │   ├── dag.py              # DAG flow engine (from minion-tasks)
│   │   └── loader.py           # YAML flow loader + inheritance
│   ├── crew/
│   │   ├── __init__.py
│   │   ├── spawn.py            # tmux pane spawning
│   │   ├── lifecycle.py        # register, stand-down, retire, cold-start, fenix-down
│   │   └── config.py           # crew YAML parsing (SwarmConfig + AgentConfig)
│   ├── providers/
│   │   ├── __init__.py         # registry: get_provider(name)
│   │   ├── base.py             # BaseProvider ABC
│   │   ├── claude.py
│   │   ├── gemini.py
│   │   ├── codex.py
│   │   └── opencode.py
│   ├── daemon/
│   │   ├── __init__.py
│   │   ├── runner.py           # AgentDaemon main loop
│   │   ├── buffer.py           # RollingBuffer
│   │   └── watcher.py          # legacy watcher mode
│   ├── filesafety.py           # file claim system
│   ├── warroom.py              # battle plans, raid log
│   ├── triggers.py             # trigger word codebook
│   ├── polling.py              # poll loop for daemon agents
│   ├── defaults.py             # path resolution, env vars, constants
│   └── fs.py                   # atomic file ops
├── task-flows/                 # YAML pipeline definitions
│   ├── _base.yaml
│   ├── feature.yaml
│   ├── bugfix.yaml
│   └── ...
├── crews/                      # crew definitions
│   ├── ff1.yaml
│   ├── ateam.yaml
│   └── ...
├── docs/
│   ├── protocol-common.md
│   ├── protocol-lead.md
│   ├── protocol-coder.md
│   └── ...
├── ui/                        # observability dashboard (React + Express)
│   ├── server.js              # Express API reading SQLite (readonly)
│   ├── src/
│   │   ├── App.tsx
│   │   └── components/
│   │       ├── Dashboard.tsx   # party overview + HP
│   │       ├── AgentLogs.tsx   # per-agent activity stream
│   │       ├── TaskBoard.tsx   # task status board
│   │       ├── SprintBoard.tsx # sprint-style view
│   │       ├── RaidLog.tsx     # raid log viewer
│   │       └── TaskLineageModal.tsx  # task DAG history
│   ├── package.json           # vite + react + tailwind + shadcn
│   └── vite.config.ts
└── tests/
    └── test_*.py               # mirror src modules
```

## Design Principles

1. **One CLI, one DB, one package.** `pip install minion-factory` gives you `minion` with all commands. No cross-repo editable installs.

2. **SQLite is the only shared state.** No files, no Redis, no sockets. DB path resolved from env or convention.

3. **Provider-agnostic daemon.** Adding a new LLM CLI = one new file in `providers/`, register in `__init__.py`. No daemon.py changes.

4. **Crew YAML = full party definition.** One file defines agents, roles, providers, models, zones, system prompts. `minion spawn-party --crew ff1` does the rest.

5. **Task DAG is first-class.** Tasks have stages, transitions, worker restrictions. `minion create-task --flow feature` scaffolds the full pipeline.

6. **No dead-drop references.** All naming uses `minion` conventions. The dead-drop era is over.

## AI-First Development Standards

Read these skills from `~/.skills/` for the full methodology. They are law for this project.

### AI-First Code Organization (`~/.skills/ai-first-design/`)

- **1 file = 1 public function.** Directory = domain. When AI runs `ls`, it understands the API without reading code.
- Modules with >1 public function become packages with `__init__.py` re-exports and `__all__`.
- Private helpers colocate with their caller. Constants shared by 2+ files go in `_constants.py`.
- Consumer imports never change when internals refactor.
- File names are self-documenting — no abbreviations, no `cmd_` or `kb_` prefixes. `knowledge_export.py` not `kb_export.py`.

### AI-First CLI (`~/.skills/ai-first-cli/`)

- **All output is JSON by default.** Agents consume this CLI — structured data, not prose.
- `--help` at every level. Agents discover commands on-demand.
- **No interactive prompts.** Everything via flags with defaults. Breaks agents and CI/CD.
- **Verb-noun structure.** `minion send`, `minion create-task`, `minion get-tasks`. Predictable discovery.
- Error messages include hints: what went wrong + what to do about it.
- Config precedence: flags > env vars > project config > user config > defaults.
- `--compact` flag for minimal output (agent-friendly one-liners).

### AI-First API (`~/.skills/ai-first-api/`)

- If internal modules expose a programmatic API, URL-prefix-style naming: `list_*` returns metadata, `get_*` returns content.
- Confidence-based responses where applicable.
- Token budget awareness — responses sized for AI context windows.

## What to Carry Forward (keep)

- The `minion` CLI interface and all its commands
- SQLite schema (messages, agents, tasks, file_claims, battle_plans, raid_log, triggers)
- Auth model (class → allowed commands)
- Provider modules (claude, gemini, codex, opencode) with error filtering
- Daemon poll mode with HP tracking and compaction detection
- Crew YAML format and tmux spawning
- Task DAG engine with YAML inheritance
- Protocol docs (protocol-common.md, protocol-{class}.md)
- Rolling buffer + context history injection

## What to Fix (improve)

- **Duplicate DB code**: commsv2 and tasks both have db.py with separate schemas. Unify into one migration-aware schema.
- **Config fragmentation**: SwarmConfig (minion-swarm) and defaults.py (commsv2) resolve paths differently. One config system.
- **CLI split**: commands spread across 3 repos. One click group, one entry point.
- **flow_bridge.py**: awkward glue between commsv2 tasks and minion-tasks DAG. Should be native.
- **Watcher mode**: legacy, rarely used. Keep but mark deprecated. Poll mode is the future.

## What to Drop

- `minion-comms` (v1) — already deprecated
- `dead_drop_*` naming in code and configs
- Duplicate crew YAMLs (minion-swarm has copies in both `crews/` and `data/crews/`)
- `ts-daemon/` experiment (stays in minion-swarm for reference, not ported)

## Build & Test

```bash
uv init
uv add click pyyaml watchdog
uv run pytest
```

Single `pyproject.toml`. Single `uv.lock`. No workspace complexity.

## Success Criteria

1. `pip install .` works, `minion --help` shows all commands
2. `minion spawn-party --crew ff1` spawns a full party with mixed providers
3. `minion send`, `check-inbox`, `create-task`, `complete-task` all work
4. `uv run pytest` passes
5. Zero imports from `minion_comms`, `minion_swarm`, or `minion_tasks` — all from `minion`

## HP System — Observed Issues (from live ff1 session)

The HP monitoring system has gaps discovered during live multi-agent operation. Address these in the merge.

### How HP Works Today

Two reporting modes:

1. **Daemon-observed** (real): `minion-swarm/daemon.py:_update_hp()` calls `minion update-hp` after each API turn with actual token counts from the provider. Uses `turn_input` (per-turn context window usage) as primary metric. Falls back to cumulative `input_tokens`.

2. **Self-reported** (sentinel): Agents with `hp_tokens_limit == 100` are gated out of the real pipeline (`monitoring.py:357`). They self-report via `set-context --hp`. The magic value `100` means "terminal agent, no daemon-observed tokens."

**Formula**: `hp_pct = max(0, 100 - (turn_input / limit * 100))`. Thresholds: >50% Healthy, >25% Wounded, <=25% CRITICAL.

**Alerts**: System messages sent to lead at <=25% and <=10%. Reset when HP recovers above 50%. Tracked in `hp_alerts_fired` JSON column.

### Observed Problems

1. **Zombie agents at 0% HP persist indefinitely.** In live ff1 session, whitemage (gpt-5.3-codex) reported `599k/200k` tokens — 3x over limit, 0% HP for 4.5+ hours. Still registered, still polling, still accepting messages. No corrective action taken automatically. Lead received alerts but took no action (terminal lead wasn't polling at the time).

2. **No guard on task assignment to CRITICAL agents.** Nothing prevents `assign-task` to an agent at 0% HP. The agent will receive the task, attempt to process it, and fail — wasting coordinator time and the message tokens.

3. **No auto-recovery.** The system alerts but never acts. If the lead is busy, offline, or ignoring alerts, the zombie persists. There's no escalation path (e.g., alert the human, auto-fenix-down, auto-retire).

4. **Messages to zombies are wasted.** Other agents (or the lead) can keep sending messages to a 0% agent. Each message costs tokens on the sender side for a message that will never be meaningfully processed.

5. **The `100` sentinel is a magic number.** Self-reported vs daemon-observed is distinguished by `hp_tokens_limit == 100`, which is fragile. An agent with a genuinely small context window (hypothetically 100 tokens) would be misclassified.

### What to Fix in minion-factory

| Issue | Fix |
|-------|-----|
| Zombie persistence | Auto-fenix-down at 0% HP (configurable threshold), or at minimum auto-retire after N minutes at 0% with no activity |
| Task assignment to dead agents | `assign-task` should warn (or block) when target is CRITICAL. Add `--force` flag to override |
| No escalation | If lead doesn't act on HP alert within N minutes, escalate to human (e.g., log to raid log, or system broadcast) |
| Wasted messages to zombies | `send` should warn when target is CRITICAL (advisory, not blocking) |
| Magic number 100 | Replace with explicit `hp_mode` column: `"daemon"` vs `"self-reported"` vs `"none"`. No sentinel values |
| Alert fatigue | Alerts fire once per threshold per drop cycle, which is good. But consider rate-limiting across agents — if 3 agents go CRITICAL simultaneously, batch the alerts |

## Provider Workspace Isolation — Observed Issues (from live ff1 session)

### Gemini Workspace Sandbox

Gemini providers enforce strict workspace directory boundaries. When a daemon spawns in project A's directory, Gemini's `read_file` tool refuses paths outside that project tree.

**Observed:** thief (gemini-3-flash-preview) spawned from `/Users/hung/projects/minion-commsv2/` could not use `read_file` on `/Users/hung/projects/minion-tasks/` or `/Users/hung/projects/minion-swarm/`. Error: `"Path not in workspace: Attempted path resolves outside the allowed workspace directories"`. The agent adapted by shelling out (`cat` via bash), but this is a friction point.

**Impact on cross-repo work:** Any task that requires reading source files from multiple repos will hit this with Gemini. Claude and Codex providers do not have this restriction.

### What to Fix in minion-factory

| Issue | Fix |
|-------|-----|
| Gemini workspace boundary | Document per-provider limitations in protocol docs. When assigning cross-repo tasks to Gemini agents, pre-copy needed source files into the workspace, or instruct agents to use shell for file reads |
| `project_dir` in crew YAML | Consider adding `allowed_dirs` list to crew config so spawn can set the workspace correctly for cross-repo work |
| Provider capability matrix | Add a provider capability table to docs: which providers support cross-dir reads, which need workarounds |

### Provider-Specific Observations

| Provider | Model | Workspace Sandbox | Cross-Dir Reads | Token Reporting | Context Window | Rate Limits |
|----------|-------|-------------------|-----------------|-----------------|----------------|-------------|
| Claude | opus/sonnet | No hard sandbox | Works | Full (input, cache_creation, cache_read, output + contextWindow) | Reported via `modelUsage.contextWindow` in stream-json `result` event | Generous (API key) |
| Codex | gpt-5.3-codex | Env var isolation | Untested | Unknown format | Unknown — daemon falls back to 200k default | Unknown |
| Gemini | gemini-3-flash | Strict sandbox | Blocked | **Not extracted** — Gemini's stream-json has different structure, no `modelUsage` dict | **Unknown** — daemon uses 200k default, but gemini-3-flash likely has 1M context | **Aggressive** — 429s observed during normal workload |

## Provider Rate Limiting

### Observed Problem

thief (Gemini) hit HTTP 429 (rate limit) during normal task execution. The daemon has no backoff logic — it logs the error and moves to the next poll cycle, which may immediately re-trigger the same rate-limited API call.

### What to Fix in minion-factory

| Issue | Fix |
|-------|-----|
| No backoff on rate limit | Provider should detect 429/rate limit responses and implement exponential backoff before retrying |
| No rate limit awareness in daemon | Daemon should track rate limit hits per provider and adjust polling interval accordingly (don't dispatch work to a rate-limited agent) |
| No provider fallback | Consider: if a provider is rate-limited, can the daemon temporarily switch to a backup provider? (e.g., gemini-flash → gemini-pro, or fall back to a queue) |
| Rate limit visibility | Rate limit events should be surfaced to the lead. An agent stuck on 429s is effectively down — similar to HP CRITICAL, the lead should know |
| Provider capacity in crew YAML | Add optional `rate_limit_rpm` field to agent config. Daemon can pace invocations to stay under provider limits |

## Spawn-Per-Task vs Persistent Agents

### Observed Problem

Agents persist between tasks, polling empty inboxes, accumulating context, hitting compaction. The bootstrap (system prompt + tools) is cached and deterministic — re-creating an agent is cheap.

**Observed costs of persistence:**
- redwizard hit compaction twice in 18 minutes (Opus context fills fast when reading files)
- fighter polled empty inbox for ~2 minutes between Task #1 and Task #4 assignment
- blackmage polled empty inbox after Task #2 completion waiting for Phase 4
- whitemage accumulated 33+ failed invocations as a zombie — would have been killed instantly in spawn-per-task model
- Each idle poll cycle costs tokens (system prompt re-read + inbox check)

### Consider: Ephemeral Agent Mode

| Aspect | Persistent (current) | Ephemeral (spawn-per-task) |
|--------|---------------------|---------------------------|
| Context | Accumulates across tasks, compacts | Fresh per task, never compacts |
| Startup | First invocation only | Every task (but prompt cache makes this ~2-3s) |
| Zombie risk | High — agent stays alive even when broken | Zero — agent dies when task completes or fails |
| Cross-task memory | Agent remembers prior tasks | Agent has no memory (must read task file) |
| Token cost | Idle polling burns tokens | Zero idle cost |
| Coordination | Agent can participate in back-and-forth | One-shot: read task → do work → report → die |

### Hybrid Approach

- **Leads** (redmage, redwizard): Persistent — they need ongoing coordination context
- **Workers** (fighter, blackmage, thief): Ephemeral — spawn per task, dismiss on completion
- **Oracle** (whitemage): Ephemeral — answer one question, die. No need to persist

This matches the playbook's advice: "One mission, then kill."

## Privilege Escalation Bug — Daemon ENV_CLASS Override

### Observed Incident

fighter (coder class) called `minion stand-down` and dismissed the entire party at 09:53:33, mid-session, without authorization. `stand-down` is supposed to be lead-only (`auth.py` gates it to `{"lead"}`). But it succeeded.

### Root Cause

`daemon.py:854` sets `env[ENV_CLASS] = "lead"` for ALL shell commands run by daemon agents. This was added so agents could call `minion update-hp` (which is lead-gated). But it's a blanket override — EVERY `minion` command run through the daemon's shell inherits lead-class permissions.

```python
# daemon.py:854
env[ENV_CLASS] = "lead"  # Daemon has permission to write HP
```

This means any daemon agent (coder, builder, recon, oracle) can:
- `minion stand-down` (dismiss the party)
- `minion set-battle-plan` (override strategy)
- `minion retire-agent` (kill other agents)
- Any other lead-only command

### What to Fix in minion-factory

| Issue | Fix |
|-------|-----|
| Blanket class override | Don't set `ENV_CLASS=lead` globally. Instead, the daemon should run HP-related commands with elevated perms internally (direct DB write, not CLI subprocess) |
| Or: scoped escalation | Pass the agent's real class as `ENV_CLASS`, and have `update-hp` use a separate auth mechanism (e.g., a daemon-specific token or flag) |
| stand-down should require confirmation | A stand-down that affects the entire party should require lead confirmation, not just lead-class permission. Add a `--force` flag or require the stand-down to come from a registered lead agent |
| Audit trail | Log which agent called stand-down and whether it was authorized. Currently only the flags table records `set_by` |

### Implementation

The daemon could support a `mode: ephemeral` flag in crew YAML per agent. When set:
1. Agent receives task via prompt (not inbox polling)
2. Agent executes task, writes results to task file / sends completion message
3. Daemon auto-retires agent after invocation completes
4. Lead spawns a new agent for the next task (fresh context, cached prompt)

## Token Reporting Gap — Provider-Specific Usage Extraction

The daemon's `_extract_usage()` is Claude-specific. It parses:
- `result.modelUsage.{model}.inputTokens/outputTokens/cacheCreationInputTokens/cacheReadInputTokens`
- `result.modelUsage.{model}.contextWindow`

These fields don't exist in Gemini's or Codex's stream-json output. Result: non-Claude agents show `0k/0k` for tokens and get the hardcoded 200k context window limit.

**Observed**: thief (gemini-3-flash) shows `99% HP [0k/0k]` — the `0k/0k` means zero tokens were ever extracted from Gemini's output. The `99%` comes from the daemon's initial boot estimate, not real data. HP is fiction for non-Claude providers.

### What to Fix in minion-factory

| Issue | Fix |
|-------|-----|
| Claude-only token extraction | Each provider should implement `extract_usage(line) -> (input, output, context_window)` method on the provider class, not in the daemon |
| Unknown context window | Provider classes should declare `context_window` as a class-level attribute or config field. Gemini-3-flash = 1M, Codex = varies. Don't default to 200k for all |
| HP is fiction for non-Claude | Until providers report tokens, mark HP as `"HP unknown (no provider telemetry)"` instead of showing fake percentages |
| No usage data = no alerts | Since non-Claude agents never report real tokens, they never trigger HP alerts. A Gemini agent could be at 95% context and nobody would know |

## Daemon Failure Loop — Observed Issue (from live ff1 session)

### The Destructive Retry Loop

When an agent's CLI commands fail (e.g., DB not accessible), the daemon enters an infinite retry loop:

1. Poll detects unread message → invokes provider
2. Provider tries `minion pull-task` → fails (DB error)
3. Provider tries `minion send` → fails (same DB error)
4. Provider turn ends → poll re-triggers (message still unread) → goto 1

**Observed**: 6+ iterations in 60 seconds. Each iteration is a full API call. The agent burns real API credits on a deterministic failure with zero chance of recovery.

**Why it happens**: The poll loop has no circuit breaker. The unread message can't be marked read (requires DB access). So poll keeps delivering the same message, triggering the same failed invocation.

### What to Fix in minion-factory

| Issue | Fix |
|-------|-----|
| No circuit breaker | After N consecutive failed invocations (same message), exponential backoff. After M failures, stop delivering and alert lead |
| No error escalation | Daemon should detect "same error N times" pattern and send alert to lead via a side channel (not the broken DB) |
| No startup validation | Daemon should verify DB access, env vars, and provider connectivity BEFORE entering poll loop. Fail fast, don't fail repeatedly |
| Provider env passthrough | Each provider's shell sandbox may or may not inherit parent env vars. Document per-provider behavior. Codex observed to lose `MINION_COMMS_DB_PATH` |
| Zombie token burn | A 0% HP agent in a failure loop burns unlimited API credits. The HP system should trigger auto-retire when agent is both CRITICAL and failing repeatedly |
| Cumulative token inflation | `hp_input_tokens` grows unbounded during failure loops. Observed: 599k → 4,510k in ~10 minutes (whitemage). Each failed Codex invocation adds ~600k to cumulative count even though no useful work happened. HP display shows `4510k/200k` which is nonsensical — 22x over limit |

## Token Accounting During Failure Loops

When an agent enters a failure loop, the daemon's `_update_hp()` keeps accumulating tokens:
- Each failed invocation reports its `turn_input` and `input_tokens` (cumulative)
- The cumulative counter grows unbounded: 599k → 1.2M → 1.8M → ... → 4.5M in 10 minutes
- HP% is computed from `turn_input` (per-turn), so it stays at 0% correctly
- But the cumulative `hp_input_tokens` becomes meaningless noise

**What to fix**:
- Don't count tokens from failed invocations toward cumulative totals, OR
- Add a `failed_invocation_count` column and track it separately
- Use cumulative tokens as a cost metric (how much was spent), not a health metric
- Display should show `turn_input/limit` for HP, and cumulative separately as "session cost"

## Task State Drift — Message Layer vs DB Layer

### Observed Problem

Agents report task completion via `minion send` (messages) but don't always run `minion update-task` to change DB status. The message layer and task DB drift apart.

**Observed**: redwizard messaged fighter "Task #1 verified and closed" but the DB still shows `status: fixed`. The verbal acknowledgment happened but the state machine wasn't updated. Any agent querying `get-tasks --status closed` would not find this task.

### Why It Happens

1. Agents have two communication channels: messages (informal) and task CRUD (formal)
2. Messages are natural language — agents say "done" or "verified" without necessarily running the corresponding CLI command
3. The daemon doesn't parse message content to auto-update task status
4. Context-limited agents (post-compaction) may forget the task update step

### What to Fix in minion-factory

| Issue | Fix |
|-------|-----|
| State drift | Consider auto-updating task status when specific trigger words appear in messages (e.g., "task #N complete" → auto-transition to `fixed`) |
| No enforcement | `complete-task` command exists but agents use `send` + verbal instead. Make the task completion flow the primary path, not messages |
| Unrecorded activity | whitemage's 33 invocations show `activity_count: 0` because DB is unreachable. Failed agents leave no trace in task records |
| No Phase 3/4 tasks | Lead created `.work/tasks/` files for future phases but hasn't registered them in DB yet. Task files and DB are separate systems that can drift |

## Observability Gap — Silent Failures

### The Invisible Zombie Problem

When an agent can't reach the DB, ALL of its communication channels are broken simultaneously:
- Can't `minion send` (DB write required)
- Can't `minion update-task` (DB write required)
- Can't trigger HP alerts (DB write required)
- Can't mark inbox messages as read (DB write required)

The agent is completely invisible to the coordination layer. The lead has no way to know the agent is failing unless they:
1. Manually check tmux panes (human action required)
2. Notice the agent hasn't reported in N minutes (requires lead to track expected report times)
3. Check `party-status` and see `activity_count: 0` (but this is also true for idle agents)

**Observed**: whitemage ran 33+ failed Codex invocations over 10+ minutes. Zero visibility in the comms system. The only evidence was in tmux pane output and error logs on disk.

### What to Fix in minion-factory

| Issue | Fix |
|-------|-----|
| DB-dependent alerting | Add a side channel for critical alerts that doesn't require DB. Options: write to a well-known file path, use OS signals, or write to stderr (which the daemon can parse) |
| No heartbeat expectation | Lead should be able to set "expect report from X within N minutes" and get alerted if it doesn't arrive |
| Daemon error detection | The daemon already sees the agent's failed commands in stdout. It should detect repeated failures and write a status file or alert the lead directly (daemon has its own DB access) |
| Compaction amnesia | After context compaction, the lead loses the battle plan and task assignments. `cold-start` should re-inject: active tasks, agent assignments, last known status, and any overdue reports |

## Compaction Recovery — Observed Behavior

### How It Works Today

1. Daemon detects compaction marker in agent's stream-json output
2. Sets `inject_history_next_turn = True`
3. Next invocation, the RollingBuffer snapshot (raw stream-json history) is prepended to the prompt
4. RollingBuffer: 100k tokens default (~400k chars), FIFO eviction. Stores raw stream output (tool calls, file contents, model responses)

### What Was Observed

Redwizard (Opus lead) hit compaction twice in 18 minutes:
- **v=2 (T+5m)**: 141k chars streamed. Compaction detected. History re-injected v=3.
- **v=4 (T+17m)**: 11k chars streamed. Compaction again. History re-injected v=5.

**Recovery quality**: Good. Post-compaction, redwizard:
- Re-read `.work/README.md` battle plan (persistent file)
- Ran `party-status` to get current HP dashboard
- Queried `get-tasks` for assignment state
- Noticed whitemage at 0% HP and reassigned Task #4
- Sent accurate sitrep with full Phase 2 status

**Why it worked**: The combination of file-based state (`.work/` directory) + DB queries (tasks, agents) + rolling buffer history gave enough context to resume coordination. The rolling buffer alone wouldn't be sufficient — it's raw stream-json, not structured state.

### What Could Be Better

| Issue | Fix |
|-------|-----|
| Raw history is noisy | Rolling buffer contains raw stream-json (tool calls, file contents, etc.). A structured state summary would be more token-efficient |
| No `cold-start` for leads | The `minion cold-start` command exists but redwizard didn't use it — it manually queried party-status + get-tasks. Cold-start should synthesize a compact "here's where you are" briefing |
| Double compaction in 18m | Opus at 200k context is tight for a lead managing 4 agents + reading source files. Consider: leads should delegate file reading to workers, not read files themselves |
| History buffer isn't provider-aware | 100k tokens * 4 chars/token = 400k chars. But Gemini's tokenizer and Claude's tokenizer produce different token counts for the same text. Buffer size should be tuned per provider |

### Tmux Output vs Agent Context — They're Different

The tmux pane shows stream output (what humans see). The agent's actual context is managed by the provider (Claude/Gemini/Codex) internally. The daemon feeds prompts via stdin; the agent's conversation history is whatever the provider maintains.

The rolling buffer captures stdout (what goes to tmux) and replays it as text on compaction. But this is a **lossy reconstruction** — the agent had structured tool calls and responses; the buffer has flattened text. The provider's internal context management (Claude's system prompt caching, Gemini's context window) operates independently.

**Implication**: After compaction, the injected history is the daemon's best guess at what the agent was doing, reconstructed from stdout. It's not the provider's actual context. Information that was in the provider's context but not reflected in stdout (e.g., system prompt evolution, tool definitions) is lost.

## Line Markers in Tmux Output

Tmux panes currently mix three sources of output with no consistent markers:
1. **Daemon log lines**: `[2026-02-20 09:40:25] [agentname] message` — has timestamp + agent prefix
2. **Model stream output**: Raw text/JSON from Claude/Gemini/Codex — no prefix, no attribution
3. **Stream boundary markers**: `=== model-stream start/end: agent=X cmd=Y v=N ts=HH:MM:SS ===`

For observability (both human viewers and terminal-lead agents watching via `tmux capture-pane`):
- The stream boundary markers already identify agent, provider command, invocation count, and timestamp — that's good
- But raw model output between markers has no line-level attribution
- When the terminal lead captures pane output, it can't programmatically extract "what did fighter write in this invocation" without parsing the stream boundaries

**Consider**: Add a terse prefix to every line within a model stream (e.g., `[f:v5]` for fighter invocation 5). This would let `grep` extract per-agent, per-invocation output from captured pane buffers. Cost: a few chars per line. Benefit: machine-parseable observability for coordinator agents.

## Package Name Collision — `minion`

### Observed Problem

The new package uses `minion` as both the Python package name (`src/minion/`) and CLI entry point (`minion = "minion.cli:cli"`). This collides with the existing `minion-commsv2` installation which also provides a `minion` CLI command (from `minion_comms.cli:cli`).

**Observed**: blackmage ran bare `pytest` instead of `uv run pytest`. Tests failed with `ModuleNotFoundError: No module named 'minion'` because no `minion` package exists in the global Python env — only in the `uv`-managed venv. The task spec said `uv run pytest tests/` but the agent used `pytest` directly.

### Implications

1. **Dev workflow**: Must always use `uv run` to get the local editable install. Bare `python -c "import minion"` fails outside the venv
2. **Coexistence**: Can't have both `minion-commsv2` and `minion-factory` installed in the same env — both provide `minion` CLI
3. **Agent confusion**: Agents may invoke bare `pytest` or `python` instead of `uv run` variants, especially after compaction when they lose the "use uv" context
4. **PyPI risk**: `minion` is a generic name — may collide with existing packages

### What to Fix

| Issue | Fix |
|-------|-----|
| Agent forgets `uv run` | Add `uv run pytest` to CLAUDE.md "Running Tests" section. Make it the ONLY documented way to run tests |
| Package name generic | Consider `minion-factory` as the distribution name but keep `minion` as the import name (this is the current setup in pyproject.toml — fine) |
| Coexistence during migration | Document that `minion-commsv2` must be uninstalled before installing `minion-factory` in the same env |

## Privilege Escalation — Daemon ENV_CLASS Override

### Observed Problem

`daemon.py:854` sets `ENV_CLASS = "lead"` for ALL shell commands executed by the daemon on behalf of any agent. This means a coder-class agent running through the daemon can execute lead-only commands (like `stand-down`) because the env var overrides the auth check.

**Observed**: fighter (coder class) called `minion stand-down`, dismissing the entire party. The auth system in `stand_down.py:23` checks `Only lead-class agents can stand_down` — but the daemon's env override defeated this check. Commander (redmage) had to manually clear the flag via direct SQLite access (`DELETE FROM flags WHERE key = 'stand_down'`) and respawn the party.

### What to Fix

| Issue | Fix |
|-------|-----|
| Blanket `ENV_CLASS = "lead"` | Daemon should pass the agent's actual class, not hardcode "lead" for everything |
| No recovery CLI | Need `minion clear-stand-down` or `minion resume-party` for leads to undo stand-down without direct DB access |
| No command allowlist per class | Instead of env-based auth, use a command allowlist in the agent's DB record. Daemon checks before executing |
| Destructive commands need confirmation | `stand-down` should require a confirmation flag (`--confirm`) or only work when sent by registered lead agents |

## Workspace Spawning — Provider Environment Requirements

### Observed Problem

Each provider runs agents in a different execution environment with different constraints on filesystem access, env vars, and process isolation. The spawn system doesn't account for these differences — it spawns all agents the same way regardless of provider.

**Observed failures by provider**:

| Provider | Issue | Root Cause |
|----------|-------|------------|
| **Codex (gpt-5.3-codex)** | `sqlite3.OperationalError: unable to open database file` | Codex sandbox blocks write access + strips env vars. Agent runs `minion` CLI inside sandbox — CLI can't reach DB. **FIXED**: `--sandbox workspace-write --add-dir ~/.minion_work -c shell_environment_policy.inherit=all` |
| **Gemini (gemini-3-flash)** | `read_file` blocked on paths outside project dir | Gemini workspace restricts filesystem to project directory. Agent self-recovered by using shell `cat` as fallback. **No `--add-dir` equivalent** — Gemini's restriction is tool-level, not shell-level. Shell commands (`cat`, `minion` CLI) work; only Gemini's native `read_file` tool is blocked. |
| **Claude (claude-sonnet-4-6)** | `uv run pytest` vs bare `pytest` — ModuleNotFoundError | Not provider-specific, but agents forget to use `uv run` after compaction. Task specs say `uv run pytest` but agents run `pytest` directly |

### What's Fixed

| Issue | Resolution |
|-------|------------|
| Codex DB access | `codex.py` now passes `--sandbox workspace-write --add-dir ~/.minion_work -c shell_environment_policy.inherit=all`. Agent's shell (including `minion` CLI child processes) can reach the DB and inherit env vars. |

### Remaining Gaps

| Issue | Fix |
|-------|-----|
| No per-provider env validation | `spawn-party` should validate that each provider can access the DB, project files, and required env vars BEFORE starting the poll loop. Fail fast with clear error |
| Provider capability matrix | Define per-provider: `{can_access_db: bool, can_read_outside_project: bool, env_passthrough: bool, shell_sandbox: bool}`. Use this to gate agent assignments |
| Gemini-specific: native tool path restrictions | Gemini's `read_file` tool rejects paths outside project dir. Shell commands work fine — `minion` CLI, `cat`, etc. are unaffected. Document in Gemini agent bootstrap: "use Bash tool for files outside project dir" |
| Agent bootstrap awareness | Each agent's system prompt should include provider-specific instructions (e.g., "always use `uv run`", "use `cat` not `read_file` for paths outside project") |

## Real-Time Agent Observability — Without Tmux

### The Problem

The lead agent (or UI) has no way to see what agents are doing *during* a turn. All current observability is post-hoc:
- `party-status`: updates only when agent's turn ends
- `check-inbox`: messages sent only after work completes
- `get-tasks`: updates only if agent explicitly ran `update-task`

Mid-turn, the only visibility is `tmux capture-pane` — which requires a terminal-transport lead watching manually. A daemon-transport lead or the UI has zero real-time visibility.

**Observed**: Commander (redmage) had to run `tmux capture-pane -t crew-ff1.3 -p | tail -20` repeatedly to check if blackmage was writing tests, hit errors, or stalled. This doesn't scale and can't be automated by the lead agent without tmux access.

### What the Daemon Already Knows

The daemon reads every agent's stdout in real time (for rolling buffer). It already has:
- Every line of model stream output
- Stream start/end markers with invocation count
- Tool call names and arguments (in stream-json)
- Errors and stack traces
- File paths being read/written

This data exists — it's just not exposed to the coordination layer.

### Proposed: Activity Stream

| Approach | Description | Cost | Benefit |
|----------|-------------|------|---------|
| **Stream tail file** | Daemon tees last N lines of each agent's stdout to `~/.minion_work/streams/<agent>.tail` (ring buffer file). Lead or UI reads this file | Minimal — just file I/O on existing data | Real-time visibility without DB writes. Works for any consumer (CLI, UI, lead agent) |
| **Activity event log** | Daemon parses stream for key events (file_write, command_run, error, task_mention) and writes to `activity_events` DB table | Medium — parser + DB writes | Structured queryable history. UI can show timeline |
| **Heartbeat column** | Daemon writes `last_activity_summary` to agents table every N seconds during active stream | Low — periodic DB update | `party-status` shows what agent is doing right now, not just last turn |
| **Push to lead** | Daemon sends message to lead on key events (error, long stall, task completion) | Low — conditional message send | Proactive alerting. Lead doesn't need to poll |

### Minimum Viable: Heartbeat + Stream Tail

1. **Heartbeat**: Every 30s during an active turn, daemon updates `agents.activity_summary` with a one-liner (e.g., "writing tests/test_cli.py", "reading src/minion/cli.py", "ERROR: ModuleNotFoundError"). `party-status` displays this.
2. **Stream tail**: Daemon writes last 50 lines of each agent's stream to a well-known file path. `minion watch <agent>` reads this file. UI polls it.

This gives both programmatic observability (heartbeat in DB, queryable) and raw observability (tail file, human-readable) without requiring tmux.

## Common Area — Shared Agent Workspace

### The Problem

Agents currently operate in silos. Each has a private inbox, private context, private HP. The only shared state is the DB — but agents discover it through specific commands (`get-tasks`, `party-status`), not through a unified common area.

**Observed**: The `.work/` directory served as an ad-hoc common area during the ff1 merge — battle plan, task specs, observation log. Agents read these files to recover context after compaction. But this was manual setup by the commander, not a framework feature. A cold-starting agent wouldn't know `.work/` exists unless told.

### What "Common Area" Means

A discoverable, shared workspace that every agent can find via `minion --help`:

| Feature | CLI Command | What It Provides |
|---------|-------------|-----------------|
| **Activity feed** | `minion activity` | Unified stream of all agent events — messages sent, tasks updated, files written, errors. Not per-inbox, not per-agent. Everything in one timeline |
| **Watch agent** | `minion watch <agent>` | Real-time stream tail of a specific agent. Replaces `tmux capture-pane` |
| **Watch all** | `minion activity --live` | All agents' activity interleaved. The "war room" view |
| **Bulletin board** | `minion announce <message>` | Lead posts to shared board. All agents see it on next `check-inbox` or `cold-start`. Unlike `send --broadcast`, this persists and is re-readable |
| **Workspace state** | `minion workspace` | What files are claimed, what tasks are in flight, what agents are active. One command, full picture |
| **Battle plan** | `minion get-battle-plan` | Already exists — but should auto-include workspace state + task summary |

### Discovery Principle

An agent bootstrapping cold should be able to run:
```
minion --help
minion activity
minion workspace
```

And understand: who's on the team, what they're doing, what's been done, what's left. No tribal knowledge about file paths, tmux sessions, or `.work/` directory conventions.

### Implementation Notes

- The activity feed is built from data the daemon already captures (stream events, DB writes). It just needs a unified query layer
- `minion watch` reads the stream tail file (see "Stream Tail" above). No new infrastructure
- Bulletin board is a simple DB table: `announcements(id, from_agent, content, timestamp, expires_at)`
- `minion workspace` is a composite view: `party-status` + `get-tasks --open` + `get-claims` + recent activity. Fused COP (like `sitrep` but discoverable)

## Agent Observability — Industry Patterns

Research conducted 2026-02-20. Concrete patterns from production multi-agent frameworks.

### 1. Data Captured Per Agent Turn

Every major framework converges on the same per-turn telemetry envelope:

| Field | Who Captures It | Notes |
|-------|----------------|-------|
| `agent_id`, `agent_name` | All frameworks | Human-readable name + unique ID |
| `conversation_id` / `thread_id` | LangSmith, AG2, AgentOps | Groups turns into sessions |
| `input_messages` (structured) | OTEL GenAI semconv, AG2 | Full prompt including system, user, assistant messages |
| `output_messages` | OTEL GenAI semconv, AG2 | Model response |
| `input_tokens`, `output_tokens` | All | Per-turn token counts |
| `model_name`, `provider` | All | Which model handled this turn |
| `tool_calls[]` (name, args, result) | LangSmith, AgentOps, AG2 | Child spans under the agent turn span |
| `latency_ms` | All | Wall-clock time for the turn |
| `cost_usd` | AgentOps, LangSmith, Helicone | Computed from token counts + model pricing |
| `error_type` | OTEL semconv | Conditionally present on failures |
| `temperature`, `max_tokens` | OTEL semconv | Request parameters |
| `context_window` | Claude provider only (observed) | Most frameworks don't capture this yet |

**Key insight**: AG2 (AutoGen) defaults to NOT capturing request/response messages on LLM spans — opt-in only, for data sensitivity. LangSmith captures everything by default.

### 2. OpenTelemetry GenAI Semantic Conventions (Emerging Standard)

OTEL is defining the standard span model for agent systems. Status: "Development" (not stable yet).

**Span types defined** ([semconv spec](https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-agent-spans/)):

| Span | `gen_ai.operation.name` | Contains |
|------|------------------------|----------|
| Create Agent | `create_agent` | Agent registration, config |
| Invoke Agent | `invoke_agent` | One agent turn — parent of LLM + tool spans |
| Execute Tool | `execute_tool` | Single tool call within a turn |

**Agent attributes** (all `gen_ai.agent.*`):
- `id`, `name`, `description`, `version`

**Proposed agentic extensions** ([Issue #2664](https://github.com/open-telemetry/semantic-conventions/issues/2664)):
- `gen_ai.task.*` — task ID, status, dependencies
- `gen_ai.team.*` — team/crew metadata
- `gen_ai.artifact.*` — files/outputs produced
- `gen_ai.memory.*` — shared memory access

**AG2 (AutoGen) implementation** ([blog post](https://docs.ag2.ai/latest/docs/blog/2026/02/08/AG2-OpenTelemetry-Tracing/)):
- Custom span type attribute: `ag2.span.type` = `{conversation, agent, llm, tool, code_execution, human_input, speaker_selection}`
- Hierarchy: `conversation` → `invoke_agent` → `chat` (LLM) → `tool`
- Group chat adds `speaker_selection` spans showing candidate agents and selection reasoning
- Exports to any OTEL-compatible backend (Jaeger, Grafana Tempo, Datadog, Arize Phoenix)

**Takeaway for minion-factory**: Adopting OTEL GenAI semconv now means traces are compatible with Jaeger, Grafana, Datadog, Phoenix, etc. out of the box. The daemon already has the data — it just needs to emit spans instead of (or in addition to) writing to SQLite.

### 3. How Frameworks Expose Observability Data

| Framework | Transport | Consumer |
|-----------|-----------|----------|
| **LangSmith** | Async callback handler → HTTP POST to LangSmith collector | Web dashboard (polling), no WebSocket observed |
| **AgentOps** | 2-line SDK init, auto-instruments LLM calls → HTTP to AgentOps cloud | Web dashboard with session/trace/span drill-down |
| **AG2/AutoGen** | OTEL spans → any OTEL collector (gRPC/HTTP) | Jaeger, Grafana, Phoenix — whatever backend you configure |
| **CrewAI** | Pluggable: AgentOps, MLflow, or OpenLIT (OTEL-native) | Depends on chosen backend |
| **Arize Phoenix** | OTEL traces via HTTP | Self-hosted web UI, real-time dashboard |
| **Helicone** | Proxy-based (sits between app and LLM API) | Web dashboard, no SDK needed |
| **Braintrust** | SDK + BTQL query language for log analysis | Web dashboard + "Loop" AI assistant that analyzes traces |

**Pattern**: Nobody uses WebSocket for trace delivery. All use async HTTP POST (fire-and-forget from the agent process) to a collector. The UI then polls the collector/DB. Real-time feel comes from short poll intervals (1-5s), not push.

**Exception**: LangGraph Platform has a "Monitoring" tab with real-time deployment metrics, but traces are still async.

### 4. UI Patterns for Watching Multiple Agents

**LangSmith** (most mature agent UI):
- **Trace tree view**: Nested spans — click a trace, see the full tree of runs (LLM calls, tool calls) as collapsible nodes
- **Thread view**: Groups traces by conversation/thread. Shows chronological progression of an agent session
- **Monitoring tab**: Aggregate metrics — latency p50/p95, error rates, token usage over time
- **"Polly" AI assistant**: Chat with your traces — ask "why did this agent fail?" and it analyzes the span data

**Arize Phoenix**:
- **Distributed trace view**: Standard OTEL waterfall (like Jaeger) adapted for LLM spans
- **Trajectory analysis**: Multi-step agent execution shown as a path through decision points
- **Drift detection**: Alerts when agent behavior diverges from baseline

**AgentOps**:
- **Session view**: One page per agent session showing timeline of events (LLM call, tool use, error)
- **Multi-agent replay**: Interleaved timeline of all agents in a session — closest to a "war room" view
- **Cost attribution**: Per-agent, per-session, per-tool cost breakdown

**Common patterns across all**:
1. **Trace tree** (nested spans) is universal — every platform has it
2. **Timeline/waterfall** for sequential execution within one agent
3. **Interleaved timeline** for multi-agent — agent events color-coded on a shared timeline
4. **Aggregate dashboard** — charts for latency, cost, error rate over time
5. **Drill-down**: dashboard → session → trace → span → raw messages

**What's missing everywhere**: No framework has a good "live war room" showing all agents doing work simultaneously with real-time updates. All UIs are post-hoc analysis tools. The closest is AgentOps' session replay, but it's replay, not live.

### 5. Shared State / Blackboard Patterns

**How multi-agent systems handle shared context**:

| Pattern | Used By | Mechanism | Discovery |
|---------|---------|-----------|-----------|
| **Shared message bus** | AutoGen GroupChat | All agents see all messages in the group. Context = full conversation history | Implicit — agents are in the group |
| **Blackboard** | Confluent event-driven patterns, academic LLM-MAS | Central knowledge store with typed entries (hypotheses, evidence, constraints, results). Agents poll for changes matching their activation conditions | Agents define `should_activate(blackboard)` predicates |
| **Shared memory object** | AutoGen Memory protocol | `ListMemory` — chronological list appended to model context. Agents call `query()` and `add()` | Injected at agent creation via `memory=` param |
| **Event-sourced log** | Confluent Kafka-based pattern | Append-only event stream. Agents produce/consume events. Keyed by originating agent | Agents subscribe to topics |
| **Persistent files** | minion-commsv2 `.work/` dir (ad-hoc) | Agents read/write files in a shared directory. Recovery via file re-read | Convention-based (must know the path) |
| **DB-backed state** | minion-commsv2 SQLite | Tasks, messages, battle plans in DB. Agents query via CLI | CLI discovery (`minion --help`) |
| **Memory-as-a-Service** | Research (2025) | Memory decoupled from agents, exposed as callable service with access control | API calls to memory service |
| **Collaborative Memory** | Research (2025) | Two-tier: private + shared memory. Dynamic bipartite access graph controls who sees what | Access graph managed by controller |

**Blackboard implementation approaches** ([ReputAgent](https://reputagent.com/patterns/blackboard-pattern)):
1. **In-memory**: Fast, single-session. Dict/list in the orchestrator process
2. **Database-backed**: Persistent across sessions. SQL table with typed entries
3. **Event-sourced**: Append-only log. Full history + replay capability

**Blackboard conflict resolution**: Voting, confidence scoring, or expert arbitration when agents disagree.

**Confluent's four event-driven multi-agent patterns**:
1. **Orchestrator-Worker**: Central coordinator assigns tasks, workers report back (closest to minion-factory's current model)
2. **Hierarchical**: Tree of supervisors, each managing a sub-team
3. **Blackboard**: Shared knowledge base, agents activate on conditions
4. **Market-based**: Agents bid on tasks, highest-capability agent wins

### 6. Implications for minion-factory

**What to adopt**:

| Decision | Rationale |
|----------|-----------|
| **OTEL spans from daemon** | The daemon already streams every agent's output. Emitting OTEL spans (`invoke_agent` → `chat` → `tool`) makes traces compatible with Jaeger/Grafana/Phoenix for free. Keep SQLite as the primary store, add OTEL as opt-in export |
| **Per-turn envelope in DB** | Add an `agent_turns` table capturing the standard envelope (agent_id, turn_input_tokens, turn_output_tokens, tool_calls_json, latency_ms, error_type, model). This is the raw material for any UI |
| **Activity event stream** | The "activity feed" already proposed in the Common Area section aligns with AgentOps' session timeline. Implement as an `activity_events` table with type-tagged rows (llm_call, tool_use, file_write, error, task_update) |
| **Heartbeat for live view** | No production framework has solved live multi-agent monitoring. The proposed heartbeat + stream tail approach (daemon writes `activity_summary` every 30s) is novel and fills a real gap |
| **Blackboard = announcements + battle plan** | The existing `announcements` table + `battle_plan` + `.work/` directory already form an ad-hoc blackboard. Formalize it: typed entries (hypothesis, decision, constraint, artifact), activation conditions for agents |
| **Skip proxy-based observability** | Helicone's proxy pattern doesn't fit — minion-factory agents talk to LLM CLIs, not HTTP APIs. Instrument at the daemon level instead |
| **Cost tracking per agent** | Every platform does this. Add `cost_usd` column to `agent_turns`, computed from provider pricing tables. Show in `party-status` |

**What NOT to adopt**:
- Complex OTEL collector infrastructure (overkill for SQLite-first system). Export spans to a file or optional collector, not required
- Memory-as-a-Service (research-grade, not production-ready)
- Market-based task allocation (minion-factory uses lead-assigned tasks, which matches orchestrator-worker pattern)

### Sources

- [CrewAI Observability Overview](https://docs.crewai.com/en/observability/overview)
- [CrewAI AgentOps Integration](https://docs.crewai.com/how-to/agentops-observability)
- [CrewAI OpenLIT Integration](https://docs.crewai.com/how-to/openlit-observability)
- [AutoGen Tracing & Observability](https://microsoft.github.io/autogen/stable//user-guide/agentchat-user-guide/tracing.html)
- [AG2 OpenTelemetry Tracing](https://docs.ag2.ai/latest/docs/blog/2026/02/08/AG2-OpenTelemetry-Tracing/)
- [AgentOps GitHub](https://github.com/AgentOps-AI/agentops)
- [LangSmith Observability](https://www.langchain.com/langsmith/observability)
- [OTEL GenAI Agent Spans Semconv](https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-agent-spans/)
- [OTEL Agentic Systems Proposal (Issue #2664)](https://github.com/open-telemetry/semantic-conventions/issues/2664)
- [OTEL AI Agent Observability Blog](https://opentelemetry.io/blog/2025/ai-agent-observability/)
- [Confluent: Four Design Patterns for Event-Driven Multi-Agent Systems](https://www.confluent.io/blog/event-driven-multi-agent-systems/)
- [Blackboard Pattern — ReputAgent](https://reputagent.com/patterns/blackboard-pattern)
- [Arize Phoenix GitHub](https://github.com/Arize-ai/phoenix)
- [Braintrust AI Observability Guide 2026](https://www.braintrust.dev/articles/best-ai-observability-tools-2026)
- [Helicone LLM Observability Guide](https://www.helicone.ai/blog/the-complete-guide-to-LLM-observability-platforms)
- [AutoGen Memory & RAG](https://microsoft.github.io/autogen/stable//user-guide/agentchat-user-guide/memory.html)
- [Datadog OTEL GenAI Semantic Conventions](https://www.datadoghq.com/blog/llm-otel-semantic-convention/)

## Lead Failure — Leaderless Recovery

### The Problem

The lead agent is a single point of failure. If the zone lead (redwizard) goes down — compaction, crash, rate limit, or context death — the entire party stalls:

1. **No task dispatch** — workers can only receive assignments from lead. No lead = no new work
2. **No coordination** — all inter-worker comms route through lead. Workers can't talk to each other directly
3. **No verification** — completed work sits unverified until lead recovers
4. **No escalation path** — workers have no mechanism to report "lead is unresponsive" to commander
5. **Idle burn** — workers keep sending "standing by" to a dead inbox, burning API calls with zero productive output

**Observed**: When fighter called unauthorized stand-down, all daemon agents (including redwizard) went down simultaneously. Only the terminal-transport commander (redmage) survived because it wasn't running through the daemon. Recovery required direct DB manipulation + manual respawn. If commander had also been a daemon agent, total party death with no recovery path.

### What Happens Today When Lead Goes Down

```
T+0:   Lead stops responding (compaction / crash / rate limit)
T+30s: Workers poll, no new messages, send "standing by" to lead
T+60s: Workers poll again, same result
T+5m:  Workers still idle. No one knows lead is down.
T+10m: Human notices tmux pane is stuck or checks party-status
T+??m: Human manually intervenes
```

No automated detection. No automated recovery. No fallback.

### Proposed: Tiered Recovery

| Tier | Trigger | Action |
|------|---------|--------|
| **1. Heartbeat timeout** | Lead hasn't updated `last_seen` in N minutes (e.g., 5m for Opus, 3m for Sonnet) | Daemon flags lead as `unresponsive` in agents table. Workers see this on next `party-status` |
| **2. Commander escalation** | Worker detects lead unresponsive | Worker sends message directly to commander (skip lead). Commander gets alert: "redwizard unresponsive, fighter has pending work" |
| **3. Pull-based fallback** | Lead unresponsive > N minutes AND task queue has work | Workers switch to `minion pull-task` mode — grab next unclaimed task from queue without lead assignment. Self-directed but still class-gated |
| **4. Acting lead** | Lead unresponsive > 2N minutes, commander also unresponsive | Highest-HP agent with lead-capable class becomes acting lead. Announced via bulletin board. Temporary until real lead recovers |
| **5. Graceful degradation** | All leads down | Workers continue current task if in-progress. Completed tasks stay in queue. No new assignments. Party enters "autonomous mode" — each worker pulls from queue, self-verifies, logs to raid log |

### Pre-loaded Task Queue (Enables Tiers 3-5)

The key enabler for leaderless recovery is **front-loading the task queue**. Instead of lead dispatching one task at a time:

**Current (push model)**:
```
Lead assigns Task A to fighter → fighter completes → reports to lead → lead assigns Task B → ...
```

**Proposed (pull model with pre-loaded queue)**:
```
Lead front-loads Tasks A, B, C, D with priorities and dependencies
Workers run: minion pull-task → get next available task matching their class
Lead monitors and adjusts priorities, but workers don't block on lead for dispatch
```

`pull-task` already exists in the CLI but wasn't used during the ff1 session. Everyone used push-based assignment via messages. The pull model eliminates the dispatch bottleneck AND enables autonomous operation when lead goes down.

### Worker-to-Worker Communication

Currently workers can `minion send` to each other, but the convention is to route through lead. In leaderless mode:

- Workers should be able to send directly to peers for coordination
- A "buddy system" — each worker has a designated peer to check on if they stall
- CC to lead inbox (so lead sees the conversation when it recovers) but don't block on lead acknowledgment

### Implementation Notes

- Heartbeat timeout is cheap — daemon already writes `last_seen` on every poll cycle. Just add a threshold check
- Commander escalation needs a `fallback_lead` field in crew YAML so workers know who to contact
- Pull-based task queue requires tasks to be created with `class_restriction` and `depends_on` fields so workers can self-filter
- Acting lead election should be simple: highest HP, lead-capable class, most recent `last_seen`. No consensus protocol needed — first to claim wins

## Role-Based Tool Surface — Factory as Source of Truth

### The Problem

`auth.py` defines `VALID_CLASSES` and `TOOL_CATALOG` mapping commands to allowed classes. But 36 of 53 commands use `VALID_CLASSES` (all classes) — meaning a worker sees the same 36 commands as a lead, plus the lead gets 17 more. That's too flat.

**Observed**: Fighter (coder) had access to `stand-down` because the daemon overrode its class to `lead`. Even without the daemon bug, a coder seeing `stand-down` in its `tools` output is an invitation to misuse.

### What the Factory Should Define

The factory is the source of truth for:
1. **What classes exist** — not just RPG names, but workflow roles with defined responsibilities
2. **What tools each class gets** — tight, per-role command sets. Not "everyone gets everything"
3. **What models each class can use** — already in `CLASS_MODEL_WHITELIST`, needs updating for new roles
4. **What briefing files each class reads** — already in `CLASS_BRIEFING_FILES`
5. **What staleness thresholds apply** — already in `CLASS_STALENESS_SECONDS`

### Current State (auth.py)

```python
VALID_CLASSES = {"lead", "coder", "builder", "oracle", "recon"}
```

36 of 53 commands available to ALL classes. Only 17 are lead-gated. `claim-file` and `release-file` gated to coder+builder only.

### What to Fix

| Fix | Detail |
|-----|--------|
| Tighten TOOL_CATALOG | Each command explicitly lists which roles need it. No more `VALID_CLASSES` as default. Every command earns its slot per role |
| Add new roles | When role architecture evolves (planner, dispatcher, worker, verifier, oracle), update `VALID_CLASSES` and `TOOL_CATALOG` |
| Bootstrap token budget | `minion tools` output goes into agent context. Fewer commands = fewer tokens burned on bootstrap. Measure: how many tokens does the tools output cost per class? |
| Role definition in factory | `auth.py` should be readable as a spec: "here are the roles, here's what each one can do." Not just a permission check — a design document |
| **Single source of truth — for everything** | The pattern of "5 separate dicts keyed by the same thing" repeats across the codebase. Not just classes — providers, triggers, statuses, transports. Every entity whose properties are scattered across multiple dicts should be consolidated into one definition per entity. **Principle**: If you add a new X, you should update ONE place, not N places. If you read about X, you look in ONE place. Applies to: classes (tools, models, staleness, briefing), providers (command builder, env reqs, capabilities), task statuses (transitions, allowed classes), trigger words (handler, severity), transport types (spawn method, poll behavior) |

## Cross-Reference Audit — Source Repos vs Factory

Systematic comparison of all 3 source repos against what was ported to minion-factory. Conducted 2026-02-20.

### minion-commsv2 → factory: COMPLETE

All 46 CLI commands ported. All public functions ported. All modules present:
- cli.py, auth.py, db.py, comms.py, monitoring.py, filesafety.py, warroom.py, triggers.py, lifecycle.py, polling.py, fs.py, defaults.py
- crew/ subpackage (spawn.py, lifecycle.py, config.py, _tmux.py, daemon.py, terminal.py)

**Status: 100% ported.**

### minion-swarm → factory: PARTIAL

| Component | Ported? | Notes |
|-----------|---------|-------|
| AgentDaemon (runner.py) | YES | Core poll loop, HP tracking, compaction detection |
| RollingBuffer (buffer.py) | YES | Token-aware FIFO buffer |
| CommsWatcher (watcher.py) | YES | Legacy watcher mode (deprecated) |
| SwarmConfig / AgentConfig (config.py) | YES | In crew/config.py |
| Providers (claude, gemini, codex, opencode) | YES | All 4 + base + __init__ registry |
| spawn.py (tmux/terminal spawning) | YES | In crew/spawn.py + crew/_tmux.py + crew/terminal.py |
| **CLI: `start` (start individual agent)** | **NO** | spawn-party starts all, but no individual agent start |
| **CLI: `stop` (graceful stop with SIGTERM/SIGKILL)** | **NO** | Only retire-agent (sets flag) and stand-down (whole party). No PID-based process kill |
| **CLI: `status` (daemon PID table)** | **NO** | party-status shows agent state but not daemon process info (PID, alive, uptime) |
| **CLI: `logs` (tail agent log)** | **NO** | No equivalent. This is the observability gap — must use tmux capture-pane |
| **CLI: `init` (seed config)** | **NO** | No config initialization command |
| **`_run-agent` (internal daemon entry)** | **UNCLEAR** | Need to verify how daemon subprocess is launched |

### minion-tasks → factory: PARTIAL

| Component | Ported? | Notes |
|-----------|---------|-------|
| dag.py (Stage, TaskFlow, Transition) | YES | DAG query layer intact |
| loader.py (load_flow, list_flows) | YES | YAML inheritance resolution |
| _schema.py (validation constants) | YES | |
| crud.py (task CRUD) | YES | But uses commsv2's task model, not minion-tasks' TaskDB |
| **TaskDB class** | **NO** | minion-tasks has a separate persistence layer with projects, transitions audit log. Not merged with commsv2 db.py |
| **Project management (create/list/get project)** | **NO** | minion-tasks supports multi-project. Factory has no project concept |
| **Transitions audit log** | **NO** | TaskDB.get_transitions() returns full history of who moved a task through which stages. Factory tracks task status but not transition history |
| **CLI: `claim-task`** | **NO** | Different from `pull-task`. claim-task in minion-tasks is DAG-aware |
| **CLI: `transition`** | **NO** | Manual stage transition with validation |
| **CLI: `show-flow`** | **NO** | Visualize a flow's stages and transitions |
| **CLI: `next-status`** | **NO** | Query what status a task can move to next |
| **CLI: `transitions`** | **NO** | View transition history for a task |
| **Task flow YAML search paths** | **PARTIAL** | loader.py searches env var → ~/.minion-tasks/ → sysconfig. Needs update to minion paths |

### Summary of Gaps

**Critical (affects core functionality):**
1. **TaskDB not merged** — DAG engine has no persistence. Flow stages exist in YAML, task CRUD exists in db.py, but the bridge (TaskDB with projects + transitions) is missing
2. **No daemon process management** — can't start/stop/status individual daemons. Only whole-party operations
3. **No `logs` command** — no way to tail agent output from CLI. Forces tmux dependency

**Important (affects usability):**
4. **No project management** — multi-project support from minion-tasks not carried over
5. **No transition audit** — who moved task through which stages is not recorded
6. **No `show-flow` / `next-status`** — agents can't discover valid transitions without reading YAML
7. **No config `init`** — no way to scaffold a new crew config from CLI

**Minor (nice to have):**
8. **Task flow search paths** — loader.py may reference old ~/.minion-tasks/ path
9. **`claim-task` vs `pull-task`** semantics — may need reconciliation

---

## Poll Loop — Tight Loop / No Backoff

**Observed**: Fresh ff1 spawn from factory. All 5 daemon agents log "polling for messages..." ~5 times per second in tmux. Wall of spam, burns CPU for zero value.

**Root cause**: `minion poll` crashes on every call — `ModuleNotFoundError: No module named 'minion.flow_bridge'` (polling.py:77). Module was never ported from source repos. Daemon catches the crash (exit code 1), returns None, and the while loop at runner.py:168-169 does `continue` with no sleep → immediate retry → tight loop.

Two fixes needed:
1. **Port `flow_bridge` module** — `polling.py:77` imports `active_statuses()` from it. Find in source repos and port, or stub if simple
2. **Add backoff as defense-in-depth** — `runner.py:168-169`: add `self._stop_event.wait(timeout=5.0)` before `continue` so crashed polls don't tight-loop

**Fix needed**:
- `runner.py`: Add `self._stop_event.wait(timeout=5.0)` before `continue` on line 169 (backoff on empty)
- `polling.py`: Verify `poll_loop()` actually honors `--interval` and `--timeout` — it should block, not return instantly when inbox is empty

**Acceptance**: Tmux panes show "polling for messages..." at most once every 5-30 seconds, not 5 times per second.

**Also observed**: Fighter and blackmage both reported 24% HP immediately after boot (zero work done). This is a bug in HP calculation — fresh agents cannot be at 24%. Either the token counting from the provider result is wrong, the context window denominator is wrong, or boot overhead is being double-counted. Separate issue from poll spam but surfaced during the same spawn.
