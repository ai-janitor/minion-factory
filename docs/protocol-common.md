# Minion Comms — Common Protocol

## Hard Blocks (Server-Enforced)

These will BLOCK your commands. Don't fight them — comply.

1. **Inbox discipline:** `send` blocked if you have unread messages. Call `minion check-inbox` first.
2. **Context freshness:** `send` blocked if your `set-context` is stale. Thresholds: coder/builder/recon 5m, lead 15m, oracle 30m.
3. **Battle plan required:** No `send` or `create-task` without an active battle plan.
4. **File claims:** Can't claim a file another agent holds. You're auto-waitlisted.
5. **Task close requires result:** `close-task` blocked without a submitted result file.
6. **Class restrictions:** Lead-only commands reject non-lead callers.

## Completion Protocol

When you finish a request from anyone (orders, questions, tasks), **always message back to the requestor**. Check your inbox for the sender's name. No silent completions — the requestor must know you're done and what you found.

## Auto Behaviors

- **Auto-CC lead:** Every non-lead message is CC'd to lead automatically.
- **Trigger detection:** Trigger words in messages are auto-detected and flagged.
- **Activity warnings:** `update-task` warns at activity count 4+.

## CLI Usage

All commands: `minion <command> [options]`. JSON output by default, `--human` for tables.

```bash
minion register --name <name> --class <class>
minion check-inbox --agent <name>
minion send --from <name> --to <target> --message "..."
minion set-context --agent <name> --context "what you have loaded"
minion who
minion sitrep                    # fused view of everything
```

## Trigger Words

Use in messages for fast coordination. Server detects automatically.

| Code | Effect |
|------|--------|
| `fenix_down` | Dump knowledge to disk |
| `moon_crash` | Emergency — blocks all task assignments |
| `stand_down` | All daemons exit gracefully |
| `sitrep` | Request status report |
| `rally` | Focus on target |
| `retreat` | Pull back, reassess |

## Filesystem Locations

### Core Principle: Filesystem IS the Source of Truth

`.work/` is a **filesystem database**. Content lives in markdown. Structure lives in directories. The SQL DB (`minion.db`) is a rebuildable runtime index — it accelerates queries and tracks metadata. If the DB dies, rebuild it by scanning the filesystem. Nothing structural is lost.

`.work/` is its own **git repository** — nested inside the project but independent. It tracks the process of how the app came together, not the app itself. The project repo gitignores `.work/`. Agents commit freely to `.work/` without touching the project's commit history. `minion init` runs `git init .work/` as part of setup.

### Directory Tree

```
.work/                                 ← its own git repo
├── .git/
├── requirements/                      ← requirements tree (see Requirements section below)
│   ├── features/                      ← ideas, brain dumps, new functionality
│   └── bugs/                          ← discoveries from running systems
├── battle-plans/                      ← commander session plans (timestamped)
├── inbox/<agent>/                     ← per-agent message inboxes
├── intel/                             ← findings, research, analysis
│   ├── audits/                        ← codebase audits
│   ├── bench/                         ← benchmark research
│   ├── design/                        ← design docs (DESIGN-*.md)
│   ├── domain/                        ← domain knowledge
│   ├── lang/                          ← language-specific analysis
│   └── tests/                         ← test infrastructure research
├── minion.db                          ← agent/task/message database (runtime index)
├── raid-log/                          ← session raid log
├── results/                           ← task deliverables
│   └── <mission>/                     ← grouped by mission (bench/, tests/, etc.)
├── tasks/                             ← task specs
│   └── <mission>/                     ← grouped by mission
└── traps/                             ← gotchas and landmines
    └── <topic>/                       ← grouped by topic (gpu/, etc.)
```

### File Routing Rules

| Content | Location | Naming |
|---------|----------|--------|
| Feature requirement | `requirements/features/<slug>/` | `README.md` |
| Bug requirement | `requirements/bugs/<slug>/` | `README.md` |
| Design doc | `intel/design/` | `DESIGN-<slug>.md` |
| Codebase audit | `intel/audits/` | `<module>-audit.md` |
| Research/recon | `intel/<topic>/` | `<descriptive-name>.md` |
| Task spec | `tasks/<mission>/` | `<task-slug>.md` |
| Task result | `results/<mission>/` | `<task-slug>.md` |
| Gotcha/trap | `traps/` or `traps/<topic>/` | `<slug>.md` |

**Rules:**
- No floating files at `intel/` root — always use a subdirectory
- Group tasks and results by mission (bench, tests, migration, etc.)
- Bug reports go into `requirements/bugs/` — they enter the same decomposition pipeline as features

## Requirements Tree

Requirements are the upstream of tasks. Every task traces back to a requirement. The requirements tree lives at `.work/requirements/` and follows strict filesystem conventions.

### Everything Is a Folder

Every requirement — root, branch, or leaf — is a folder with a `README.md`. No exceptions. No standalone `.md` files.

- A leaf today might need decomposition tomorrow. If it's already a folder, no migration needed.
- `README.md` is always the content. You never have to guess which file is the entry point.
- `ls` at any level gives you a clean list of folder names. No noise.

### Origin-Based Organization

Top level separates by origin — where did this requirement come from?

```
.work/requirements/
├── features/                          ← ideas, brain dumps, new functionality
├── bugs/                              ← discoveries from running systems
```

More origins can be added later (`refactors/`, `tech-debt/`, etc.) without changing the convention. The pipeline inside is identical regardless of origin.

### Three-Stage Document Pipeline

A raw brain dump doesn't go straight to a tree. It goes through an intermediate step:

```
README.md (raw) → itemized-requirements.md → child folders
```

1. **Raw doc** (`README.md`) — unstructured brain dump or bug writeup. Never modified after creation.
2. **Itemized doc** (`itemized-requirements.md`) — structured numbered list extracted from the raw doc. Maps prose → discrete requirements.
3. **Child folders** — each numbered section expanded into its own folder with `README.md`.

### Filenames Are Data

Filenames encode section number and slug. You never have to open a file to know what it is and where it fits. `ls` is your query engine.

### Full Example

```
.work/requirements/
├── features/
│   ├── genesis/                                   ← the original app vision
│   │   ├── README.md                              ← raw brain dump (untouched)
│   │   ├── itemized-requirements.md               ← numbered index extracted from raw
│   │   ├── 001-auth-flow/                         ← section 1
│   │   │   ├── README.md                          ← section 1 expanded
│   │   │   ├── 001.1-oauth-provider/
│   │   │   │   └── README.md
│   │   │   ├── 001.2-session-management/
│   │   │   │   └── README.md
│   │   │   └── 001.3-token-refresh/
│   │   │       └── README.md
│   │   ├── 002-task-dashboard/
│   │   │   └── README.md
│   │   └── 003-agent-comms/                       ← leaf (just README.md, no children yet)
│   │       └── README.md
│   └── requirements_2-23/                         ← next day's additions
│       ├── README.md
│       └── ...
├── bugs/
│   ├── preview-final-word-loss/
│   │   ├── README.md                              ← bug writeup
│   │   ├── itemized-requirements.md
│   │   ├── 001-refactor-handoff/
│   │   │   └── README.md
│   │   ├── 002-fix-queue-drain/
│   │   │   └── README.md
│   │   └── 003-add-word-loss-logging/
│   │       └── README.md
│   └── gpu-probe-timeout/
│       ├── README.md
│       └── ...
```

### Filesystem As Query Engine

| Query | Command |
|-------|---------|
| Parent of a requirement | `dirname(dirname(file_path))` (up past README.md) |
| Children of a requirement | `ls` the folder — child folders are children |
| Full lineage | directory path from root to leaf |
| What's been decomposed | has child folders (not just README.md) |
| What's a leaf | folder contains only README.md |
| Partial decomposition progress | diff itemized section count vs child folder count |
| Section mapping | folder prefix (001, 002) matches itemized doc section numbers |
| All features | `ls .work/requirements/features/` |
| All bugs | `ls .work/requirements/bugs/` |

### Decomposition Rules

1. **Genesis decomposition** (raw → itemized → children) is the first pass on any root doc. The planner reads the raw `README.md`, produces `itemized-requirements.md`, then expands each section into a numbered child folder.
2. **Recursive decomposition** — any child that's still too complex gets decomposed further into its own children. Same convention, deeper nesting.
3. **When to stop decomposing** — can one agent, in one session, hold enough context to finish this requirement? If no, decompose further. This is a planner judgment call.
4. **Resumability** — planner dies after decomposing 8 of 20 sections? Next planner reads `itemized-requirements.md` (20 sections), runs `ls` (8 folders), and picks up sections 9-20. The filesystem diff IS the progress tracker.
5. **Leaf requirements become tasks** — when a requirement is small enough to implement in one session, it gets converted to a task. The task's `requirement_path` column points back to the requirement folder.

### Requirement → Task Traceability

Every task has a `requirement_path` column pointing to the requirement folder it came from. This enables:

| Question | How |
|----------|-----|
| What spawned this task? | `task.requirement_path` → read the folder's README.md |
| Is this requirement done? | All tasks pointing into this path are closed |
| What hasn't been decomposed? | Folders with only README.md and no itemized doc |
| What % of requirements are tasked? | Query the `requirements` index table by stage |

### Design Reference

Full design rationale, edge cases, and three-tier DAG architecture: `.work/intel/design/DESIGN-genesis-decomposition-pipeline.md`
