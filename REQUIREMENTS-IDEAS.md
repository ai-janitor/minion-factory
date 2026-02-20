# minion-factory — Ideas & Optional Requirements

Ideas captured during live sessions. Not committed to — just logged for future consideration.

## Autonomous Mode (Unsupervised Crew)

**Context**: If commander and zone lead are both down, workers idle forever or improvise dangerously.

**Idea**: Crew YAML defines `autonomous_mode: true` with guardrails:
- `max_tasks_unsupervised: N` — workers may complete up to N tasks from pre-loaded queue without lead check-in, then stop
- `allowed_commands_autonomous: [pull-task, complete-task, send]` — restricted command set when unsupervised
- `blocked_commands_autonomous: [stand-down, retire-agent, spawn-party]` — destructive ops forbidden
- After N tasks or M minutes with no lead heartbeat, workers enter "park" mode — stop pulling, log status to raid log, wait

## Idle Chatter as Heartbeat

**Context**: Workers sending "standing by" messages to dead lead inbox is wasteful but also serves as a passive liveness signal.

**Idea**: Replace accidental heartbeat with intentional one:
- `minion heartbeat --agent fighter` — single CLI call, no LLM invocation, daemon can do it directly
- Heartbeat writes `last_seen` + `status: alive` without waking the model
- Saves full API invocation cost while preserving liveness signal

## Buddy System for Workers

**Context**: Workers can't detect if a peer has stalled. Only lead monitors everyone.

**Idea**: Each worker has a designated buddy in crew YAML:
```yaml
agents:
  fighter:
    buddy: blackmage
  blackmage:
    buddy: fighter
```
- If buddy's `last_seen` exceeds threshold, send alert to lead (or commander if lead is down)
- Distributed failure detection without centralized lead

## Task Queue Ceiling

**Context**: Pre-loaded pull-based queue enables autonomous work, but uncapped autonomy is risky.

**Idea**: Queue has a "ceiling" — max tasks a worker can pull without lead verification:
- After ceiling hit, worker parks and sends "ceiling reached, N tasks complete, awaiting verification"
- Lead reviews batch, approves, resets ceiling
- Balances autonomy with oversight

## Spawn-Per-Task (Ephemeral Agents)

**Context**: Current model is persistent agents polling forever. Alternative: spawn agent, execute task, dismiss.

**Idea**:
- `minion run-task --task-id 5 --agent fighter --provider claude-sonnet` — one-shot execution
- Agent bootstraps from cache (deterministic), reads task spec, executes, reports result, exits
- No poll loop, no idle burn, no compaction risk (short-lived)
- Trade-off: no conversational context between tasks, cold start per task

## Provider Fallback Chain

**Context**: Gemini hits rate limits, Codex can't reach DB. No automatic fallback.

**Idea**: Crew YAML defines fallback providers per agent:
```yaml
agents:
  thief:
    provider: gemini-3-flash
    fallback: [claude-haiku, claude-sonnet]
```
- If primary provider fails N times, daemon switches to fallback
- Log the switch, alert lead
- Reset to primary after cooldown period

## Model-Role Mismatch — Lead Doesn't Need Opus

**Context**: Observed redwizard (Opus, $15/MTok) spending turns journaling about its accomplishments instead of forwarding Phase 6 orders. Meanwhile fighter (Sonnet, $3/MTok) sat idle on v23 waiting for dispatch.

**Data**:
- Redwizard: 4 compactions in ~40 minutes. Zero files written. 100% coordination overhead
- Fighter: 23 invocations. 60% of all code output. Waited 3-8 min between tasks for lead dispatch
- Redwizard's actual work: read task spec, write message, send message. No reasoning required

**Idea**: Match model to role complexity:
- **Lead/coordinator**: Haiku or Sonnet. Fast, cheap, no self-reflection. Job is: route messages, write task specs, verify completion
- **Workers/coders**: Sonnet or Opus depending on task complexity. Reasoning for code, not for dispatch
- **Recon/verification**: Flash-tier (Gemini Flash, Haiku). Read files, compare, report

**Trade-off**: Cheaper lead might miss nuance in task specs or fail to catch worker errors. But the current Opus lead missed dispatching Phase 6 entirely because it was journaling — so "smarter" ≠ "more effective coordinator."

## Planner Class — One-Shot Task DAG Creation

**Context**: Redwizard (Opus lead) does 4 jobs: planning, dispatching, verifying, journaling. All on a 200k window that compacts every 10 minutes. Each compaction loses the plan. The planning work (reading requirements, breaking into tasks, setting dependencies) only needs to happen ONCE at session start.

**Idea**: New class `planner` — runs once, creates the full task DAG, exits:
1. Reads REQUIREMENTS.md + source repos
2. Creates tasks with dependencies, class restrictions, acceptance criteria
3. Front-loads the pull-task queue
4. Writes battle plan to `.work/`
5. Exits. Never polls. Never dispatches. Never journals.

**Crew role split**:
- **Planner** (Opus, one-shot): deep reasoning to decompose requirements into tasks. Expensive but runs once
- **Dispatcher** (Haiku, persistent): lightweight message router. Pulls from pre-loaded queue, assigns to workers. No reasoning needed — just queue management
- **Workers** (Sonnet, persistent): pull tasks, write code, report completion
- **Verifier** (Haiku/Flash, on-demand): spawned per completed task. Checks work, closes task, exits

**Why this fixes the bottleneck**: The current lead (Opus) is both the thinker and the router. Planning needs intelligence. Routing doesn't. Separate them and put the right model on each job.

**Trade-off**: More agents = more coordination overhead? No — the planner exits after setup. The dispatcher is cheap. Net cost goes down because Opus runs once instead of 18 invocations of journaling.

## Revised Role Architecture — Six Workflow Roles

**Context**: Current system has 5 classes (lead, coder, builder, recon, oracle) mapped to RPG archetypes. Live session revealed these don't map to actual work patterns. AI agents are general-purpose — they don't need domain specialization, they need workflow-pattern roles.

**Proposed roles**:

| Role | What It Does | Lifecycle | Model Tier | Auth Level |
|------|-------------|-----------|------------|------------|
| **lead** | Human interface, strategy, overrides, judgment calls | Persistent (terminal transport) | Opus/Sonnet | Full access |
| **planner** | Read requirements, decompose into task DAG, front-load queue | One-shot, exits after setup | Opus | Read all, write tasks + battle plan |
| **dispatcher** | Route messages, assign from queue, monitor heartbeats | Persistent, lightweight | Haiku/Sonnet | Read tasks + agents, write assignments |
| **worker** | Pull tasks, write code, report completion | Persistent or spawn-per-task | Sonnet | Read tasks, write code + files, send messages |
| **verifier** | Check completed work, run tests, close tasks | On-demand per completed task | Haiku/Flash | Read all, write task status |
| **oracle** | Answer questions, provide context, unblock workers | On-demand, spawned when asked | Sonnet/Opus | Read all, no write except messages |

**Key design principles**:
- AI agents are general-purpose — no domain specialization (no "frontend-coder" vs "backend-coder")
- Roles map to **permission levels and lifecycle patterns**, not skills
- Expensive models (Opus) run once or on-demand, not persistent
- Cheap models (Haiku) handle persistent polling/routing
- Workers pull from queue — don't wait for dispatcher push

**Migration from current classes**:
- `lead` → stays `lead` (human interface doesn't change)
- `lead` (zone lead like redwizard) → split into `planner` + `dispatcher`
- `coder` → `worker`
- `builder` → `worker` (same permissions, different system prompt)
- `recon` → `verifier` (primary) or `oracle` (if answering questions)
- `oracle` → `oracle` (but on-demand, not persistent)

## Same-Class Collaboration Protocol

**Context**: If we spawn fighter + fighter2, both workers need rules for collaborating. Currently no protocol for same-class agents working in parallel. File claims exist but aren't enforced by convention in protocol docs.

**Observed gap**: fighter edited db.py (a shared file) during Phase 2 without coordinating with blackmage who was also working on related modules. It worked by luck, not by protocol.

**Idea**: Add to protocol-worker.md (or per-class protocol):

### On Startup (same-class awareness)
```
1. minion who → find peers with same class
2. minion get-claims → see what files are taken
3. Send peer: "I'm [name], working on [task]. What are you on?"
4. Read common area / bulletin board for current assignments
```

### During Work
- `claim-file` before ANY edit. No exceptions.
- Check `get-claims` before reading a file you might edit — peer may be mid-write
- If you need a file that's claimed → send peer a message, wait for release. Don't force-claim
- Task is atomic — once pulled, yours until complete. No splitting across workers
- CC same-class peers on completion so they know what changed

### Shared File Protocol
- If two workers need the same file → first to claim wins
- Second worker sends request via lead (or directly to peer): "need to add X to db.py"
- Peer either: (a) adds it themselves, (b) releases claim, (c) suggests alternative approach
- NEVER have two workers editing the same file simultaneously

### Handoff Pattern
- Worker A finishes schema → sends to Worker B: "schema done in tasks/db.py, you can wire CLI now"
- Worker B claims tasks/db.py, reads it, builds on top
- Sequential handoff > parallel conflict

**This should be in every class protocol doc**, not just worker. Any class that writes files needs these rules.

## Zone-Based Oracle Splitting

**Context**: Two oracles can split knowledge domains so workers get faster answers without either oracle reading the entire codebase.

**Idea**: Oracles assigned knowledge zones via crew YAML:
```yaml
agents:
  oracle-db:
    class: oracle
    zone: "db, tasks, auth, schema, migrations"
  oracle-infra:
    class: oracle
    zone: "providers, daemon, config, spawn, tmux"
```

**Worker protocol**:
1. Worker has a question → checks `minion who` → finds oracles and their zones
2. Routes question to the oracle whose zone matches the topic
3. Oracle answers from its zone knowledge — doesn't need to read the whole codebase
4. If question spans zones, worker asks both — they each answer their piece

**Oracle startup**:
1. Read files in their zone on boot (pre-cache knowledge)
2. Announce zone coverage: "I cover db, tasks, auth. Ask me about schemas and migrations."
3. Stay on-demand — don't poll, get spawned when asked

**CORRECTION — zones are emergent, not declared.** Don't hardcode zones in YAML — the codebase changes, new modules get added. Oracle discovers its zone dynamically:

1. Oracle reads files on-demand as questions come in
2. Tracks what it's read: "I've covered db.py, tasks/, auth.py"
3. Announces coverage to peers: `minion set-context --agent oracle1 --context "read: db, tasks, auth"`
4. Second oracle sees oracle1's context → reads different files → covers different ground
5. Workers check `minion who` → see oracle contexts → route question to the oracle that already has the knowledge

**Knowledge captured on the battlefield** — zones emerge from what the oracle actually reads during the session, not from static config. The `context_summary` field already exists for this — oracles publish what they know, workers route accordingly.

**Extends to any same-class agents**: Two workers split by file zone. Two verifiers split by module zone. Same pattern — negotiate at runtime via context, not YAML.

## Command Surface Per Role — 53 Is Too Many

**Context**: Factory now has 53 CLI commands. Every agent sees all 53 in `minion tools` output during bootstrap. That's 53 lines of context consumed before the agent does any work. A worker needs ~10 commands, not 53.

**Observed**: `minion --compact register` outputs the full command list + trigger words + playbook instructions. For a worker, 80% of that is noise — commands they'll never use and shouldn't know about (stand-down, spawn-party, debrief, etc.).

**Idea**: `minion tools` output scoped tightly per role:
- Worker sees: pull-task, complete-task, send, check-inbox, claim-file, release-file, set-context, set-status, who, get-claims, get-task (~11 commands)
- Dispatcher sees: assign-task, get-tasks, send, check-inbox, who, party-status (~6 commands)
- Verifier sees: get-task, get-claims, check-inbox, send, complete-task, who (~6 commands)
- Oracle sees: check-inbox, send, who, get-task, set-context (~5 commands)
- Planner sees: create-task, set-battle-plan, get-tasks, list-flows, show-flow, who (~6 commands)
- Lead sees: everything (53 commands)

**Why it matters**: Fewer commands = fewer tokens in bootstrap = more context window for actual work. An Opus lead can afford 53 commands. A Haiku worker can't waste context on `spawn-party` and `debrief`.

**Implementation**: `auth.py` already has `get_tools_for_class()`. Just tighten the mapping per the new role architecture.

## Cost-Aware Task Assignment

**Context**: Different providers have wildly different costs. No cost tracking today.

**Idea**: Track `cost_usd` per agent per task. Lead can see:
- "fighter (Sonnet) costs $0.12/task, thief (Gemini) costs $0.003/task"
- Auto-assign cheap tasks to cheap providers, expensive tasks to capable ones
- Budget ceiling per session: "stop all work if session cost exceeds $X"
