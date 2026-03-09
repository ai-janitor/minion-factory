# AU-10 Cross-Cutting + Small Domains Audit Results

**Auditor:** AU-10 (Cross-Cutting Deep Dive)
**Date:** 2026-03-09
**Codebase:** minion-factory (`src/minion/`)
**Scope:** Cross-cutting files (D15), requirements package (D11), backlog package (D13)

---

## Cross-Cutting Pattern Analysis

### Logging — 3 Competing Patterns (SF-02 confirmed CRITICAL)

| Pattern | Files | Occurrences | Context |
|---------|-------|-------------|---------|
| `logging.getLogger` | 3 | 3 | db/migrations.py, db/coordinator.py, intel/_frontmatter.py |
| `print()` to stderr/stdout | 27+ | 55+ | monitoring.py, crew/_tmux.py, daemon/runner/*, network/server.py, providers/*.py, comms/*.py |
| `click.echo()` | 10+ | 45+ | output.py (canonical), auth.py, cli/*.py, crew/logs.py |

**Analysis:**
- `logging.getLogger` — proper structured logging, used in only 3 files. No `logging.basicConfig()` or handler configuration found anywhere in the codebase. These loggers write to nowhere unless a consumer configures the root logger.
- `print()` — used as the de facto warning/error/operational log. Split into two sub-patterns: `print(..., file=sys.stderr)` for warnings (correct) and `print(...)` to stdout for server startup info (also correct for user-facing output). However, no structured format, no log levels, no timestamps.
- `click.echo()` — correct for CLI output. Used in output.py single funnel (good) and directly in cli/*.py (acceptable). Also used in auth.py decorators for error messages to stderr.

**Verdict:** No canonical logging strategy exists. The 3 patterns serve different purposes (stdlib logging for library code, print for daemon/operational, click.echo for CLI) but this split is undocumented and inconsistent. No log configuration, no structured logging, no log levels in print() calls.

### Error Handling — Two Competing Patterns (SF-03 confirmed MAJOR)

| Pattern | Files | Usage Context |
|---------|-------|---------------|
| `return {"error": "..."}` (dict-return) | 25+ files | Business logic functions (monitoring, filesafety, triggers, warroom, intel/*, backlog/*, comms/*) |
| `raise ValueError/FileNotFoundError/RuntimeError` (raise stdlib) | 20+ files | Config loaders (crew/config, daemon/config, missions/loader, tasks/loader), backlog/promote, requirements/* |
| `raise click.ClickException/UsageError` | 3 files | CLI layer (cli/api_cmds.py, cli/crew_cmds.py, requirements/crud.py) |

**Analysis:**
- **Dict-return pattern** — functions return `{"error": "msg"}` and `output.py` checks `if "error" in data:` then `sys.exit(1)`. This is the dominant pattern for CLI-consumed business logic.
- **Raise pattern** — used in config/loader validation where callers wrap in try/except. Also used in backlog/promote.py which mixes both: raises ValueError for validation, but checks `{"error": ...}` from downstream calls.
- **No custom exception hierarchy** — zero custom Exception subclasses in entire codebase. All raises use stdlib exceptions (ValueError, FileNotFoundError, RuntimeError, KeyError).
- **Risk:** Callers can accidentally ignore error dicts by not checking for the "error" key. The dict-return pattern is a convention, not a type-system enforced contract.
- **103 `except Exception` blocks across 43 files** — many are appropriate (daemon resilience), but some swallow errors silently (monitoring.py lines 312-313: `except Exception: pass`).

### Configuration — defaults.py vs Direct os.environ (SF-05 confirmed MODERATE)

**defaults.py coverage:**
- Defines: `ENV_DB_PATH`, `ENV_DOCS_DIR`, `ENV_PROJECT`, `ENV_CLASS`, `ENV_COORDINATOR_DB_PATH`
- Resolvers: `resolve_db_path()`, `resolve_docs_dir()`, `resolve_work_dir()`, `resolve_swarm_runtime_dir()`, `resolve_coordinator_db_path()`, `resolve_path()`

**Direct os.environ reads that bypass defaults.py (33 occurrences across 15 files):**

| File | Env Var | In defaults.py? | Should Use defaults.py? |
|------|---------|-----------------|------------------------|
| auth.py:228 | `MINION_CLASS` | YES (ENV_CLASS) | YES — should use `defaults.ENV_CLASS` |
| auth.py:241 | `MINION_AGENT_NAME` | NO | MAYBE — could add to defaults.py |
| api/daemon.py:118 | `MINION_NETWORK_INSECURE` | NO | YES — add to defaults.py |
| api/daemon.py:136 | `os.environ.copy()` | N/A | N/A — env passthrough |
| crew/daemon.py:29 | `os.environ` passthrough | N/A | N/A — env passthrough |
| crew/daemon.py:38 | `PATH` | NO | N/A — system env |
| crew/daemon.py:132-133 | `MINION_TS_DAEMON_DIR` | NO | YES — add to defaults.py |
| crew/daemon.py:155 | `MINION_CLASS`, `MINION_PROJECT` | YES | YES — use defaults constants |
| cli/main.py:65 | `MINION_DB_PATH` | YES | Already uses ENV_DB_PATH elsewhere |
| crew/spawn.py:203 | `ENV_DB_PATH` | YES | GOOD — uses defaults constant |
| crew/config.py:85,91 | `ENV_DB_PATH`, `ENV_DOCS_DIR` | YES | GOOD — uses defaults constants |
| daemon/config.py:44,49 | `ENV_DB_PATH`, `ENV_DOCS_DIR` | YES | GOOD — uses defaults constants |
| daemon/runner/_alerting.py:26 | `os.environ.items()` filtering | N/A | N/A — env passthrough |
| daemon/runner/_polling.py:36,71 | `os.environ.items()` filtering | N/A | N/A — env passthrough |
| daemon/runner/_hp.py:126 | `os.environ.items()` filtering | N/A | N/A — env passthrough |
| daemon/runner/_execution.py:70 | `os.environ.items()` filtering | N/A | N/A — env passthrough |
| cli/api_cmds.py:84,169 | `MINION_CLUSTER_TOKEN` | NO | YES — add to defaults.py |
| network/handlers/compat.py:56 | `MINION_COMPAT_PROJECT` | NO | YES — add to defaults.py |
| network/client.py:19-22 | `MINION_NETWORK_URL`, `MINION_CLUSTER_TOKEN`, `MINION_NETWORK_INSECURE` | NO | YES — add all 3 to defaults.py |
| network/server.py:192,207 | `MINION_CLUSTER_TOKEN`, `MINION_NETWORK_INSECURE` | NO | YES — add to defaults.py |

**Verdict:** defaults.py covers core paths (DB, docs, work dirs) well. But 5 network/cluster env vars (`MINION_CLUSTER_TOKEN`, `MINION_NETWORK_URL`, `MINION_NETWORK_INSECURE`, `MINION_COMPAT_PROJECT`, `MINION_TS_DAEMON_DIR`) are scattered direct reads with no canonical constants. ~12 of 33 reads are env passthrough (acceptable); ~8 use defaults constants (good); ~13 bypass defaults.py (findings).

### Auth — Inline _check_token Duplication (SF-08 contained)

| Location | Function | Used By |
|----------|----------|---------|
| `network/server.py:37-42` | `_check_token(headers, expected)` | `_Handler.do_GET`, `_Handler.do_POST` |
| `network/auth.py:18-34` | `check_token(headers, expected)` + `AuthMixin.require_auth()` | Not yet integrated into _Handler |
| `auth.py:285-337` | `require_class()`, `require_scope()` decorators | CLI command functions |

**Analysis:**
- `network/auth.py` was scaffolded (has formal PURPOSE/RESPONSIBILITIES headers — one of the few files with them) to centralize network auth. It defines `check_token()` and `AuthMixin`.
- `network/server.py` still has the original `_check_token()` inline — identical logic, not yet migrated to use `network/auth.py`.
- **This is a partial migration.** The centralized module exists but isn't wired in. Two implementations coexist.
- CLI auth (`auth.py` decorators) and network auth (`network/auth.py`) are correctly separate concerns — different trust boundaries.

**Verdict:** Minor duplication. `network/auth.py` is ready; `server.py` just needs to import from it instead of defining its own `_check_token`. The scaffolding is already done.

### Pattern Registry (De Facto)

| Concern | De Facto Pattern | Documented? | Consistent? |
|---------|-----------------|-------------|-------------|
| Logging | 3 competing: logging, print, click.echo | No | No |
| Error handling | dict-return + raise stdlib | No | Partially — dict for business logic, raise for config |
| Config | defaults.py + direct env reads | Partially (CLAUDE.md mentions defaults.py) | No — 13 env vars bypass defaults.py |
| Auth (CLI) | require_class/require_scope decorators | Yes (auth.py docstrings) | Yes |
| Auth (network) | _check_token + AuthMixin (unmigrated) | Partially (network/auth.py scaffold) | No — duplicate exists |
| Output (CLI) | output.py single funnel | Implicit | Mostly — some CLI files bypass it |
| DB access | get_db() + connection-per-call | Implicit | Yes |
| File write | fs.atomic_write_file() | Implicit | Yes — used consistently |

**No formal pattern-registry.md exists.** De facto patterns are tribal knowledge, not documented.

---

## Cross-Cutting Utility Review

### monitoring.py
- Comprehensive monitoring functions: `party_status()`, `check_activity()`, `check_freshness()`, `sitrep()`, `update_hp()`.
- 6 `print()` calls for warnings (corrupt timestamps) — should use structured logging.
- `_fire_hp_alerts()` has its own DB connection — correctly isolated.
- Not real observability: no metrics, no structured events, no dashboards. It is operational status checking, which is appropriate for the scale.

### filesafety.py
- Clean implementation: `claim_file()`, `release_file()`, `get_claims()`.
- Proper transaction handling with `conn.commit()`.
- Waitlist feature for contended files.
- No size/count limits on claims — could grow unbounded (low risk at current scale).

### fs.py
- Atomic write (`atomic_write_file`) using temp+rename — correct pattern.
- `read_content_file()` has **no size limit** — reads entire file into memory. Low risk for message/plan files (typically <10KB) but could be a problem if file paths are ever user-controlled.
- Path builders use `_slugify()` for filesystem safety.

### triggers.py
- Thin wrapper: `get_triggers()` returns TRIGGER_WORDS dict from auth.py, `clear_moon_crash()` manages flag state.
- Clean, no findings.

### output.py
- Single funnel for CLI output: JSON (default), human-readable, compact modes.
- Error handling: `if "error" in data:` → `sys.exit(1)`. This is the convention that makes dict-return errors work.
- Compact formatter (`_format_compact`) handles specific data shapes.
- **Not used by all CLI commands** — `cli/backlog_cmds.py` does `click.echo(json.dumps(...))` directly instead of routing through `output()`.

### defaults.py
- Clean single-source-of-truth for path resolution.
- Walk-up logic in `resolve_db_path()` handles subdirectory launches.
- Missing: network env var constants (see Config analysis above).

---

## Small Domain Results

### Requirements Package (D11)

**Files:** `__init__.py`, `crud.py`, `decompose.py`, `findings.py`, `itemize.py`, `report.py`

- **Clean API surface:** `__init__.py` re-exports all public functions (15 names).
- **Validation:** `decompose.py` and `itemize.py` use `raise ValueError` for spec validation — consistent with the "raise for config/loaders" pattern.
- **Test coverage:** `test_requirements.py` (26 functions) + `test_req_decompose_inline.py` — well covered.
- **PP-DRY:** No duplication observed. Each file has a clear, single responsibility.
- **PP-ORTH:** Self-contained; changes to decompose don't ripple to itemize.
- **IC-HDR:** No formal headers (standard docstrings only) — systemic finding, not unique to this package.

### Backlog Package (D13)

**Files:** `__init__.py`, `add_item.py`, `close_item.py`, `get_item.py`, `lineage.py`, `list_items.py`, `path_resolution_and_slug.py`, `promote.py`, `reindex.py`, `update_item.py`

- **Clean API surface:** `__init__.py` re-exports 10 public functions.
- **Filesystem-as-DB done right:** Items live under `.work/backlog/<type>/<slug>/` as README.md folders. The DB is a rebuildable index; the filesystem is the source of truth.
- **Test coverage:** `test_backlog.py` (69 functions) — the most thoroughly tested package in the codebase.
- **Mixed error patterns:** `add_item.py` uses both `raise FileNotFoundError` (line 40) and `return {"error": ...}` (lines 62-74). `promote.py` uses `raise ValueError` throughout but checks `{"error": ...}` from downstream (line 187). This confirms the error handling duality.
- **PP-DRY:** `path_resolution_and_slug.py` is a dedicated utility — good DRY practice.
- **PP-ORTH:** Each operation is its own file — excellent orthogonality.
- **Descriptive file names:** `path_resolution_and_slug.py`, `close_item.py` — filesystem-as-DB naming pattern followed well.

---

## Filled Checklist

### CS Foundations — Security (CS-SEC, all 5 rules)

| Rule | Status | Evidence |
|------|--------|----------|
| SEC-1 | **YES** | Two trust boundaries clearly defined: (1) CLI — trusted local, env-var identity (MINION_CLASS + MINION_AGENT_NAME), (2) Network API — untrusted, Bearer token. auth.py owns CLI boundary; network/server.py + network/auth.py own network boundary. |
| SEC-2 | **YES** | CLI: MINION_CLASS env var + MINION_AGENT_NAME → coordinator DB lookup for scope. Network: MINION_CLUSTER_TOKEN Bearer token in Authorization header. Both paths verified in auth.py and network/server.py. |
| SEC-3 | **YES** | CLI: `require_class(*allowed)` decorator checks class ∈ allowed set. `require_scope(command_path)` checks scope_mode vs SCOPE_RESTRICTIONS dict. 7 classes (lead, coder, builder, oracle, recon, planner, auditor). 10 capabilities (manage, code, build, review, test, investigate, plan, monitor, memory, engineer). TOOL_CATALOG maps 60+ commands to allowed class sets. Network: binary token check (has valid token or not). |
| SEC-4 | **YES** | Secrets in env vars only: `MINION_CLUSTER_TOKEN`, `MINION_CLASS`, `MINION_AGENT_NAME`. No hardcoded tokens/passwords/secrets in source code. Token values are empty string defaults (dev mode = no auth), which is appropriate for a local-first tool. |
| SEC-5 | **NO** | **CLI boundary:** `filesafety.py` normalizes paths with `os.path.abspath()` — good. But no input length validation, no path traversal prevention beyond normalization. **Network boundary:** Handlers use `body.get()` with no validation, no length limits, no sanitization. 25+ `body.get`/`json.loads` calls in handler files with zero schema validation. `intel/read_doc.py` reads files without size limit. (Owned by AU-05 for network; AU-10 notes cross-cutting gap.) |

### Clean Architecture (subset)

| Rule | Status | Evidence |
|------|--------|----------|
| CA-COMP-1 | **YES** | No cycles in dependency graph. auth.py → tasks (lazy import via `_agent_classes()`) breaks potential cycle. Cross-cutting files (defaults.py, fs.py, output.py) are leaf dependencies — nothing imports them that they import back. Verified by tracing imports of all 7 cross-cutting files. |
| CA-COMP-2 | **YES** | Cross-cutting files are highly stable (most-depended-upon, rarely changing): defaults.py (imported by db, crew, daemon, network), fs.py (imported by monitoring, comms, warroom), output.py (imported by all CLI commands). Fan-in >> Fan-out for all cross-cutting modules. |
| CA-DEP-1 | **YES** | Dependencies point inward: cli/ → business logic → db/. Cross-cutting utilities (defaults.py, fs.py, output.py) sit at the bottom layer — they import only stdlib and db. No outward dependency violations in cross-cutting files. |

### Pragmatic Programmer (subset — CRITICAL for cross-cutting)

| Rule | Status | Evidence |
|------|--------|----------|
| PP-DRY-1 | **NO** | **Logging:** 3 competing patterns (logging.getLogger: 3 files, print: 27+ files, click.echo: 10+ files) — no single authoritative representation. **Config:** defaults.py is canonical for paths, but 5 network env vars have no constants. **Error handling:** dict-return AND raise — two patterns, no taxonomy. **Auth:** _check_token duplicated in server.py vs network/auth.py. |
| PP-DRY-2 | **NO** | **Config loading duplicated:** daemon/config.py `load_config()` (135 lines) is nearly identical to crew/config.py `load_config()` (182 lines). They share dataclasses (daemon imports AgentConfig/SwarmConfig from crew) but duplicate the entire YAML parsing and agent construction logic. Approximately 80% code overlap. The daemon version lacks `skills` and `scope` fields; crew version has them. A shared `_parse_agents()` helper would eliminate ~100 lines of duplication. |
| PP-DRY-3 | **YES** | Reuse is easy: `from minion.db import get_db`, `from minion.defaults import resolve_db_path`, `from minion.output import output`. The utility functions are well-factored and straightforward to import. |
| PP-ORTH-1 | **YES** | Cross-cutting modules are self-contained: defaults.py (paths only), fs.py (file I/O only), output.py (CLI output only), auth.py (authorization only), triggers.py (trigger state only), filesafety.py (file claims only), monitoring.py (status queries only). Each has a single purpose. |
| PP-ORTH-2 | **NO** | 13 direct os.environ reads across 10 files bypass defaults.py for env vars that should have canonical constants. See Config analysis table. Global mutable state (os.environ) accessed in scattered locations rather than through the designated accessor module. |
| PP-ORTH-3 | **YES** | Changes to cross-cutting modules are localized. Adding a new env var to defaults.py doesn't ripple. Changing auth class list only touches auth.py. Provider changes only touch providers/. |
| PP-DECOUPLE-5 | **NO** | Configuration partially externalized: defaults.py handles path config well, but 5 network env vars (MINION_CLUSTER_TOKEN, MINION_NETWORK_URL, MINION_NETWORK_INSECURE, MINION_COMPAT_PROJECT, MINION_TS_DAEMON_DIR) are read directly from os.environ in multiple locations with no central definition or documentation. |
| PP-CONTRACT-1 | **NO** | No preconditions/postconditions/invariants defined on any cross-cutting function. daemon/contracts.py exists but covers only daemon agent contracts, not general DBC. Zero `assert` statements in cross-cutting files for invariant checking. Only 5 total assert statements in entire production codebase (requirements/crud.py:1, daemon/runner/_execution.py:1, tasks/engine.py:1). |
| PP-CONTRACT-3 | **NO** | Zero assertions for "impossible" conditions in cross-cutting code. No invariant checking. See CONTRACT-1. |
| PP-APPROACH-3 | **NO** | Broken windows: (1) 3 logging patterns coexist — print() in 27+ files not migrated to structured logging. (2) network/auth.py created to centralize token check but server.py still has inline duplicate. (3) cli/backlog_cmds.py bypasses output.py funnel. These are not catastrophic but represent accumulating tech debt. |

### Implementation Coding Core (subset)

| Rule | Status | Evidence |
|------|--------|----------|
| IC-HDR-1 | **NO** | Of 7 cross-cutting files: zero have formal PURPOSE header. All have module-level docstrings (e.g., `"""Class-based authorization, constants, and gate functions."""`). Only exception: network/auth.py has a full formal header (Purpose/Rationale/Responsibility/Organization) — the ONE file in cross-cutting scope with proper headers. Systemic finding (reference AU-00 SF-01). |
| IC-HDR-2 | **NO** | Zero files have formal RESPONSIBILITIES header (except network/auth.py). See IC-HDR-1. |
| IC-HDR-3 | **NO** | Zero files have formal NOT RESPONSIBLE FOR header. |
| IC-HDR-4 | **NO** | Zero files have formal DEPENDENCIES header (except network/auth.py which lists "Implementation order: 1st (no dependencies)"). |
| IC-HDR-5 | **YES** | Docstring headers are persistent — no evidence of removal. PSEUDO comments preserved in auth.py (get_agent_scope), network/auth.py, and network/server.py. |
| IC-SCALE-2 | **NO** | No timeouts on external calls in cross-cutting scope. `fs.read_content_file()` reads without size limit. `intel/read_doc.py` reads entire file to memory with no size bound. Network calls in `network/client.py` use `urllib.request.urlopen` without explicit timeout parameter. |
| IC-SCALE-3 | **NO** | `fs.read_content_file()` reads entire file in one shot — no streaming, no size limit. `intel/read_doc.py` does `fh.read()` on full file. Low risk for current usage (message files <10KB) but no defensive bounds. |

---

## Findings

| # | Rule(s) | Severity | Affected Files | Description | Remediation |
|---|---------|----------|----------------|-------------|-------------|
| F001 | PP-DRY-1, CS-ERR-5, PP-APPROACH-3 | **Critical** | 40+ files | **3 competing logging patterns, no canonical strategy.** logging.getLogger (3 files, no handler config), print (27+ files), click.echo (10+ files). No structured logging, no log levels in print() calls, no centralized config. Highest blast radius — affects debugging, operations, and agent observability across entire codebase. | Choose canonical pattern. Recommend: `logging.getLogger(__name__)` for library code, `click.echo` for CLI output only. Add `logging.basicConfig()` in cli/main.py and daemon entrypoint. Migrate print() → logging with appropriate levels. |
| F002 | PP-DRY-1, CS-ERR-1 | **Major** | 25+ files | **Two competing error patterns with no taxonomy.** Dict-return `{"error": ...}` for business logic, `raise` stdlib for config/loaders. No custom exception hierarchy. output.py convention (`if "error" in data`) is the only contract — not type-enforced. Some files (backlog/promote.py, backlog/add_item.py) mix both patterns. | Document the convention: dict-return for CLI-consumed functions, raise for internal validation. Consider a `MinionError` base exception for raises. Add type annotation (e.g., `Result = TypedDict("Result", ...)`) for dict-return pattern. |
| F003 | PP-DRY-2 | **Major** | daemon/config.py, crew/config.py | **Config load_config() duplicated ~80%.** Both files parse YAML, validate structure, construct AgentConfig instances with nearly identical logic. daemon/config.py already imports dataclasses from crew/config.py but duplicates the parsing. ~100 lines of redundant code. | Extract shared `_parse_agents(raw, cfg_path) -> Dict[str, AgentConfig]` helper into crew/config.py. daemon/config.py calls it, adding daemon-specific fields. |
| F004 | PP-DECOUPLE-5, PP-ORTH-2 | **Moderate** | 10 files | **5 network env vars bypass defaults.py.** MINION_CLUSTER_TOKEN, MINION_NETWORK_URL, MINION_NETWORK_INSECURE, MINION_COMPAT_PROJECT, MINION_TS_DAEMON_DIR read directly from os.environ in network/server.py, network/client.py, api/daemon.py, crew/daemon.py, cli/api_cmds.py, network/handlers/compat.py. | Add `ENV_CLUSTER_TOKEN`, `ENV_NETWORK_URL`, `ENV_NETWORK_INSECURE`, `ENV_COMPAT_PROJECT`, `ENV_TS_DAEMON_DIR` constants to defaults.py. Replace direct os.environ.get() calls with defaults constants. |
| F005 | PP-DRY-1 | **Minor** | network/server.py, network/auth.py | **_check_token duplicated.** server.py:37-42 defines `_check_token()`. network/auth.py:18-34 defines identical `check_token()` + AuthMixin. network/auth.py was scaffolded as the replacement but server.py wasn't updated. | Replace `_check_token` in server.py with `from minion.network.auth import check_token`. Optionally make _Handler inherit AuthMixin. |
| F006 | PP-CONTRACT-1, PP-CONTRACT-3 | **Moderate** | All cross-cutting files | **No contracts or assertions.** Zero preconditions/postconditions/invariants defined on cross-cutting functions. Only 5 assert statements in entire production codebase. No defensive invariant checking. | Add assertions for impossible conditions (e.g., `assert conn is not None` after get_db()). Add docstring contracts for critical functions (e.g., `claim_file: precondition — agent_name is registered`). |
| F007 | IC-SCALE-2, IC-SCALE-3 | **Moderate** | fs.py, intel/read_doc.py | **Unbounded file reads.** `read_content_file()` and `read_doc()` read entire files without size limits. Low risk at current scale (message files <10KB) but no defensive bounds. | Add optional `max_bytes` parameter to `read_content_file()`. Add size check in `read_doc()` before full read. |
| F008 | PP-APPROACH-3 | **Minor** | cli/backlog_cmds.py | **CLI output funnel bypassed.** backlog_cmds.py uses `click.echo(json.dumps(...))` directly (30+ occurrences) instead of routing through output.py. This means --human/--compact flags don't work for backlog commands. | Refactor backlog_cmds.py to use `output(data, human, compact)` from output.py. |
| F009 | — | **Info** | — | **No formal pattern registry.** De facto patterns for logging, error handling, config, auth, output, and DB access are undocumented tribal knowledge. Agents have no reference for which pattern to use in new code. | Create `.planning/patterns.md` documenting each cross-cutting pattern, when to use it, and examples. |
| F010 | CS-ERR-2 | **Moderate** | All cross-cutting files | **103 bare `except Exception` blocks across 43 files.** Some are appropriate (daemon resilience, monitoring.py corruption handling). Others swallow useful errors: monitoring.py lines 312-313 (`except Exception: pass` for war plan and intel count). | Audit each `except Exception` — narrow catches where possible. At minimum, log the swallowed exception even in resilience paths. |

---

## Strengths

1. **defaults.py is well-designed** — path resolution logic (walk-up for DB, env cascade) is correct and used consistently for core paths. The resolver pattern is clean.

2. **output.py single funnel** — JSON/human/compact modes from one function. Error handling via `if "error" in data:` → `sys.exit(1)` is a pragmatic convention that works for CLI tools.

3. **Auth model is intentionally two-tier** — CLI (class+scope env-based) and network (bearer token) are separate concerns with separate modules. The class/capability/scope hierarchy in auth.py is well-thought-out with 7 classes, 10 capabilities, and scope-based narrowing.

4. **fs.py atomic writes** — `atomic_write_file()` using temp+rename is the correct pattern for crash-safe file writes. Used consistently across the codebase.

5. **filesafety.py waitlist** — the file claim system with automatic waitlisting for contended files is a pragmatic solution for multi-agent file access.

6. **Backlog package is exemplary** — filesystem-as-DB pattern done right (`.work/backlog/<type>/<slug>/`), rebuildable DB index, 69 test functions, descriptive file names, clean separation of operations.

7. **Requirements package is well-tested** — 26 test functions, clean API surface, proper validation via raise ValueError.

8. **network/auth.py scaffold exists** — formal headers (PURPOSE/RESPONSIBILITIES/NOT RESPONSIBLE FOR), PSEUDO comments, ready for integration. This is the one file in cross-cutting scope that follows the IC-HDR mandated format. It demonstrates the target state for all files.

9. **No circular dependencies** — auth.py's lazy import (`_agent_classes()`) correctly breaks the auth ↔ tasks ↔ comms cycle. All cross-cutting files are stable leaf dependencies.

10. **TOOL_CATALOG is comprehensive** — 60+ commands mapped to allowed class sets in one authoritative location. Easy to audit, easy to extend.
