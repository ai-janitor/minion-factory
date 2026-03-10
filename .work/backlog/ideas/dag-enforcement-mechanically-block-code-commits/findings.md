# Investigation Findings: DAG Enforcement — Mechanically Block Code Commits Without Completed Scaffolding Phase

**Investigator:** b17-investigator
**Date:** 2026-03-10
**Task:** #102 (backlog #17)

---

## 1. Current State of DAG System

### 1.1 Flow Definitions (task-flows/*.yaml)

12 flow YAMLs exist: `_base`, `bugfix`, `build`, `chore`, `feature`, `hotfix`, `implementation`, `investigation`, `requirement`, `requirement-lite`, `research`, plus `_agent-classes`.

Each flow defines a DAG of stages. Stages have:
- `next` / `fail` / `alt_next` — transition edges
- `workers` — which agent classes can work each stage
- `requires` — preconditions (file existence, DB conditions, task field checks)
- `gate` — named gates checked by `past_gate()` method

### 1.2 The Implementation Flow Already Has a Scaffolding Gate

`task-flows/implementation.yaml` defines this pipeline:

```
open → assigned → spec → plan → implement → qe → verify → closed
```

The `plan` stage has `gate: scaffolding` and `requires: [plan.md]`. This means:
- The agent must write `plan.md` before transitioning out of `plan`
- The gate named `scaffolding` is attached to this stage
- `TaskFlow.past_gate("scaffolding")` returns True only if the task's current status is at or after the `plan` stage

### 1.3 How Tasks Track Their Stage

Tasks table in SQLite (`minion.db`):
- `status` column holds the current DAG stage name (e.g., "open", "assigned", "spec", "plan", "implement")
- `flow_type` column holds which flow YAML to load (e.g., "implementation", "bugfix")
- `assigned_to` column holds the agent name

The `past_gate()` method on `TaskFlow` walks the DAG from the gated stage forward and returns True if the current status is reachable from the gated stage.

### 1.4 Existing Git Hook Infrastructure

**Already implemented:**

1. **`scripts/scaffolding-gate.sh`** — a pre-commit hook that:
   - Only activates when `MINION_AGENT_NAME` env var is set
   - Has `MINION_HOOKS_BYPASS=1` kill switch
   - Checks staged files for code extensions (.py, .ts, .go, etc.)
   - Queries SQLite: finds tasks assigned to the agent with `flow_type = 'implementation'` and `status IN ('open', 'assigned', 'spec')`
   - If any such tasks exist AND code files are staged, blocks the commit
   - Always allows scaffolding file types (.md, .yaml, .json, .toml, .sh, etc.)
   - Fail-open: if DB query fails, commit proceeds

2. **`minion install-hooks`** CLI command that:
   - Installs the Claude Code Stop hook (poll-on-stop.sh)
   - Symlinks `scaffolding-gate.sh` into `.git/hooks/pre-commit`
   - Safe to run multiple times

3. **`scripts/poll-on-stop.sh`** — Claude Code Stop hook for inbox enforcement

---

## 2. Gap Analysis

### 2.1 What Already Works

The scaffolding-gate.sh hook is **functional and correctly designed**. It:
- Queries the right DB column (`flow_type = 'implementation'`)
- Checks the right pre-scaffolding statuses (`open`, `assigned`, `spec`)
- Allows scaffolding artifacts through
- Has proper safety guards (bypass, fail-open, agent-gated)

### 2.2 Gaps and Limitations

**Gap 1: Only covers `implementation` flow_type.**
Other flows (`bugfix`, `feature`, `hotfix`, `chore`) use the `_base` pipeline which has no scaffolding gate. The base flow goes: `open → assigned → in_progress → qe → fixed → verified → closed`. An agent on a `feature` task can commit code immediately after assignment.

**Gap 2: No file-to-task linkage.**
The hook checks if the agent has ANY implementation task in pre-scaffolding. It does NOT check if the specific files being committed are related to a specific task. If an agent has two tasks — one past scaffolding and one not — it blocks ALL code commits even for the scaffolded task.

**Gap 3: Hook is not installed by default.**
`minion install-hooks` must be run manually. New project setups or worktrees may not have the hook. Agents spawned without running install-hooks have no enforcement.

**Gap 4: Only blocks commits, not file writes.**
An agent can write implementation code to disk all day — the hook only fires at `git commit` time. The damage (wasted context/tokens on unplanned code) has already been done by then.

**Gap 5: Schema drift — `task_type` vs `flow_type`.**
The schema DDL in `schema.py` says `task_type TEXT DEFAULT 'bugfix'` but the actual DB column is `flow_type`. The hook uses `flow_type` (correct for the actual DB), but this drift could cause issues if the schema is recreated from DDL.

**Gap 6: No coverage for non-agent commits.**
Humans or scripts running without `MINION_AGENT_NAME` bypass the hook entirely. This is by design (no-op for regular terminal sessions), but means the rule is only enforced for spawned agents.

---

## 3. Feasibility Assessment

### 3.1 SQLite Performance in Pre-Commit Hook

**Verdict: Fast enough.** The current query is a single-table SELECT with an equality filter on `assigned_to` and `flow_type`, plus an IN clause on `status`. On a typical minion.db with <1000 tasks, this completes in <5ms. SQLite read operations are non-blocking — multiple agents can query simultaneously. The hook adds negligible latency to `git commit`.

### 3.2 Can the Hook Be Extended?

Yes. The hook's structure is clean and extensible. Adding support for more flow types or file-task linkage is straightforward.

### 3.3 Edge Cases

| Case | Current Behavior | Desired Behavior |
|------|-----------------|-----------------|
| Agent has no tasks | Hook passes | Correct — no enforcement needed |
| Agent has only non-implementation tasks | Hook passes | Gap — should check all flow types with scaffolding gates |
| Agent has mixed tasks (some scaffolded, some not) | Blocks ALL code commits | Could be smarter — check file-task linkage |
| Files not linked to any task | Hook passes | Acceptable — untracked files are outside the system |
| Multiple tasks touch same file | N/A (no file linkage) | Would need resolution policy |
| DB missing or corrupt | Hook passes (fail-open) | Correct — safety design |

---

## 4. Implementation Proposal

### Phase 1: Fix the Schema Drift (Low effort, high value)
Update `schema.py` to use `flow_type` instead of `task_type` to match the actual DB column. This prevents future breakage.

### Phase 2: Extend Hook to All Flow Types with Scaffolding Gates (Medium effort)
Instead of hardcoding `flow_type = 'implementation'`, the hook should:
1. Query all tasks assigned to the agent that are NOT in a terminal status
2. For each task, load its flow YAML and check `past_gate("scaffolding")`
3. Block if ANY non-terminal task has a scaffolding gate and hasn't passed it

**Challenge:** This requires the hook to parse YAML and walk the DAG — or alternatively, add a `minion` CLI command that the hook calls:
```bash
minion task check-scaffolding-gate --agent $AGENT_NAME
```
This would return exit code 0 (all clear) or 1 (blocked) with a message. The hook stays simple (bash), the logic lives in Python where the DAG engine already exists.

### Phase 3: Add Scaffolding Gates to More Flows (Low effort)
Add `gate: scaffolding` to the appropriate stage in `bugfix.yaml`, `feature.yaml`, etc. For base-inheriting flows, this means adding a `plan` or `scaffold` stage before `in_progress`.

### Phase 4: Auto-Install Hook on Spawn (Low effort, high value)
Have `minion spawn-party` and `minion agent register` (for terminal agents) automatically run `install-hooks` if the git pre-commit hook is missing. This eliminates Gap 3.

### Phase 5 (Optional): File-Task Linkage (High effort)
Map files to tasks using the `files` column on the tasks table (currently a TEXT field, could be JSON array). The hook would check: for each staged file, find the task that claims it, and verify that task is past scaffolding. This addresses Gap 2 but requires:
- Agents to consistently populate the `files` field
- A resolution policy for unclaimed files
- More complex SQL in the hook (or the CLI command from Phase 2)

**Recommendation:** Phases 1-4 are achievable in a single implementation cycle. Phase 5 should wait until file-task linkage is more mature.

---

## 5. Concrete Next Steps

1. **Create a feature task** for Phase 2 (CLI command `minion task check-scaffolding-gate`)
2. **Create a chore task** for Phase 1 (schema drift fix)
3. **Create a chore task** for Phase 4 (auto-install on spawn)
4. **Add Phase 3** to each flow type's backlog as needed
5. **Defer Phase 5** until file claims system is more robust

---

## 6. Summary

The mechanical enforcement infrastructure **already exists** in `scripts/scaffolding-gate.sh` and is correctly wired via `minion install-hooks`. The main gaps are: (a) it only covers the `implementation` flow type, (b) it's not auto-installed, and (c) it can't leverage the full DAG engine because it's a bash script doing raw SQL. The recommended fix is a thin CLI command (`minion task check-scaffolding-gate`) that the bash hook calls, bringing the full Python DAG engine into the enforcement path. This is feasible, fast (SQLite + in-memory DAG), and extends naturally to all flow types.
