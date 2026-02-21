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

All work lives under `.work/` in the project root.

```
.work/
├── battle-plans/              ← commander session plans (timestamped)
├── inbox/<agent>/             ← per-agent message inboxes
├── intel/                     ← findings, research, analysis
│   ├── audits/                ← codebase audits
│   ├── bench/                 ← benchmark research
│   ├── bugs/                  ← bug reports (BUG-*.md)
│   ├── design/                ← design docs (DESIGN-*.md)
│   ├── domain/                ← domain knowledge
│   ├── lang/                  ← language-specific analysis
│   └── tests/                 ← test infrastructure research
├── minion.db                  ← agent/task/message database
├── raid-log/                  ← session raid log
├── results/                   ← task deliverables
│   └── <mission>/             ← grouped by mission (bench/, tests/, etc.)
├── tasks/                     ← task specs
│   └── <mission>/             ← grouped by mission
└── traps/                     ← gotchas and landmines
    └── <topic>/               ← grouped by topic (gpu/, etc.)
```

### File routing rules

| Content | Location | Naming |
|---------|----------|--------|
| Bug report | `intel/bugs/` | `BUG-<slug>.md` |
| Design doc | `intel/design/` | `DESIGN-<slug>.md` |
| Codebase audit | `intel/audits/` | `<module>-audit.md` |
| Research/recon | `intel/<topic>/` | `<descriptive-name>.md` |
| Task spec | `tasks/<mission>/` | `<task-slug>.md` |
| Task result | `results/<mission>/` | `<task-slug>.md` |
| Gotcha/trap | `traps/` or `traps/<topic>/` | `<slug>.md` |

**Rules:**
- No floating files at `intel/` root — always use a subdirectory
- Group tasks and results by mission (bench, tests, migration, etc.)
- Bug reports belong in the **project where the bug lives**, not where you found it
