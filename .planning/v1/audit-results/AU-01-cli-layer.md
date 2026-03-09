# AU-01: CLI Layer Deep Dive Audit Results

**Auditor:** AU-01 (CLI Layer)
**Date:** 2026-03-09
**Codebase:** minion-factory (`src/minion/cli/` + `src/minion/output.py` + `src/minion/defaults.py`)
**Stats:** 21 CLI files, 1 output module, 1 defaults module, ~250 click options/arguments

---

## Command Tree (Step 1)

```
minion (root group)
  Global flags: --human, --compact, --project-dir/-C, --version

  Groups (18 groups):
    agent/         register, set-status, set-context, who, update-hp, cold-start,
                   refresh, fenix-down, retire, check-activity, check-freshness
    comms/         send/ (local, global), check-inbox, purge-inbox, list-history
    task/          create, assign, update, list, get, spec, lineage, submit-result,
                   close, done, reopen, pull, complete-phase, check-work, comment,
                   comments, define, result, review, test, block
    flow/          list, show, next-status, transition
    war/           set-plan, get-plan, update-status, log, list-log
    war-plan/      show, set, append
    file/          claim, release, list
    crew/          list, spawn, stand-down, halt, recruit, hand-off-zone, status
    trigger/       list, clear-moon-crash
    daemon/        run (hidden), start, stop, logs
    mission/       list, suggest, spawn
    backlog/       add, list, show, update, promote, kill, defer, lineage, reindex
    intel/         add, link, list, find, get, read, for-task, reindex, suggest,
                   register-docs
    req/           register, reindex, list, tree, status, update, link, unlinked,
                   orphans, create, decompose, itemize, findings, report
    global/        who, send, deregister, prune
    network/       serve, gen-cert, status, who, outbox, projects, overview, alerts,
                   project-agents
    api/           start, stop, status, restart, set-remote, list-remotes,
                   remove-remote, remote-status, remote-agents, remote-send,
                   remote-inbox, remote-projects, remote-overview, remote-alerts

  Top-level (ungrouped on root):
    poll, sitrep, install-docs, dashboard, end-session, tools, debrief,
    deregister, rename, interrupt, resume, install-hooks, docs

  Hidden aliases (backwards-compat): ~50 flat-name aliases
    e.g., register, send-local, create-task, spawn-party, etc.

  Max nesting: 3 levels (comms > send > local|global)
```

**Top-level command leaks identified:**
- `deregister` — should be under `agent` group
- `rename` — should be under `agent` group
- `interrupt` — should be under `agent` or `crew` group
- `resume` — should be under `agent` or `crew` group
- `end-session` — could be under `crew` group
- `debrief` — could be under a session group

---

## Filled Checklist

### AI-First CLI (19 rules)

| Rule | Status | Evidence |
|------|--------|----------|
| CMD-1 | **NO** | Noun-verb pattern throughout: `minion agent register`, `minion task create`, `minion comms send local`. Skill expects verb-noun (`minion register agent`). Consistent internal convention (kubectl-style) but violates the skill letter. All 18 groups follow noun-verb. |
| CMD-2 | **NO** | 3 levels at `minion comms send local` and `minion comms send global`. Skill says max 2 subcommand levels. All other commands are at 2 levels (group + command). Only `comms send` nests to 3. |
| CMD-3 | **NO** | Only 6 short flags across all CLI files: `-C` (project-dir), `-v` (verbose, flow list), `-p` (password-file, api), `-m` (message, api remote-send), `-o` (output, docs). The vast majority of options (~244 of ~250) lack short forms — e.g., `--agent`, `--name`, `--task-id`, `--crew`, `--status`, `--message`, `--from`, `--to` all have no short form. |
| CMD-4 | **NO** | Verb vocabulary inconsistencies: "register" (agent) vs "create" (task, req) vs "add" (backlog, intel) vs "spawn" (crew, mission) for creation operations. "deregister" vs "kill" vs "remove-remote" for deletion. "list" vs "who" for enumeration. "list-history" vs "list-log" vs "list-claims" for listing. "done" vs "close" vs "complete-phase" for completion. |
| OUT-1 | **NO** | JSON is the default output (output.py line 24: `json.dumps(data, indent=2)`). Human-readable mode is opt-in via `--human` flag. Skill expects human-readable default with `--json` for machine mode. Intentional inversion — agent-first design — but violates the rule as stated. |
| OUT-2 | **YES** | JSON is always the default output. All command handlers pass data through `_output()` which calls `json.dumps()`. The `--human` flag toggles to human-readable. Same data, different format. Effectively, the `--json` flag is "always on" by default. |
| OUT-3 | **PARTIAL** | `--compact` flag exists (main.py line 40) and returns pipe-friendly output via `_format_compact()` in output.py. However, the compact formatter only handles specific data shapes (status+agent, tools, triggers, playbook). For unrecognized data shapes, it falls back to full JSON (line 76). Not a true "IDs/names only" quiet mode. Also, **backlog_cmds.py bypasses the output funnel entirely** — 23 direct `click.echo(json.dumps(...))` calls, ignoring `--human` and `--compact` flags. |
| OUT-4 | **PARTIAL** | Most commands pass the same data dict through `_output()` which renders in 3 modes (JSON, human, compact). However: (1) backlog_cmds.py bypasses `_output()` completely — 23 direct `click.echo(json.dumps())` calls, so `--human` and `--compact` are silently ignored. (2) `agent set-status` passes only `ctx.obj["human"]` without compact (line 49). (3) Several `flow_cmds` error paths call `_output({"error": ...})` without human/compact args. |
| DISC-1 | **YES** | Click provides `--help` at every level automatically. All 18 groups and all subcommands have help text. Root CLI has an epilog: "Run 'minion <group> --help' to see subcommands." Main help includes quick-start examples. |
| DISC-2 | **PARTIAL** | Some commands include actionable hints: backlog add warns about missing `--flow-hint` with a follow-up command; api start error says "Use -p <file>, MINION_CLUSTER_TOKEN env var, or prompt." However, most error paths just return `{"error": "..."}` with no remediation guidance. Examples of unhelpful errors: `{"error": "MINION_NETWORK_URL not set."}` (no hint on how to set it), `{"error": "Backlog item not found."}` (no suggestion to try `backlog list`). |
| DISC-3 | **NO** | No fuzzy matching or "did you mean" suggestions for unknown commands. Click does not provide this by default. Would need `click-didyoumean` plugin or custom error handler. Typing `minion agnt register` just fails with "No such command 'agnt'." |
| CFG-1 | **YES** | Precedence chain verified: (1) Click flags (e.g., `--project-dir`) override everything, (2) env vars (`MINION_DB_PATH`, `MINION_CLASS`) read via `defaults.py`, (3) project config via `.work/` directory, (4) defaults in `defaults.py`. main.py line 64: `--project-dir` flag sets `MINION_DB_PATH` env, overriding defaults. |
| CFG-2 | **YES** | All env vars use `MINION_*` prefix consistently: `MINION_DB_PATH`, `MINION_DOCS_DIR`, `MINION_PROJECT`, `MINION_CLASS`, `MINION_CLUSTER_TOKEN`, `MINION_COORDINATOR_DB_PATH`, `MINION_AGENT_NAME`, `MINION_PROJECT_DIR`, `MINION_NETWORK_URL`, `MINION_HOOKS_BYPASS`. All defined or documented in defaults.py. |
| CFG-3 | **NO** | Config file locations not documented in `--help` output. The root `cli --help` text mentions quick-start and communication but not where `.work/minion.db` lives, which env vars are supported, or the config hierarchy. Users must read CLAUDE.md to discover these. |
| AGENT-1 | **PARTIAL** | Nearly all commands are fully non-interactive. However, `api_cmds.py` uses `getpass.getpass()` as a fallback for token input (lines 87, 171). When called without `-p` or `MINION_CLUSTER_TOKEN`, the `api start` and `api set-remote` commands prompt interactively. This would break agent invocation without TTY. The code does provide `-p` and env var alternatives, so agents CAN avoid the prompt — but the fallback violates the principle. |
| AGENT-2 | **YES** | Agent rules via CLAUDE.md (checked into repo), AGENTS.md (universal agent playbook), and system prompts injected at spawn time via `system_prefix` in crew YAMLs. The `minion docs` command generates a full CLI reference from Click introspection. |
| AGENT-3 | **YES** | Deterministic output: same input produces same JSON. No random elements, timestamps in output are from DB (reproducible). `_format_compact` is deterministic. All commands are stateless reads/writes against SQLite. |
| AGENT-4 | **NO** | Exit codes are inconsistent: (1) `output.py` always uses `sys.exit(1)` for errors. (2) `poll` uses 0 (content), 1 (timeout), 3 (stand_down/retire) — custom semantics. (3) `check-work` uses 0 (work available), 1 (no work). (4) backlog_cmds uses both `sys.exit(1)` and `raise SystemExit(1)` inconsistently. (5) No `exit(2)` for usage errors anywhere — Click handles these internally but the convention isn't documented. (6) crew_cmds, api_cmds also use `raise SystemExit(1)`. No documented exit code convention. |
| AGENT-5 | **NO** | No shell completions configured. Click supports `shell_complete` but it's not set up. No `_MINION_COMPLETE` env var handling. Running `eval "$(_MINION_COMPLETE=bash_source minion)"` would work if configured but it's not documented or tested. |

---

### Pragmatic Programmer (7 selected rules)

| Rule | Status | Evidence |
|------|--------|----------|
| PP-CRAFT-5 | **YES** | Command and option names reveal intent well. `cold-start`, `fenix-down`, `complete-phase`, `check-freshness`, `hand-off-zone` — all descriptive. File names: `agent_cmds.py`, `backlog_cmds.py`, `war_plan_cmds.py`. Option names: `--class-required`, `--blocked-by`, `--flow-hint`, `--requesting-agent`. |
| PP-DECOUPLE-1 | **YES** | No train wrecks in CLI handlers. Commands follow a clean pattern: parse args, lazy-import business logic, call function, pass result to `_output()`. No chained method calls. Deepest chain is `ctx.obj["human"]` (2 levels, acceptable). |
| PP-DECOUPLE-5 | **YES (CLI layer)** | Within the CLI layer itself, only 3 direct `os.environ` reads: main.py sets `MINION_DB_PATH` (intentional override from flag), api_cmds.py reads `MINION_CLUSTER_TOKEN` (documented 3-priority cascade). All other config resolution goes through `defaults.py` resolvers. CLI layer is clean; the 29 scattered env reads from AU-00 are in business logic, not CLI. |
| PP-CONTRACT-2 | **YES** | CLI crashes early on errors. `output.py` calls `sys.exit(1)` immediately on `{"error": ...}` data (line 14). Auth checks via `require_class()` fail fast. backlog_cmds catches ValueError and exits with error JSON + `sys.exit(1)`. No silent failures observed in CLI handlers. |
| PP-DRY-1 | **NO** | `backlog_cmds.py` duplicates the output pattern — 23 direct `click.echo(json.dumps(...))` calls instead of using `_output()`. Every other CLI module uses `_output()`. This is a clear DRY violation: the error-handling + JSON output pattern is reimplemented 23 times in one file. Also, `_resolve_token()` in api_cmds.py duplicates the token resolution logic from the `api start` handler. |
| PP-DRY-2 | **PARTIAL** | CLI boilerplate is somewhat repetitive across files (import pattern, `register_commands`, group definition, `@click.pass_context`, `_output(result, ctx.obj["human"])`) but this is inherent to Click's decorator pattern. The `_agent_option` helper (main.py line 31) is a good DRY improvement — reused across 10+ files. auth `require_class("lead")(lambda: None)()` pattern is repeated ~15 times but hard to DRY further without a decorator. |
| PP-ORTH-1 | **YES** | Each CLI module is self-contained and covers one domain. Modules only import from `minion.cli.main` (for `_output` and `_agent_option`) and their respective business logic modules (lazy-imported inside handlers). No cross-module CLI dependencies. Changes to one group don't affect others. |

---

### Clean Architecture (4 selected rules)

| Rule | Status | Evidence |
|------|--------|----------|
| CA-SCRM-1 | **YES** | `cli/` file names communicate use cases by domain: `agent_cmds.py`, `backlog_cmds.py`, `comms_cmds.py`, `crew_cmds.py`, `task_cmds.py`, `intel_cmds.py`, `req_cmds.py`. Not framework names. One could infer "multi-agent coordination" from the file listing. |
| CA-SCRM-2 | **YES** | A stranger reading `ls cli/` would understand: agents, backlog, comms, crew, daemon, files, flow, intel, missions, network, requirements, tasks, triggers, war/war-plan. The domain is immediately apparent. The `_cmds.py` suffix is a clear convention. |
| CA-COMP-4 | **YES** | Classes that change together are colocated. Agent lifecycle commands are all in `agent_cmds.py`. Task lifecycle is all in `task_cmds.py`. Comms send/inbox are all in `comms_cmds.py`. The grouping matches the domain model. |
| CA-COMP-5 | **YES** | Classes used together are in the same component. Crew spawn + recruit + stand-down + halt are all in `crew_cmds.py`. War plan + war log are split between `war_cmds.py` and `war_plan_cmds.py` (slightly fragmented but both are war-related). |

---

### Implementation Coding Core (9 selected rules)

| Rule | Status | Evidence |
|------|--------|----------|
| IC-HDR-1 | **NO** | Zero files have formal PURPOSE header. All 21 CLI files use module-level docstrings instead (e.g., `"""Agent group -- register, deregister, rename, set-context, ..."`). Reference SF-01 from AU-00 — systemic finding. |
| IC-HDR-2 | **NO** | Zero files have formal RESPONSIBILITIES header. Docstrings loosely describe responsibilities but not in mandated format. Reference SF-01. |
| IC-HDR-3 | **NO** | Zero files have formal NOT RESPONSIBLE FOR header. Reference SF-01. |
| IC-HDR-4 | **NO** | Zero files have formal DEPENDENCIES header. Reference SF-01. |
| IC-HDR-5 | **YES** | The docstring headers that do exist are persistent — no evidence of deletion. The convention is consistently maintained across all CLI files. The `_cmds.py` module docstring pattern is uniform. |
| IC-VER-1 | **YES** | CLI builds without errors. Entry point in pyproject.toml (`minion = "minion.cli:cli"`) resolves correctly. All imports are valid. test_imports.py confirms import chain works. |
| IC-VER-2 | **YES** | All imports present and correct. Each CLI module's lazy imports (inside handlers) resolve at runtime. No circular imports — lazy import pattern prevents this. |
| IC-VER-3 | **YES** | Tests pass. test_cli.py and test_entrypoint.py provide surface-level CLI verification. |
| IC-VER-4 | **YES** | Build/test discipline evident — `uv run pytest` is standard verification step. |

---

## Findings

| # | Rule | Severity | Affected Files | Description | Remediation |
|---|------|----------|----------------|-------------|-------------|
| F001 | CMD-1 | **Info** | All cli/*.py | **Noun-verb pattern is intentional** (kubectl-style) but violates skill letter. `minion agent register` not `minion register agent`. Consistent across all 18 groups. | Document as intentional design decision. No migration needed — consistency matters more than strict skill compliance here. |
| F002 | CMD-2 | **Minor** | comms_cmds.py | **3-level nesting** at `minion comms send local/global`. Only violation. | Consider flattening to `minion comms send-local` / `minion comms send-global` (already have flat aliases `send-local`, `send-global`). |
| F003 | CMD-3 | **Moderate** | All cli/*.py | **~244 of ~250 options lack short flags.** Only 6 short flags exist: `-C`, `-v`, `-p`, `-m`, `-o`. High-frequency agent options like `--agent`, `--task-id`, `--name`, `--message`, `--status` have no short forms. Agents burn tokens typing full flag names. | Add short flags for top-20 most-used options: `-a` (agent), `-t` (task-id), `-n` (name), `-m` (message), `-s` (status), `-f` (from), etc. |
| F004 | CMD-4 | **Moderate** | Multiple | **Verb vocabulary inconsistencies.** Create operations: register/create/add/spawn. Delete operations: deregister/kill/remove-remote. List operations: list/who. Completion operations: done/close/complete-phase. | Standardize on canonical verbs: `create` (new resources), `delete` (remove), `list` (enumerate), `close` (complete). Add aliases for backwards compat. |
| F005 | OUT-1 | **Info** | output.py | **JSON is default output** — inverted from skill expectation. Correct for agent-first CLI. Skill assumes human-first design. | Document as intentional. This is a STRENGTH for an agent-first CLI despite violating the skill letter. |
| F006 | OUT-3/4 | **Moderate** | backlog_cmds.py | **backlog_cmds.py bypasses output funnel.** 23 direct `click.echo(json.dumps(...))` calls. `--human` and `--compact` flags silently ignored for all backlog commands. Every other CLI module uses `_output()`. | Refactor backlog_cmds.py to use `_output()` like all other modules. Requires passing `ctx.obj["human"]` and `ctx.obj["compact"]`. |
| F007 | OUT-4 | **Minor** | agent_cmds.py, flow_cmds.py | **Inconsistent _output() argument passing.** `agent set-status` (line 49): passes `human` only, no `compact`. Several `flow_cmds` error paths: `_output({"error": ...})` with no human/compact args at all. | Audit all `_output()` calls, ensure all 3 args are always passed. |
| F008 | DISC-2 | **Minor** | Multiple | **Most error messages lack actionable hints.** e.g., `"MINION_NETWORK_URL not set."` (no setup instructions), `"Backlog item not found."` (no suggestion to list). backlog commands DO include good hints (flow-hint warning). | Add remediation hints to top-10 most common error paths. |
| F009 | DISC-3 | **Minor** | main.py | **No fuzzy matching for unknown commands.** `minion agnt` fails with generic "No such command" without suggesting `agent`. | Install `click-didyoumean` package or add custom error handler. |
| F010 | CFG-3 | **Minor** | main.py | **Config locations not in --help.** Users must read CLAUDE.md to discover `.work/`, env vars, and config hierarchy. | Add config location summary to root CLI group epilog. |
| F011 | AGENT-1 | **Minor** | api_cmds.py | **Interactive getpass() fallback** in `api start` and `api set-remote` (lines 87, 171). Breaks agents without TTY. Mitigated by `-p` file and env var alternatives, but fallback path is interactive. | Add `--token` flag as additional non-interactive option. Guard getpass with `sys.stdin.isatty()` check. |
| F012 | AGENT-4 | **Moderate** | Multiple | **Exit codes undocumented and inconsistent.** poll: 0/1/3. check-work: 0/1. output.py: always 1 for error. No exit(2) for usage errors. Both `sys.exit(1)` and `raise SystemExit(1)` used. | Define exit code convention (0=success, 1=error, 2=usage, 3=signal). Document in root --help. Standardize on `sys.exit()` not `raise SystemExit()`. |
| F013 | AGENT-5 | **Minor** | N/A | **No shell completions.** Click supports this but it's not configured or documented. | Add `eval "$(_MINION_COMPLETE=bash_source minion)"` to docs. Test with bash/zsh/fish. |
| F014 | PP-DRY-1 | **Major** | backlog_cmds.py | **backlog_cmds.py reimplements output 23 times** instead of using `_output()`. Every `click.echo(json.dumps(result, indent=2))` is a copy-paste of the JSON output path. Error handling pattern `try/except ValueError -> json error -> sys.exit(1)` repeated 10 times. | Refactor to use `_output()`. Extract error-handling wrapper for the repeated try/except pattern. |
| F015 | IC-HDR-* | **Major (systemic)** | All 21 cli/*.py | **No formal comment headers.** Zero files have PURPOSE/RESPONSIBILITIES/NOT RESPONSIBLE FOR/DEPENDENCIES in mandated format. All use module-level docstrings. Reference AU-00 SF-01. | Systemic remediation — add headers to all 21 CLI files per IC-HDR template. Low complexity per file but high count. |
| F016 | CMD-4 | **Minor** | top_level.py | **Top-level command leaks.** `deregister`, `rename`, `interrupt`, `resume` are registered on the root CLI instead of under `agent` or `crew` groups. They conceptually belong in groups but were left at top level. | Move to appropriate groups, add hidden root aliases for backwards compat. |

---

## Strengths (Preserve These)

1. **Consistent module pattern** — Every CLI module follows the same structure: module docstring, `register_commands(cli)` function, group definition, subcommands. This makes the CLI highly navigable and predictable.

2. **Lazy imports** — All business logic is imported inside command handlers, not at module top level. This prevents circular imports, speeds up CLI startup, and keeps CLI layer decoupled from business logic. Every single handler does `from minion.whatever import function`.

3. **Single output funnel (output.py)** — `_output()` is the canonical output path supporting JSON (default), human-readable, and compact modes from the same data dict. 17 of 18 CLI modules use it consistently. (backlog_cmds.py is the exception.)

4. **_agent_option() helper** — A DRY helper (main.py line 31) that standardizes the `--agent` flag with automatic heartbeat callback across all modules. Used consistently in 10+ modules.

5. **Backwards-compatible aliases** — aliases.py provides hidden flat-name commands (e.g., `minion register`, `minion spawn-party`) that old scripts/agents can use while the new grouped syntax is canonical. Clean migration path.

6. **Non-interactive by design** — Except for the `api start/set-remote` getpass fallback, the entire CLI is fully non-interactive. Zero prompts, zero confirmations, zero "are you sure?" dialogs. Agent-safe.

7. **Rich help text** — Most commands have detailed help strings with `\b` formatted sections, examples, and behavioral notes (e.g., poll explains exit codes, comms send explains routing). The root CLI help includes a quick-start guide.

8. **Auth checks at CLI boundary** — `require_class("lead")(lambda: None)()` is called at the CLI handler level, failing fast before any business logic runs. Auth is enforced at the entry point, not deep in the call stack.

9. **Defaults.py as config canon** — All path resolution and env var names are centralized in `defaults.py` with named constants (`ENV_DB_PATH`, `ENV_CLASS`, etc.) and resolver functions. CLI files reference this, not raw env vars (mostly).

10. **Group organization matches domain model** — 18 groups map to the domain: agent, comms, task, flow, crew, backlog, intel, req, war, etc. A domain expert can find commands by thinking about the domain, not the framework.

---

## Summary Statistics

| Skill | Rules | YES | NO | PARTIAL | Info |
|-------|-------|-----|----|---------|----- |
| AI-First CLI | 19 | 6 | 9 | 4 | — |
| Pragmatic Programmer | 7 | 5 | 1 | 1 | — |
| Clean Architecture | 4 | 4 | 0 | 0 | — |
| Implementation Coding Core | 9 | 5 | 4 | 0 | — |
| **Total** | **39** | **20** | **14** | **5** | — |

### Findings by Severity

| Severity | Count | IDs |
|----------|-------|-----|
| Major | 2 | F014, F015 |
| Moderate | 4 | F003, F004, F006, F012 |
| Minor | 7 | F002, F007, F008, F009, F010, F011, F013, F016 |
| Info | 2 | F001, F005 |
| **Total** | **16** | |

### Priority Remediation Order

1. **F014 (Major)** — backlog_cmds.py output bypass. Quick win: refactor 1 file to use `_output()`.
2. **F006 (Moderate)** — same root cause as F014. Fixed together.
3. **F012 (Moderate)** — exit code convention. Define once, apply everywhere.
4. **F003 (Moderate)** — short flags. High agent-impact: saves tokens per invocation.
5. **F004 (Moderate)** — verb vocabulary. Document canonical verbs, add aliases.
6. **F015 (Major)** — comment headers. Systemic but mechanical. Batch across all CLI files.
7. Everything else is minor/info.
