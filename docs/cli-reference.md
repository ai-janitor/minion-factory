# Minion CLI Reference

`minion, version 0.1.0`

---

## 1. Agent Registry

### `register`

Register an agent.

```
Usage: minion register [OPTIONS]

Options:
  --name TEXT         [required]
  --class TEXT        [required]
  --model TEXT
  --description TEXT
  --transport TEXT
```

### `deregister`

Remove an agent from the registry.

```
Usage: minion deregister [OPTIONS]

Options:
  --name TEXT  [required]
```

### `rename`

Rename an agent. Lead only.

```
Usage: minion rename [OPTIONS]

Options:
  --old TEXT  [required]
  --new TEXT  [required]
```

### `who`

List all registered agents.

```
Usage: minion who [OPTIONS]

Options:
  (none)
```

### `tools`

List available tools for your class.

```
Usage: minion tools [OPTIONS]

Options:
  --class TEXT  Class to list tools for (default: MINION_CLASS env)
```

---

## 2. Comms

### `send`

Send a message to an agent (or `all` for broadcast).

```
Usage: minion send [OPTIONS]

Options:
  --from TEXT     [required]
  --to TEXT       [required]
  --message TEXT  [required]
  --cc TEXT
```

### `check-inbox`

Check and clear unread messages.

```
Usage: minion check-inbox [OPTIONS]

Options:
  --agent TEXT  [required]
```

### `get-history`

Return the last N messages across all agents.

```
Usage: minion get-history [OPTIONS]

Options:
  --count INTEGER
```

### `purge-inbox`

Delete old messages from inbox.

```
Usage: minion purge-inbox [OPTIONS]

Options:
  --agent TEXT                [required]
  --older-than-hours INTEGER
```

### `set-context`

Update context summary and HP metrics.

```
Usage: minion set-context [OPTIONS]

Options:
  --agent TEXT            [required]
  --context TEXT          [required]
  --tokens-used INTEGER
  --tokens-limit INTEGER
  --hp INTEGER            Self-reported HP 0-100 (skips daemon token counting)
  --files-modified TEXT   Comma-separated files modified this turn; warns if unclaimed
```

### `set-status`

Set agent status.

```
Usage: minion set-status [OPTIONS]

Options:
  --agent TEXT   [required]
  --status TEXT  [required]
```

---

## 3. Tasks

### `create-task`

Create a new task. Lead only.

```
Usage: minion create-task [OPTIONS]

Options:
  --agent TEXT           [required]
  --title TEXT           [required]
  --task-file TEXT       [required]
  --project TEXT
  --zone TEXT
  --blocked-by TEXT
  --class-required TEXT  Agent class required (e.g. coder, builder, recon)
  --type TEXT            Task flow type (default: bugfix)
```

### `assign-task`

Assign a task to an agent. Lead only.

```
Usage: minion assign-task [OPTIONS]

Options:
  --agent TEXT        [required]
  --task-id INTEGER   [required]
  --assigned-to TEXT  [required]
```

### `pull-task`

Claim a specific task by ID.

```
Usage: minion pull-task [OPTIONS]

Options:
  --agent TEXT       [required]
  --task-id INTEGER  [required]
```

### `update-task`

Update a task's status, progress, or files.

```
Usage: minion update-task [OPTIONS]

Options:
  --agent TEXT       [required]
  --task-id INTEGER  [required]
  --status TEXT
  --progress TEXT
  --files TEXT
```

### `complete-task`

DAG-routed task completion.

```
Usage: minion complete-task [OPTIONS]

Options:
  --agent TEXT       [required]
  --task-id INTEGER  [required]
  --failed           Mark as failed (routes to fail branch in DAG)
```

### `submit-result`

Submit a result file for a task.

```
Usage: minion submit-result [OPTIONS]

Options:
  --agent TEXT        [required]
  --task-id INTEGER   [required]
  --result-file TEXT  [required]
```

### `close-task`

Close a task. Lead only.

```
Usage: minion close-task [OPTIONS]

Options:
  --agent TEXT       [required]
  --task-id INTEGER  [required]
```

### `get-tasks`

List tasks.

```
Usage: minion get-tasks [OPTIONS]

Options:
  --status TEXT
  --project TEXT
  --zone TEXT
  --assigned-to TEXT
  --class-required TEXT  Filter by required agent class
  --count INTEGER
```

### `get-task`

Get full detail for a single task.

```
Usage: minion get-task [OPTIONS]

Options:
  --task-id INTEGER  [required]
```

### `task-lineage`

Show task lineage — DAG history and who worked each stage.

```
Usage: minion task-lineage [OPTIONS]

Options:
  --task-id INTEGER  [required]
```

---

## 4. Task Flows

### `list-flows`

List available task flow types.

```
Usage: minion list-flows [OPTIONS]

Options:
  (none)
```

### `show-flow`

Show a flow's stages and transitions.

```
Usage: minion show-flow [OPTIONS] TYPE_NAME

Arguments:
  TYPE_NAME  [required]
```

### `next-status`

Query routing: what status comes next?

```
Usage: minion next-status [OPTIONS] TYPE_NAME CURRENT

Arguments:
  TYPE_NAME  [required]
  CURRENT    [required]

Options:
  --failed  Query fail path instead of happy path
```

### `transition`

Manually transition a task to a new status.

```
Usage: minion transition [OPTIONS] TASK_ID TO_STATUS

Arguments:
  TASK_ID    [required]
  TO_STATUS  [required]

Options:
  --agent TEXT  Agent triggering transition  [required]
```

---

## 5. File Safety

### `claim-file`

Claim a file for exclusive editing.

```
Usage: minion claim-file [OPTIONS]

Options:
  --agent TEXT  [required]
  --file TEXT   [required]
```

### `release-file`

Release a file claim.

```
Usage: minion release-file [OPTIONS]

Options:
  --agent TEXT  [required]
  --file TEXT   [required]
  --force
```

### `get-claims`

List active file claims.

```
Usage: minion get-claims [OPTIONS]

Options:
  --agent TEXT
```

---

## 6. War Room

### `set-battle-plan`

Set the active battle plan. Lead only.

```
Usage: minion set-battle-plan [OPTIONS]

Options:
  --agent TEXT  [required]
  --plan TEXT   [required]
```

### `get-battle-plan`

Get battle plan by status.

```
Usage: minion get-battle-plan [OPTIONS]

Options:
  --status TEXT
```

### `update-battle-plan-status`

Update a battle plan's status. Lead only.

```
Usage: minion update-battle-plan-status [OPTIONS]

Options:
  --agent TEXT       [required]
  --plan-id INTEGER  [required]
  --status TEXT      [required]
```

### `log-raid`

Append an entry to the raid log.

```
Usage: minion log-raid [OPTIONS]

Options:
  --agent TEXT     [required]
  --entry TEXT     [required]
  --priority TEXT
```

### `get-raid-log`

Read the raid log.

```
Usage: minion get-raid-log [OPTIONS]

Options:
  --priority TEXT
  --count INTEGER
  --agent TEXT
```

---

## 7. Monitoring

### `party-status`

Full raid health dashboard. Lead only.

```
Usage: minion party-status [OPTIONS]

Options:
  (none)
```

### `sitrep`

Fused COP: agents + tasks + zones + claims + flags + recent comms.

```
Usage: minion sitrep [OPTIONS]

Options:
  (none)
```

### `check-activity`

Check an agent's activity level.

```
Usage: minion check-activity [OPTIONS]

Options:
  --agent TEXT  [required]
```

### `check-freshness`

Check file freshness relative to agent's last set-context. Lead only.

```
Usage: minion check-freshness [OPTIONS]

Options:
  --agent TEXT  [required]
  --files TEXT  [required]
```

### `update-hp`

Daemon-only: write observed HP to SQLite.

```
Usage: minion update-hp [OPTIONS]

Options:
  --agent TEXT             [required]
  --input-tokens INTEGER   [required]
  --output-tokens INTEGER  [required]
  --limit INTEGER          [required]
  --turn-input INTEGER     Per-turn input tokens (current context pressure)
  --turn-output INTEGER    Per-turn output tokens (current context pressure)
```

---

## 8. Lifecycle

### `cold-start`

Bootstrap an agent into (or back into) a session.

```
Usage: minion cold-start [OPTIONS]

Options:
  --agent TEXT  [required]
```

### `fenix-down`

Dump session knowledge to disk before context death.

```
Usage: minion fenix-down [OPTIONS]

Options:
  --agent TEXT     [required]
  --files TEXT     [required]
  --manifest TEXT
```

### `debrief`

File a session debrief. Lead only.

```
Usage: minion debrief [OPTIONS]

Options:
  --agent TEXT         [required]
  --debrief-file TEXT  [required]
```

### `end-session`

End the current session. Lead only.

```
Usage: minion end-session [OPTIONS]

Options:
  --agent TEXT  [required]
```

---

## 9. Triggers

### `get-triggers`

Return the trigger word codebook.

```
Usage: minion get-triggers [OPTIONS]

Options:
  (none)
```

### `clear-moon-crash`

Clear the moon_crash emergency flag. Lead only.

```
Usage: minion clear-moon-crash [OPTIONS]

Options:
  --agent TEXT  [required]
```

---

## 10. Crew Management

### `spawn-party`

Spawn daemon workers in tmux panes. Auto-registers lead from crew YAML.

```
Usage: minion spawn-party [OPTIONS]

Options:
  --crew TEXT            [required]
  --project-dir TEXT
  --agents TEXT
  --runtime [python|ts]  Daemon runtime: python (minion-swarm) or ts (SDK daemon).
```

### `stand-down`

Dismiss the party. Lead only.

```
Usage: minion stand-down [OPTIONS]

Options:
  --agent TEXT  [required]
  --crew TEXT
```

### `retire-agent`

Signal a single daemon agent to exit gracefully. Lead only.

```
Usage: minion retire-agent [OPTIONS]

Options:
  --agent TEXT             Agent to retire  [required]
  --requesting-agent TEXT  Lead requesting retirement  [required]
```

### `hand-off-zone`

Direct zone handoff — retiring agent bestows zone to replacements.

```
Usage: minion hand-off-zone [OPTIONS]

Options:
  --from TEXT  [required]
  --to TEXT    Comma-separated agent names  [required]
  --zone TEXT  [required]
```

### `list-crews`

List available crews. Lead only.

```
Usage: minion list-crews [OPTIONS]

Options:
  (none)
```

### `install-docs`

Copy protocol + contract docs to `~/.minion_work/docs/`.

```
Usage: minion install-docs [OPTIONS]

Options:
  (none)
```

---

## 11. Daemon

### `start`

Start a single daemon agent from a crew.

```
Usage: minion start [OPTIONS] AGENT

Arguments:
  AGENT  [required]

Options:
  --crew TEXT         Crew YAML name (e.g. ff1)  [required]
  --project-dir TEXT  Project directory
```

### `stop`

Stop a single daemon agent (SIGTERM -> SIGKILL).

```
Usage: minion stop [OPTIONS] AGENT

Arguments:
  AGENT  [required]
```

### `logs`

Show (and optionally follow) one agent's log.

```
Usage: minion logs [OPTIONS] AGENT

Arguments:
  AGENT  [required]

Options:
  --lines INTEGER
  --follow / --no-follow
```

### `poll`

Poll for messages and tasks. Returns content when available.

```
Usage: minion poll [OPTIONS]

Options:
  --agent TEXT        [required]
  --interval INTEGER  Poll interval in seconds
  --timeout INTEGER   Timeout in seconds (0 = forever)
```
