# Minion CLI Reference

> Auto-generated from Click introspection — v0.3.38
> Generated: 2026-02-23T00:59:26Z
>
> Regenerate: `minion docs --output docs/`

## Global Options

| Option | Description |
|--------|-------------|
| `--human` | Human-readable output instead of JSON |
| `--compact` | Concise text output for agent context injection |
| `--project-dir`, `-C` | Project directory (default: cwd) |
| `--version` | Show version and exit |

## 1. agent

Join the session, report your state, and manage your identity.

### `minion agent check-activity`

Check an agent's activity level.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--agent` | text | Yes |  |  |

### `minion agent check-freshness`

Check file freshness relative to agent's last set-context. Lead only.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--agent` | text | Yes |  |  |
| `--files` | text | Yes |  |  |

### `minion agent cold-start`

Bootstrap an agent into (or back into) a session.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--agent` | text | Yes |  |  |

### `minion agent fenix-down`

Save session state to disk before context window runs out.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--agent` | text | Yes |  |  |
| `--files` | text | Yes |  |  |
| `--manifest` | text |  |  |  |

### `minion agent register`

Register an agent.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--name` | text | Yes |  |  |
| `--class` | choice | Yes |  |  |
| `--model` | text |  |  |  |
| `--description` | text |  |  |  |
| `--transport` | choice |  | `terminal` |  |

### `minion agent retire`

Signal a single daemon agent to exit gracefully. Lead only.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--agent` | text | Yes |  | Agent to retire |
| `--requesting-agent` | text | Yes |  | Lead requesting retirement |

### `minion agent set-context`

Update context summary and health (tokens used, token limit).

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--agent` | text | Yes |  |  |
| `--context` | text | Yes |  |  |
| `--tokens-used` | integer |  |  |  |
| `--tokens-limit` | integer |  |  |  |
| `--hp` | integer |  |  | Self-reported HP 0-100 (skips daemon token counting) |
| `--files-modified` | text |  |  | Comma-separated files modified this turn; warns if unclaimed |

### `minion agent set-status`

Set agent status.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--agent` | text | Yes |  |  |
| `--status` | text | Yes |  |  |

### `minion agent update-hp`

Daemon-only: record token usage and compute health score.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--agent` | text | Yes |  |  |
| `--input-tokens` | integer | Yes |  |  |
| `--output-tokens` | integer | Yes |  |  |
| `--limit` | integer | Yes |  |  |
| `--turn-input` | integer |  |  | Per-turn input tokens (current context pressure) |
| `--turn-output` | integer |  |  | Per-turn output tokens (current context pressure) |

### `minion agent who`

List all registered agents.

*No options.*

## 2. backlog

Capture and triage ideas, bugs, requests, smells, and tech debt.

### `minion backlog add`

Add a new item to the backlog.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--type` | choice | Yes |  |  |
| `--title` | text | Yes |  | Short descriptive title |
| `--source` | text |  | `human` | Who captured this (default: human) |
| `--description` | text |  |  | Longer description of the item |
| `--priority` | choice |  | `unset` |  |

### `minion backlog defer`

Defer a backlog item until a later date or milestone.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `path` | text | Yes |  |  |
| `--until` | text | Yes |  | Date or milestone to defer until |

### `minion backlog kill`

Mark a backlog item as killed.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `path` | text | Yes |  |  |
| `--reason` | text | Yes |  | Why this item is being killed |

### `minion backlog list`

List backlog items with optional filters.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--type` | choice |  |  |  |
| `--priority` | choice |  |  |  |
| `--status` | choice |  | `open` |  |

### `minion backlog promote`

Promote a backlog item into the requirement pipeline.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `path` | text | Yes |  |  |
| `--origin` | choice |  |  | Requirement origin override |

### `minion backlog reindex`

Rebuild the backlog DB index by scanning the filesystem.

*No options.*

### `minion backlog show`

Show a single backlog item by file path.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `path` | text | Yes |  |  |

### `minion backlog update`

Update priority and/or status of a backlog item.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `path` | text | Yes |  |  |
| `--priority` | choice |  |  |  |
| `--status` | choice |  |  |  |

## 3. comms

Send and receive messages between agents.

### `minion comms check-inbox`

Check and clear unread messages.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--agent` | text | Yes |  |  |

### `minion comms list-history`

Return the last N messages across all agents.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--count` | integer |  | `20` |  |

### `minion comms purge-inbox`

Delete old messages from inbox.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--agent` | text | Yes |  |  |
| `--older-than-hours` | integer |  | `2` |  |

### `minion comms send`

Send a message to an agent (or 'all' for broadcast).

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--from` | text | Yes |  |  |
| `--to` | text | Yes |  |  |
| `--message` | text | Yes |  |  |
| `--cc` | text |  |  |  |

## 4. crew

Spawn agent crews from YAML, add/remove agents, check party health.

### `minion crew halt`

Pause all agents — they finish current work, save state, then stop.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--agent` | text | Yes |  | Lead agent issuing the halt |

### `minion crew hand-off-zone`

Transfer file zone ownership from one agent to another.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--from` | text | Yes |  |  |
| `--to` | text | Yes |  | Comma-separated agent names |
| `--zone` | text | Yes |  |  |

### `minion crew list`

List available crews. Lead only.

*No options.*

### `minion crew recruit`

Add an ad-hoc agent into a running crew. Lead only.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--name` | text | Yes |  | Agent name |
| `--class` | choice |  |  |  |
| `--crew` | text | Yes |  | Running crew to join (tmux session crew-<name>) |
| `--from-crew` | text |  |  | Source crew YAML to pull character config from |
| `--capabilities` | text |  |  | Comma-separated capabilities (code,review,...) |
| `--system` | text |  |  | System prompt override |
| `--provider` | choice |  |  |  |
| `--model` | text |  |  | Model override |
| `--transport` | choice |  |  |  |
| `--permission-mode` | text |  |  | Permission mode for the agent |
| `--zone` | text |  |  | Zone assignment |
| `--runtime` | choice |  | `python` | Daemon runtime: python or ts. |

### `minion crew spawn`

Launch agents from a crew YAML into tmux panes.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--crew` | text | Yes |  |  |
| `--project-dir` | text |  | `.` |  |
| `--agents` | text |  |  |  |
| `--runtime` | choice |  | `python` | Daemon runtime: python (minion-swarm) or ts (SDK daemon). |

### `minion crew stand-down`

Shut down all agents in a crew. Lead only.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--agent` | text | Yes |  |  |
| `--crew` | text |  |  |  |

### `minion crew status`

Show crew health — agent status, token usage, active tasks. Lead only.

*No options.*

## 5. daemon

Start, stop, and tail logs for individual daemon agents.

### `minion daemon logs`

Show (and optionally follow) one agent's log.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `agent` | text | Yes |  |  |
| `--lines` | integer |  | `80` |  |
| `--follow` | boolean |  |  |  |

### `minion daemon start`

Start a single daemon agent from a crew.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `agent` | text | Yes |  |  |
| `--crew` | text | Yes |  | Crew YAML name (e.g. ff1) |
| `--project-dir` | text |  | `.` | Project directory |

### `minion daemon stop`

Stop a single daemon agent (SIGTERM → SIGKILL).

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `agent` | text | Yes |  |  |

## 6. file

Claim files before editing to prevent conflicts between agents.

### `minion file claim`

Claim a file for exclusive editing.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--agent` | text | Yes |  |  |
| `--file` | text | Yes |  |  |

### `minion file list`

List active file claims.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--agent` | text |  |  |  |

### `minion file release`

Release a file claim.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--agent` | text | Yes |  |  |
| `--file` | text | Yes |  |  |
| `--force` | boolean |  |  |  |

## 7. flow

Inspect task flow DAGs — see stages, transitions, and routing rules.

### `minion flow list`

List available task flow types.

*No options.*

### `minion flow next-status`

Query routing: what status comes next?

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `type_name` | text | Yes |  |  |
| `current` | text | Yes |  |  |
| `--failed` | boolean |  |  | Query fail path instead of happy path |

### `minion flow show`

Show a flow's stages and transitions.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `type_name` | text | Yes |  |  |

### `minion flow transition`

Manually transition a task to a new status.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `task_id` | integer | Yes |  |  |
| `to_status` | text | Yes |  |  |
| `--agent` | text | Yes |  | Agent triggering transition |

## 8. mission

Compose a crew from a mission description. AI suggests roles and skills.

### `minion mission list`

List available mission templates.

*No options.*

### `minion mission spawn`

Resolve mission slots, suggest party, and spawn.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `mission_type` | text | Yes |  |  |
| `--party` | text |  |  | Comma-separated character names to spawn |
| `--crew` | text |  |  | Comma-separated crew names to filter characters |
| `--project-dir` | text |  | `.` | Project directory |
| `--runtime` | choice |  | `python` | Daemon runtime: python or ts. |

### `minion mission suggest`

Show required capabilities, resolved slots, and eligible characters.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `mission_type` | text | Yes |  |  |
| `--crew` | text |  |  | Comma-separated crew names to filter characters |
| `--project-dir` | text |  | `.` | Project directory for crew scanning |

## 9. req

Track requirements through the decomposition pipeline — seed to completed.

### `minion req link`

Link a task to its source requirement.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--task` | integer | Yes |  | Task ID to link |
| `--path` | text | Yes |  | Requirement path relative to .work/requirements/ |

### `minion req list`

List all requirements with optional filters.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--stage` | choice |  |  |  |
| `--origin` | text |  |  | Filter by origin (feature, bug, ...) |

### `minion req orphans`

List leaf requirements with no linked tasks (work never started).

*No options.*

### `minion req register`

Register a requirement folder in the index.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--path` | text | Yes |  | Path relative to .work/requirements/ |
| `--by` | text |  | `human` | Who is registering (agent name or 'human') |

### `minion req reindex`

Rebuild the requirements index by scanning the filesystem.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--work-dir` | text |  |  | Path to .work/ directory (default: cwd/.work or -C project-dir/.work) |

### `minion req status`

Show a requirement, its linked tasks, and completion percentage.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `path` | text | Yes |  |  |

### `minion req tree`

Show the decomposition tree rooted at PATH.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `path` | text | Yes |  |  |

### `minion req unlinked`

List tasks with no requirement_path (orphan tasks).

*No options.*

### `minion req update`

Advance a requirement's stage.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--path` | text | Yes |  | Requirement path relative to .work/requirements/ |
| `--stage` | choice | Yes |  |  |

## 10. task

Create, assign, and update work items. Track progress through the DAG.

### `minion task assign`

Assign a task to an agent. Lead only.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--agent` | text | Yes |  |  |
| `--task-id` | integer | Yes |  |  |
| `--assigned-to` | text | Yes |  |  |

### `minion task check-work`

Check if agent has available tasks. Exit 0 = work, 1 = no work.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--agent` | text | Yes |  |  |

### `minion task close`

Close a task. Lead only.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--agent` | text | Yes |  |  |
| `--task-id` | integer | Yes |  |  |

### `minion task complete-phase`

Complete your phase — DAG routes to next stage.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--agent` | text | Yes |  |  |
| `--task-id` | integer | Yes |  |  |
| `--failed` | boolean |  |  | Mark as failed (routes to fail branch in DAG) |
| `--reason` | text |  |  | Required when blocking — why you're stuck |

### `minion task create`

Create a new task. Lead only.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--agent` | text | Yes |  |  |
| `--title` | text | Yes |  |  |
| `--task-file` | text | Yes |  |  |
| `--project` | text |  |  |  |
| `--zone` | text |  |  |  |
| `--blocked-by` | text |  |  |  |
| `--class-required` | text |  |  | Agent class required (e.g. coder, builder, recon) |
| `--type` | choice |  | `bugfix` |  |

### `minion task get`

Get full detail for a single task.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--task-id` | integer | Yes |  |  |

### `minion task lineage`

Show task lineage — DAG history and who worked each stage.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--task-id` | integer | Yes |  |  |

### `minion task list`

List tasks.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--status` | text |  |  |  |
| `--project` | text |  |  |  |
| `--zone` | text |  |  |  |
| `--assigned-to` | text |  |  |  |
| `--class-required` | text |  |  | Filter by required agent class |
| `--count` | integer |  | `50` |  |

### `minion task pull`

Claim a specific task by ID.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--agent` | text | Yes |  |  |
| `--task-id` | integer | Yes |  |  |

### `minion task reopen`

Reopen a terminal task back to an earlier phase. Lead only.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--agent` | text | Yes |  |  |
| `--task-id` | integer | Yes |  |  |
| `--to-status` | text |  | `assigned` | Target status (default: assigned) |

### `minion task submit-result`

Submit a result file for a task.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--agent` | text | Yes |  |  |
| `--task-id` | integer | Yes |  |  |
| `--result-file` | text | Yes |  |  |

### `minion task update`

Update a task's status, progress, or files.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--agent` | text | Yes |  |  |
| `--task-id` | integer | Yes |  |  |
| `--status` | text |  |  |  |
| `--progress` | text |  |  |  |
| `--files` | text |  |  |  |

## 11. trigger

Manage trigger words that flag messages for special handling.

### `minion trigger clear-moon-crash`

Clear the emergency stop flag. Lead only.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--agent` | text | Yes |  |  |

### `minion trigger list`

Return the trigger word codebook.

*No options.*

## 12. war

Session strategy — set objectives and log progress entries.

### `minion war get-plan`

Get the session objective by status.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--status` | choice |  | `active` |  |

### `minion war list-log`

Read the progress log.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--priority` | choice |  |  |  |
| `--count` | integer |  | `20` |  |
| `--agent` | text |  |  |  |

### `minion war log`

Log a progress entry — what was done, decisions made, blockers hit.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--agent` | text | Yes |  |  |
| `--entry` | text | Yes |  |  |
| `--priority` | choice |  | `normal` |  |

### `minion war set-plan`

Set the session's current objective. Lead only.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--agent` | text | Yes |  |  |
| `--plan` | text | Yes |  |  |

### `minion war update-status`

Update an objective's status. Lead only.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--agent` | text | Yes |  |  |
| `--plan-id` | integer | Yes |  |  |
| `--status` | choice | Yes |  |  |

## 13. Top-Level Commands

### `minion assign-task`

Assign a task to an agent. Lead only.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--agent` | text | Yes |  |  |
| `--task-id` | integer | Yes |  |  |
| `--assigned-to` | text | Yes |  |  |

### `minion check-activity`

Check an agent's activity level.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--agent` | text | Yes |  |  |

### `minion check-freshness`

Check file freshness relative to agent's last set-context. Lead only.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--agent` | text | Yes |  |  |
| `--files` | text | Yes |  |  |

### `minion check-inbox`

Check and clear unread messages.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--agent` | text | Yes |  |  |

### `minion check-work`

Check if agent has available tasks. Exit 0 = work, 1 = no work.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--agent` | text | Yes |  |  |

### `minion claim-file`

Claim a file for exclusive editing.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--agent` | text | Yes |  |  |
| `--file` | text | Yes |  |  |

### `minion clear-moon-crash`

Clear the emergency stop flag. Lead only.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--agent` | text | Yes |  |  |

### `minion close-task`

Close a task. Lead only.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--agent` | text | Yes |  |  |
| `--task-id` | integer | Yes |  |  |

### `minion cold-start`

Bootstrap an agent into (or back into) a session.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--agent` | text | Yes |  |  |

### `minion complete-phase`

Complete your phase — DAG routes to next stage.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--agent` | text | Yes |  |  |
| `--task-id` | integer | Yes |  |  |
| `--failed` | boolean |  |  | Mark as failed (routes to fail branch in DAG) |
| `--reason` | text |  |  | Required when blocking — why you're stuck |

### `minion create-task`

Create a new task. Lead only.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--agent` | text | Yes |  |  |
| `--title` | text | Yes |  |  |
| `--task-file` | text | Yes |  |  |
| `--project` | text |  |  |  |
| `--zone` | text |  |  |  |
| `--blocked-by` | text |  |  |  |
| `--class-required` | text |  |  | Agent class required (e.g. coder, builder, recon) |
| `--type` | choice |  | `bugfix` |  |

### `minion daemon-run`

Run a single agent daemon (internal — called by spawn-party).

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--config` | text | Yes |  | Path to crew YAML config |
| `--agent` | text | Yes |  | Agent name to run |

### `minion dashboard`

Live task board. Run in a tmux pane — no DB registration.

*No options.*

### `minion debrief`

File a session debrief. Lead only.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--agent` | text | Yes |  |  |
| `--debrief-file` | text | Yes |  |  |

### `minion deregister`

Remove an agent from the registry.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--name` | text | Yes |  |  |

### `minion docs`

Generate CLI reference from Click introspection.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--format` | choice |  | `markdown` | Output format |
| `--output`, `-o` | path |  |  | Write cli-reference.md to this directory |

### `minion end-session`

End the current session. Lead only.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--agent` | text | Yes |  |  |

### `minion fenix-down`

Save session state to disk before context window runs out.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--agent` | text | Yes |  |  |
| `--files` | text | Yes |  |  |
| `--manifest` | text |  |  |  |

### `minion get-battle-plan`

Get the session objective by status.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--status` | choice |  | `active` |  |

### `minion get-claims`

List active file claims.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--agent` | text |  |  |  |

### `minion get-history`

Return the last N messages across all agents.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--count` | integer |  | `20` |  |

### `minion get-raid-log`

Read the progress log.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--priority` | choice |  |  |  |
| `--count` | integer |  | `20` |  |
| `--agent` | text |  |  |  |

### `minion get-task`

Get full detail for a single task.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--task-id` | integer | Yes |  |  |

### `minion get-tasks`

List tasks.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--status` | text |  |  |  |
| `--project` | text |  |  |  |
| `--zone` | text |  |  |  |
| `--assigned-to` | text |  |  |  |
| `--class-required` | text |  |  | Filter by required agent class |
| `--count` | integer |  | `50` |  |

### `minion get-triggers`

Return the trigger word codebook.

*No options.*

### `minion halt`

Pause all agents — they finish current work, save state, then stop.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--agent` | text | Yes |  | Lead agent issuing the halt |

### `minion hand-off-zone`

Transfer file zone ownership from one agent to another.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--from` | text | Yes |  |  |
| `--to` | text | Yes |  | Comma-separated agent names |
| `--zone` | text | Yes |  |  |

### `minion install-docs`

Copy protocol + contract docs to ~/.minion_work/docs/.

*No options.*

### `minion interrupt`

Interrupt an agent's current invocation. Lead only.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--agent` | text | Yes |  | Agent to interrupt |
| `--requesting-agent` | text | Yes |  | Lead requesting interrupt |

### `minion list-claims`

List active file claims.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--agent` | text |  |  |  |

### `minion list-crews`

List available crews. Lead only.

*No options.*

### `minion list-flows`

List available task flow types.

*No options.*

### `minion list-history`

Return the last N messages across all agents.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--count` | integer |  | `20` |  |

### `minion list-raid-log`

Read the progress log.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--priority` | choice |  |  |  |
| `--count` | integer |  | `20` |  |
| `--agent` | text |  |  |  |

### `minion list-tasks`

List tasks.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--status` | text |  |  |  |
| `--project` | text |  |  |  |
| `--zone` | text |  |  |  |
| `--assigned-to` | text |  |  |  |
| `--class-required` | text |  |  | Filter by required agent class |
| `--count` | integer |  | `50` |  |

### `minion list-triggers`

Return the trigger word codebook.

*No options.*

### `minion log-raid`

Log a progress entry — what was done, decisions made, blockers hit.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--agent` | text | Yes |  |  |
| `--entry` | text | Yes |  |  |
| `--priority` | choice |  | `normal` |  |

### `minion logs`

Show (and optionally follow) one agent's log.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `agent` | text | Yes |  |  |
| `--lines` | integer |  | `80` |  |
| `--follow` | boolean |  |  |  |

### `minion next-status`

Query routing: what status comes next?

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `type_name` | text | Yes |  |  |
| `current` | text | Yes |  |  |
| `--failed` | boolean |  |  | Query fail path instead of happy path |

### `minion party-status`

Show crew health — agent status, token usage, active tasks. Lead only.

*No options.*

### `minion poll`

Poll for messages and tasks. Returns content when available.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--agent` | text | Yes |  |  |
| `--interval` | integer |  | `5` | Poll interval in seconds |
| `--timeout` | integer |  |  | Timeout in seconds (0 = forever) |

### `minion pull-task`

Claim a specific task by ID.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--agent` | text | Yes |  |  |
| `--task-id` | integer | Yes |  |  |

### `minion purge-inbox`

Delete old messages from inbox.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--agent` | text | Yes |  |  |
| `--older-than-hours` | integer |  | `2` |  |

### `minion recruit`

Add an ad-hoc agent into a running crew. Lead only.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--name` | text | Yes |  | Agent name |
| `--class` | choice |  |  |  |
| `--crew` | text | Yes |  | Running crew to join (tmux session crew-<name>) |
| `--from-crew` | text |  |  | Source crew YAML to pull character config from |
| `--capabilities` | text |  |  | Comma-separated capabilities (code,review,...) |
| `--system` | text |  |  | System prompt override |
| `--provider` | choice |  |  |  |
| `--model` | text |  |  | Model override |
| `--transport` | choice |  |  |  |
| `--permission-mode` | text |  |  | Permission mode for the agent |
| `--zone` | text |  |  | Zone assignment |
| `--runtime` | choice |  | `python` | Daemon runtime: python or ts. |

### `minion register`

Register an agent.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--name` | text | Yes |  |  |
| `--class` | choice | Yes |  |  |
| `--model` | text |  |  |  |
| `--description` | text |  |  |  |
| `--transport` | choice |  | `terminal` |  |

### `minion release-file`

Release a file claim.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--agent` | text | Yes |  |  |
| `--file` | text | Yes |  |  |
| `--force` | boolean |  |  |  |

### `minion rename`

Rename an agent. Lead only.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--old` | text | Yes |  |  |
| `--new` | text | Yes |  |  |

### `minion reopen-task`

Reopen a terminal task back to an earlier phase. Lead only.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--agent` | text | Yes |  |  |
| `--task-id` | integer | Yes |  |  |
| `--to-status` | text |  | `assigned` | Target status (default: assigned) |

### `minion resume`

Send a resume message to an interrupted agent. Lead only.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--agent` | text | Yes |  | Agent to resume |
| `--message` | text | Yes |  | Message to send on resume |
| `--from` | text | Yes |  | Sending agent (lead) |

### `minion retire-agent`

Signal a single daemon agent to exit gracefully. Lead only.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--agent` | text | Yes |  | Agent to retire |
| `--requesting-agent` | text | Yes |  | Lead requesting retirement |

### `minion send`

Send a message to an agent (or 'all' for broadcast).

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--from` | text | Yes |  |  |
| `--to` | text | Yes |  |  |
| `--message` | text | Yes |  |  |
| `--cc` | text |  |  |  |

### `minion set-battle-plan`

Set the session's current objective. Lead only.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--agent` | text | Yes |  |  |
| `--plan` | text | Yes |  |  |

### `minion set-context`

Update context summary and health (tokens used, token limit).

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--agent` | text | Yes |  |  |
| `--context` | text | Yes |  |  |
| `--tokens-used` | integer |  |  |  |
| `--tokens-limit` | integer |  |  |  |
| `--hp` | integer |  |  | Self-reported HP 0-100 (skips daemon token counting) |
| `--files-modified` | text |  |  | Comma-separated files modified this turn; warns if unclaimed |

### `minion set-status`

Set agent status.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--agent` | text | Yes |  |  |
| `--status` | text | Yes |  |  |

### `minion show-flow`

Show a flow's stages and transitions.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `type_name` | text | Yes |  |  |

### `minion sitrep`

Fused COP: agents + tasks + zones + claims + flags + recent comms.

*No options.*

### `minion spawn-party`

Launch agents from a crew YAML into tmux panes.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--crew` | text | Yes |  |  |
| `--project-dir` | text |  | `.` |  |
| `--agents` | text |  |  |  |
| `--runtime` | choice |  | `python` | Daemon runtime: python (minion-swarm) or ts (SDK daemon). |

### `minion stand-down`

Shut down all agents in a crew. Lead only.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--agent` | text | Yes |  |  |
| `--crew` | text |  |  |  |

### `minion start`

Start a single daemon agent from a crew.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `agent` | text | Yes |  |  |
| `--crew` | text | Yes |  | Crew YAML name (e.g. ff1) |
| `--project-dir` | text |  | `.` | Project directory |

### `minion stop`

Stop a single daemon agent (SIGTERM → SIGKILL).

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `agent` | text | Yes |  |  |

### `minion submit-result`

Submit a result file for a task.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--agent` | text | Yes |  |  |
| `--task-id` | integer | Yes |  |  |
| `--result-file` | text | Yes |  |  |

### `minion task-lineage`

Show task lineage — DAG history and who worked each stage.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--task-id` | integer | Yes |  |  |

### `minion tools`

List available tools for your class.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--class` | text |  |  | Class to list tools for (default: MINION_CLASS env) |

### `minion transition`

Manually transition a task to a new status.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `task_id` | integer | Yes |  |  |
| `to_status` | text | Yes |  |  |
| `--agent` | text | Yes |  | Agent triggering transition |

### `minion update-battle-plan-status`

Update an objective's status. Lead only.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--agent` | text | Yes |  |  |
| `--plan-id` | integer | Yes |  |  |
| `--status` | choice | Yes |  |  |

### `minion update-hp`

Daemon-only: record token usage and compute health score.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--agent` | text | Yes |  |  |
| `--input-tokens` | integer | Yes |  |  |
| `--output-tokens` | integer | Yes |  |  |
| `--limit` | integer | Yes |  |  |
| `--turn-input` | integer |  |  | Per-turn input tokens (current context pressure) |
| `--turn-output` | integer |  |  | Per-turn output tokens (current context pressure) |

### `minion update-task`

Update a task's status, progress, or files.

| Option | Type | Required | Default | Description |
|--------|------|----------|---------|-------------|
| `--agent` | text | Yes |  |  |
| `--task-id` | integer | Yes |  |  |
| `--status` | text |  |  |  |
| `--progress` | text |  |  |  |
| `--files` | text |  |  |  |

### `minion who`

List all registered agents.

*No options.*

