# Broad Sweep Triage — v1

**Auditor:** AU-00 (Broad Sweep)
**Date:** 2026-03-09
**Codebase:** minion-factory (`src/minion/` + `tests/`)
**Stats:** 37 packages, 181 Python source files, 20 test files, 224 test functions

---

## Summary

- Rules scanned: 194
- PASS: 80
- FAIL: 72
- NEEDS-DEEP-DIVE: 42

---

## Triage by Skill

### CS Foundations (37 rules)

| Rule | Status | Evidence | Affected Domains |
|------|--------|----------|------------------|
| SEP-1 | PASS | Same model (no CQRS), appropriate for scale — tasks/query_task.py reads, tasks/create_task.py writes | All |
| SEP-2 | PASS | CLI mutations return created object as JSON — pragmatic for agent consumers | All |
| SEP-3 | PASS | Clear layering: policy (tasks/, auth.py), detail (db/, network/, providers/), glue (cli/, crew/) | All |
| SEP-4 | PASS | 37 packages with clear bounded contexts, no circular imports | All |
| SEP-5 | PASS | Two public surfaces (CLI + HTTP API); internal `__init__.py` re-exports exist but not all control exports | D5, D7 |
| DATA-1 | PASS | Clear ownership: db/ owns schema, tasks/ owns flow, comms/ owns messaging; exception: daemon/config.py re-implements crew/config.py parsing | D6 |
| DATA-2 | PASS | Current-state snapshot in SQLite; no event sourcing — appropriate for scale | All |
| DATA-3 | PASS | SQLite + filesystem — justified for local-first tool | All |
| DATA-4 | PASS | Schema-on-write; 14 tables with explicit CREATE TABLE; JSON columns for flex sub-docs | All |
| DATA-5 | FAIL | No archival, no deletion/cleanup, no TTL on messages | D3, D4, D6 |
| DATA-6 | PASS | Derived data (rollups, war plans, dashboards) computed on-read — appropriate | D4, D8 |
| COMM-1 | PASS | Primarily sync request/response; daemon polling is sync; one async pattern (filesystem watcher) | All |
| COMM-2 | PASS | External integrations documented: provider CLIs, tmux, network peers, filesystem | D6, D7 |
| COMM-3 | FAIL | No formal event taxonomy; daemon triggers are function calls, not named/versioned events | D6 |
| COMM-4 | PASS | Two API styles: Click CLI (noun-verb) + REST-like HTTP with custom router | All |
| COMM-5 | PASS | JSON everywhere for structured data; YAML for config; markdown for prompts | All |
| CONSIST-1 | PASS | Strong consistency within each SQLite DB; per-aggregate across 3 DBs | All |
| CONSIST-2 | FAIL | Some business operations lack explicit transactions (task creation, agent registration); only 2 files use `with conn:` | D3, D4, D6 |
| CONSIST-3 | PASS | WAL mode + threading.Lock for server writes; adequate for scale | D6, D7 |
| CONSIST-4 | FAIL | No explicit idempotency design; migrations have IF NOT EXISTS but core ops (send, create) are not idempotent | D3, D4, D6 |
| CONSIST-5 | PASS | Message ordering via SQLite rowid/timestamp; task flow ordering via gate validation | D3, D4 |
| SCALE-1 | PASS | Designed for 1-50 agents on single host — appropriate | All |
| SCALE-2 | PASS | Hot path: daemon polling loop (every few seconds), CLI invocations, task queries — all simple SQLite reads | D6 |
| SCALE-3 | PASS | Minimal caching; no explicit cache needed at this scale | All |
| SCALE-4 | FAIL | No Big-O documentation anywhere | D4, D6 |
| SCALE-5 | FAIL | No resource bounds: no connection pooling, no disk quota, no memory limits on daemon, unbounded file reads in intel/read_doc.py | D6, D8 |
| SEC-1 | PASS | Two trust boundaries: CLI (trusted local) and network API (untrusted, bearer token) | D7 |
| SEC-2 | PASS | CLI uses MINION_CLASS env + MINION_AGENT_NAME; network uses bearer token | D7 |
| SEC-3 | PASS | require_class/require_scope decorators in auth.py; network is binary (has token or not) | D7 |
| SEC-4 | PASS | Secrets in env vars (MINION_CLUSTER_TOKEN); no secrets in code; adequate for local/dev | D7 |
| SEC-5 | FAIL | Network API: manual body.get() with no validation, no input length limits, no sanitization; 25 body.get/json.loads in handlers | D7 |
| ERR-1 | FAIL | Two competing patterns: dict-return `{"error":...}` for CLI/tasks, raise stdlib exceptions for config/loaders; no custom exception hierarchy | All |
| ERR-2 | FAIL | No formal retry strategy; daemon retries implicitly (poll loop); network client has no retry/backoff; 30+ bare `except Exception` blocks | D6, D7 |
| ERR-3 | PASS | Daemon designed for resilience (broad except, continue); CLI fails fast; network returns error JSON | D6, D7 |
| ERR-4 | PASS | Mixed by design: CLI fail-fast, daemon graceful degradation, network per-request fail | All |
| ERR-5 | FAIL | 3 logging patterns (logging.getLogger: 3 files, print: 23 files, click.echo: 9 files = 102 total occurrences); no centralized config, no structured logs except 1 line in server.py | All |
| **Subtotal** | **PASS: 22, FAIL: 10, NDD: 0** | | |

---

### Clean Architecture (25 rules)

| Rule | Status | Evidence | Affected Domains |
|------|--------|----------|------------------|
| DEP-1 | PASS | Dependencies point inward: cli/ → business logic → db/; no outward violations observed in import scan | All |
| DEP-2 | NDD | No formal "entity" layer; closest are Row objects from SQLite — these import sqlite3 (stdlib, acceptable) but not frameworks | D3, D4 |
| DEP-3 | NDD | No formal "use case" layer; business logic in tasks/, comms/, crew/ depends on db.get_db() directly — not through ports/interfaces | All |
| DEP-4 | PASS | CLI commands convert between Click params and business logic; network handlers convert HTTP to/from business logic | D1, D7 |
| DEP-5 | PASS | Provider abstraction (BaseProvider ABC) with DIP for provider CLIs; only 1 ABC in entire codebase | D6 |
| DEP-6 | PASS | cli/main.py is the dirty "main" component — wiring, config loading, Click group setup | D1 |
| SOLID-1 | PASS | Packages grouped by domain/actor: tasks/, comms/, crew/, intel/, backlog/ — each changes for different reasons | All |
| SOLID-2 | PASS | Detail changes (e.g., new provider) don't force policy changes — provider registry is a dict | D6 |
| SOLID-3 | PASS | BaseProvider implementations interchangeable; 4 providers (claude, codex, gemini, opencode) | D6 |
| SOLID-4 | PASS | No observed transitive dependencies on unused modules; packages import only what they need | All |
| SOLID-5 | NDD | Only 1 ABC (BaseProvider); rest of codebase uses concrete imports — DIP not widely applied but may be fine for this scale | All |
| COMP-1 | PASS | No cycles in dependency graph; auth→tasks lazy import breaks potential cycle | All |
| COMP-2 | PASS | Dependencies point toward stability: db/ is most stable (most depended-on), cli/ is least stable (most dependers) | All |
| COMP-3 | NDD | Stable components (db/) are not abstract — concrete SQLite code; acceptable for non-framework project | D3 |
| COMP-4 | PASS | Classes that change together are colocated: tasks/ has db.py + create_task.py + query_task.py + gates.py | D4 |
| COMP-5 | PASS | Classes used together are colocated: crew/config.py + crew/spawn.py + crew/lifecycle.py | D6 |
| BOUND-1 | PASS | Boundaries at package level; network/handlers/ boundary separates HTTP from business logic | All |
| BOUND-2 | PASS | Partial boundaries (facade pattern) — appropriate cost/complexity for a CLI tool | All |
| BOUND-3 | NDD | Data crossing boundaries: dict objects (not formal DTOs) cross between CLI → business logic → db; functional but fragile | All |
| SCRM-1 | PASS | Top-level dirs: tasks/, comms/, crew/, intel/, backlog/ — communicate use cases, not framework (not "controllers/models/views") | All |
| SCRM-2 | PASS | A stranger can tell the domain from tree output: "multi-agent coordination framework" is evident | All |
| TEST-1 | PASS | Tests verify behavior (test_task_done, test_skip_stage), not implementation details | D4 |
| TEST-2 | FAIL | Tests structured by type (flat test_*.py files), not by use case — no tests/tasks/, tests/comms/ directories | All |
| TEST-3 | NDD | No explicit testing API; tests use the same functions as production code | All |
| TEST-4 | NDD | No explicit humble object pattern; network server handler is relatively thin but testable logic not separated | D7 |
| **Subtotal** | **PASS: 16, FAIL: 1, NDD: 8** | | |

---

### Pragmatic Programmer (33 rules)

| Rule | Status | Evidence | Affected Domains |
|------|--------|----------|------------------|
| DRY-1 | FAIL | Config duplication: daemon/config.py re-implements crew/config.py YAML parsing; auth logic partially duplicated between auth.py and network/auth.py | D6, D7 |
| DRY-2 | NDD | Potential inter-developer duplication in CLI handlers — each *_cmds.py repeats similar Click boilerplate patterns | D1 |
| DRY-3 | PASS | Reuse is easy: `from minion.db import get_db` is consistent; output.py is a single funnel; defaults.py centralizes paths | All |
| ORTH-1 | PASS | Components are self-contained: each package has clear single purpose; 37 packages, minimal cross-concerns | All |
| ORTH-2 | FAIL | 29 direct os.environ reads across 16 files (despite defaults.py existing as canonical source) — global state scattered | All |
| ORTH-3 | PASS | Module changes are generally localized; adding new provider only touches providers/ | All |
| DECOUPLE-1 | PASS | No significant train wrecks; 42 chained `.get().get()` occurrences across 27 files but mostly dict access, not method chains | All |
| DECOUPLE-2 | NDD | Tell-Don't-Ask: business logic generally follows this but CLI handlers query then act (acceptable for CLI pattern) | D1 |
| DECOUPLE-3 | PASS | Law of Demeter mostly respected; functions operate on immediate arguments | All |
| DECOUPLE-4 | PASS | Only 1 inheritance hierarchy (BaseProvider → 4 providers); rest uses composition/delegation | All |
| DECOUPLE-5 | FAIL | 29 os.environ reads across 16 files vs defaults.py canonical; config not fully externalized through one path | All |
| CONTRACT-1 | FAIL | No preconditions/postconditions/invariants defined; daemon/contracts.py exists but covers only daemon agent contracts, not general DBC | D6 |
| CONTRACT-2 | PASS | CLI crashes early (sys.exit(1) on error); daemon continues but logs | All |
| CONTRACT-3 | FAIL | No assertions for impossible conditions; zero `assert` statements in production code for invariant checking | All |
| CONTRACT-4 | PASS | Resources generally cleaned up: get_db() per-operation, subprocess calls managed | All |
| CRAFT-1 | PASS | Code is intentional — docstrings explain why on 95% of files; PSEUDO comments in router.py show deliberate design | All |
| CRAFT-2 | FAIL | No Big-O documentation; DAG operations complexity not analyzed | D4, D6 |
| CRAFT-3 | NDD | Refactoring status unclear from surface scan; db/ was recently decomposed (good sign) | All |
| CRAFT-4 | FAIL | Tests not written first — 17 packages have zero tests; test coverage concentrated in backlog/tasks/requirements | All |
| CRAFT-5 | PASS | Names reveal intent; descriptive file names (flow_gates_and_validation.py, path_resolution_and_slug.py) | All |
| CRAFT-6 | PASS | Small steps: migrations v1-v13, incremental development evident | All |
| DELIVER-1 | PASS | Version control drives builds; pyproject.toml + setup.py; `uv run pytest` for testing | All |
| DELIVER-2 | NDD | No CI/CD config observed in scan; manual procedures possible | All |
| DELIVER-3 | PASS | Tests must pass before merge (implied by project conventions) | All |
| DELIVER-4 | NDD | Bug-then-test protocol not observable from surface scan | All |
| DELIVER-5 | NDD | State coverage vs code coverage not determinable from surface scan | All |
| REQ-1 | PASS | CLAUDE.md documents philosophy and user-facing requirements iteratively | All |
| REQ-2 | PASS | Short iterations evident: 13 migration versions, incremental feature additions | All |
| REQ-3 | FAIL | Business rules partially hardcoded: DAG stages in Python, flow types embedded in code; should be metadata/config | D4 |
| REQ-4 | PASS | Project glossary exists (CLAUDE.md Dev Reference table); agent class/capability vocabulary consistent | All |
| APPROACH-1 | PASS | Tracer bullet approach evident: thin end-to-end from CLI to DB working early | All |
| APPROACH-2 | PASS | Mission YAML templates serve as prototyping system | All |
| APPROACH-3 | FAIL | Broken windows: 3 logging patterns coexist; print() in 23 files not cleaned up | All |
| APPROACH-4 | PASS | Decisions kept reversible: provider abstraction, config externalization, modular packages | All |
| APPROACH-5 | PASS | No over-engineering; features built as needed, not speculatively | All |
| **Subtotal** | **PASS: 19, FAIL: 8, NDD: 6** | | |

---

### Implementation Coding Core (24 rules)

| Rule | Status | Evidence | Affected Domains |
|------|--------|----------|------------------|
| LAY-1 | PASS | Layer 1 (structure) complete — all 37 packages stubbed, file structure exists | All |
| LAY-2 | FAIL | Layer 2 (intent headers): zero formal PURPOSE/RESPONSIBILITIES/NOT RESPONSIBLE headers in mandated format; 95% docstring coverage instead | All |
| LAY-3 | PASS | Layer 3 (signatures): functions have docstrings, type hints used in most files | All |
| LAY-4 | NDD | Layer commits not observable from surface scan (would need git log analysis) | All |
| LAY-5 | NDD | Layer review gates not observable from surface scan | All |
| LAY-6 | NDD | One-function-at-a-time discipline not observable from surface scan | All |
| HDR-1 | FAIL | Zero files have formal PURPOSE header in mandated format; module docstrings used instead | All |
| HDR-2 | FAIL | Zero files have formal RESPONSIBILITIES header; some docstrings describe responsibility informally | All |
| HDR-3 | FAIL | Zero files have formal NOT RESPONSIBLE FOR header | All |
| HDR-4 | FAIL | Zero files have formal DEPENDENCIES header (except network/router.py which has a partial scaffold) | All |
| HDR-5 | PASS | Docstring headers are persistent — no evidence of removal; PSEUDO comments preserved in router.py | All |
| IC-SCALE-1 | FAIL | No "what happens at 10x/100x/1000x" analysis documented for data structures | D4, D6 |
| IC-SCALE-2 | FAIL | No timeouts on external calls: network/client.py urllib calls, subprocess calls in providers lack explicit timeouts | D6, D7 |
| IC-SCALE-3 | FAIL | intel/read_doc.py reads files without size limits; no streaming/limiting for file I/O | D5 |
| IC-SCALE-4 | FAIL | Assumptions not documented in code comments (except a few PSEUDO comments in router.py) | All |
| IC-DATA-1 | FAIL | No defined schemas for network API request/response; handlers use manual body.get() | D7 |
| IC-DATA-2 | FAIL | No runtime schema validation — body parsed directly from JSON without validation | D7 |
| IC-DATA-3 | FAIL | No validation error messages with expected vs received | D7 |
| IC-DATA-4 | FAIL | No central schema definitions for API contracts | D7 |
| IC-DATA-5 | FAIL | No integration tests verifying schema matches actual API (test_network_api_route_integrity.py tests routes exist, not payloads) | D7 |
| VER-1 | PASS | Build passes (`uv run pytest` confirmed in project conventions) | All |
| VER-2 | PASS | All imports present and correct (test_imports.py exists to verify) | All |
| VER-3 | PASS | Tests pass before merge | All |
| VER-4 | PASS | Build/test discipline evident from project conventions | All |
| **Subtotal** | **PASS: 8, FAIL: 14, NDD: 2** | | |

---

### Test-Driven Development (19 rules)

| Rule | Status | Evidence | Affected Domains |
|------|--------|----------|------------------|
| CYC-1 | FAIL | Tests written after implementation — 17 of 37 packages have zero tests | All |
| CYC-2 | NDD | RED phase confirmation not observable | All |
| CYC-3 | NDD | Minimum code discipline not observable | All |
| CYC-4 | NDD | Refactoring discipline not observable | All |
| CYC-5 | NDD | One-test-at-a-time not observable | All |
| CYC-6 | PASS | Tests run after changes (per project conventions; `uv run pytest`) | All |
| QUAL-1 | PASS | Tests verify behavior: test_task_done, test_skip_stage, test_backlog — all behavioral | All |
| QUAL-2 | PASS | Test names are descriptive: test_create_and_retrieve, test_skip_stage_blocked, etc. | All |
| QUAL-3 | PASS | AAA structure observed in test files (arrange setup DB, act call function, assert result) | All |
| QUAL-4 | PASS | No observed test duplication; 224 test functions with unique scenarios | All |
| QUAL-5 | PASS | Tests are fast (SQLite in-memory, no network calls in unit tests) | All |
| COV-1 | FAIL | Happy path coverage only for 10 of 27 packages; 17 packages with zero behavioral tests (auth, providers, intel, prompts, missions, daemon, lifecycle, monitoring, output, etc.) | All |
| COV-2 | FAIL | Edge case coverage sparse; backlog tests have most edge cases (69 functions); most packages have none | All |
| COV-3 | FAIL | Error case coverage minimal outside of backlog and tasks; no error path tests for network handlers, daemon, providers | D6, D7 |
| COV-4 | PASS | State change tests exist: test_register_agent_db, test_task_done, test_task_result | D3, D4 |
| BUG-1 | NDD | Bug-first-test protocol not observable from surface scan | All |
| BUG-2 | NDD | Bug confirmation not observable | All |
| BUG-3 | NDD | Fix verification not observable | All |
| BUG-4 | NDD | Full suite after fix not observable | All |
| **Subtotal** | **PASS: 7, FAIL: 4, NDD: 8** | | |

---

### AI-First CLI (19 rules)

| Rule | Status | Evidence | Affected Domains |
|------|--------|----------|------------------|
| CMD-1 | FAIL | Noun-verb pattern (`minion agent register`, `minion task create`), not verb-noun (`minion register agent`); consistent but inverted from skill expectation | D1 |
| CMD-2 | PASS | Max 2 subcommand levels observed (minion + group + command) | D1 |
| CMD-3 | PASS | Click provides both long and short flags (--human/-h, --compact/-C, --project-dir/-C) | D1 |
| CMD-4 | FAIL | Verb vocabulary is inconsistent: "register" vs "create" vs "add" vs "spawn" for similar create operations | D1 |
| OUT-1 | FAIL | JSON is the default output, not human-readable; inverted from skill expectation (CLI is agent-first, which is intentional but violates the rule) | D1 |
| OUT-2 | PASS | JSON is default; `--human` flag available for human-readable output | D1 |
| OUT-3 | PASS | `--compact` flag returns pipe-friendly output (output.py _format_compact) | D1 |
| OUT-4 | PASS | All three modes (JSON, human, compact) return same underlying data via output.py single funnel | D1 |
| DISC-1 | PASS | --help works at every level via Click's built-in help system | D1 |
| DISC-2 | NDD | Error messages include actionable hints — need to test specific error paths | D1 |
| DISC-3 | NDD | Unknown command suggestions — Click may do this but needs verification | D1 |
| CFG-1 | PASS | Precedence: flags > env (MINION_*) > project config (.work/) > defaults.py; documented in CLAUDE.md | D1 |
| CFG-2 | PASS | Environment variables use MINION_* prefix consistently (MINION_DB_PATH, MINION_CLASS, etc.) | D1 |
| CFG-3 | NDD | Config file locations documentation in --help not verified | D1 |
| AGENT-1 | PASS | Zero interactive prompts; fully agent-safe (confirmed in research findings) | D1 |
| AGENT-2 | PASS | Agent rules via CLAUDE.md, AGENTS.md, and system prompts at spawn time | D1 |
| AGENT-3 | PASS | Deterministic output: same input = same JSON output | D1 |
| AGENT-4 | NDD | Exit codes: sys.exit(1) on error observed in 7 files; need to verify 0/1/2 convention | D1 |
| AGENT-5 | FAIL | No shell completions available | D1 |
| **Subtotal** | **PASS: 10, FAIL: 4, NDD: 5** | | |

---

### AI-First API (37 rules — evaluated as aspirational per UF-001)

| Rule | Status | Evidence | Affected Domains |
|------|--------|----------|------------------|
| ROUTE-1 | FAIL | No verb-prefix routing; routes are resource-based (/projects/{name}/agents, /health, /spawn) | D7 |
| ROUTE-2 | FAIL | No prefix-based Content-Type; all responses are JSON | D7 |
| ROUTE-3 | FAIL | No per-prefix routers; single Router class with add_get/add_post; 8 handler modules register by domain not prefix | D7 |
| ROUTE-4 | FAIL | No /search or /read endpoints returning text/markdown | D7 |
| ROUTE-5 | FAIL | All endpoints return JSON but not via /list or /push prefixes | D7 |
| ROUTE-6 | FAIL | No /pull endpoint returning binary | D7 |
| CONF-1 | FAIL | No confidence-based response system | D7 |
| CONF-2 | FAIL | No confidence thresholds | D7 |
| CONF-3 | FAIL | No medium-confidence multi-option responses | D7 |
| CONF-4 | FAIL | No low-confidence fallback content | D7 |
| CONF-5 | NDD | Endpoints return useful data in one call but not confidence-aware | D7 |
| TOK-1 | FAIL | No documented token budgets | D7 |
| TOK-2 | FAIL | No response truncation/summarization | D7 |
| TOK-3 | FAIL | No smart truncation | D7 |
| TOK-4 | FAIL | No truncated-response pointers | D7 |
| TOK-5 | FAIL | No X-Token-Count/X-Token-Budget headers | D7 |
| TOK-6 | FAIL | No list item caps or description length limits | D7 |
| CLI-1 | FAIL | No GET /install/cli endpoint | D7 |
| CLI-2 | FAIL | No self-serving CLI generation | D7 |
| CLI-3 | FAIL | No baked-in API URL | D7 |
| CLI-4 | FAIL | No auto-generated CLI from routes | D7 |
| CLI-5 | FAIL | No version check against /health | D7 |
| CLI-6 | FAIL | No self-update mechanism | D7 |
| SPEC-1 | FAIL | No /openapi.json endpoint; stdlib http.server, not FastAPI | D7 |
| SPEC-2 | FAIL | No /docs Swagger UI | D7 |
| SPEC-3 | NDD | No ENDPOINTS dict; routes registered per-module via register(router) pattern | D7 |
| SPEC-4 | PASS | /health endpoint exists, returns status (registered in core handlers) | D7 |
| INFRA-1 | FAIL | No docker-compose.yml | D8 |
| INFRA-2 | FAIL | No Makefile with standard commands | D8 |
| INFRA-3 | FAIL | No .env.example | D8 |
| INFRA-4 | FAIL | Config not via pydantic-settings; uses os.environ directly | D8 |
| INFRA-5 | FAIL | No Docker configs | D8 |
| DOC-1 | PASS | README (CLAUDE.md) has install instructions and dev reference | All |
| DOC-2 | FAIL | No bootstrap authentication guide (bearer token setup undocumented for first-time users) | D7 |
| DOC-3 | PASS | First request examples via CLAUDE.md CLI examples | All |
| DOC-4 | FAIL | No link to interactive docs (none exist) | D7 |
| DOC-5 | PASS | Top workflows documented (agent lifecycle, polling protocol, crew management) | All |
| DOC-6 | NDD | Fresh session test not verified | All |
| PLAN-1 | NDD | Planning docs exist (.planning/v1/) but Assumptions sections not checked | All |
| PLAN-2 | PASS | Implementation roadmap exists (iterative decomposition DAG) | All |
| PLAN-3 | NDD | Phase gate enforcement not observable from surface scan | All |
| PLAN-4 | NDD | Design-implementation variance tracking not observed | All |
| **Subtotal** | **PASS: 5, FAIL: 26, NDD: 6** | | |

**Note:** API rules evaluated as aspirational per UF-001. The network API uses stdlib http.server, not FastAPI. Many FAIL ratings are expected gaps for a migration path, not current-state defects.

---

## Systemic Findings (report once, reference everywhere)

| # | Finding | Rules | Severity | All Domains? |
|---|---------|-------|----------|--------------|
| SF-01 | **No formal comment headers** — zero files use mandated PURPOSE/RESPONSIBILITIES/NOT RESPONSIBLE/DEPENDENCIES format; 95% use module-level docstrings instead | IC-HDR-1, IC-HDR-2, IC-HDR-3, IC-HDR-4 | Major | Yes |
| SF-02 | **Three competing logging patterns** — logging.getLogger (3 files), print() (23 files), click.echo (9 files); 102 total occurrences, no centralized strategy | CS-ERR-5, PP-APPROACH-3 | Critical | Yes |
| SF-03 | **Two competing error patterns** — dict-return `{"error":...}` for CLI/tasks and raise stdlib exceptions for config/loaders; no custom exception hierarchy, no failure taxonomy | CS-ERR-1, PP-CONTRACT-1 | Major | Yes |
| SF-04 | **17 packages with zero behavioral tests** — auth, providers, intel, prompts, missions, daemon (beyond contracts), lifecycle, monitoring, output, dashboard, filesafety, triggers, flow_bridge, polling, api, network (beyond route integrity) | TDD-CYC-1, TDD-COV-1, TDD-COV-2, TDD-COV-3 | Critical | Yes |
| SF-05 | **Config access scattered** — 29 direct os.environ reads across 16 files despite defaults.py existing as canonical source | PP-ORTH-2, PP-DECOUPLE-5 | Moderate | Yes |
| SF-06 | **No network input validation** — handlers use manual body.get() with no schema validation, no length limits, no expected-vs-received errors; 25 body.get/json.loads in handler files | CS-SEC-5, IC-DATA-1 through IC-DATA-5 | Major | D7 |
| SF-07 | **No timeouts on external calls** — network client urllib calls, subprocess provider calls lack explicit timeouts | IC-SCALE-2 | Moderate | D6, D7 |
| SF-08 | **Config parsing duplicated** — daemon/config.py re-implements YAML parsing that crew/config.py owns | PP-DRY-1, CS-DATA-1 | Moderate | D6 |
| SF-09 | **Network API is stdlib http.server** — entire ai-first-api skill (37 rules) is aspirational; no FastAPI, no OpenAPI, no Swagger, no verb-prefix routing | ROUTE-1 through ROUTE-6, SPEC-1 through SPEC-4, all CLI-*, all TOK-*, all CONF-* | Info (aspirational) | D7 |
| SF-10 | **No explicit transaction boundaries** — only 2 files use `with conn:`; most business operations don't wrap multi-step mutations in transactions | CS-CONSIST-2 | Moderate | D3, D4, D6 |
| SF-11 | **30+ bare except Exception blocks** — broad catch-all in daemon, polling, network handlers, db coordinator; some appropriate (daemon resilience), others swallow useful errors | CS-ERR-2, PP-CONTRACT-3 | Moderate | D6, D7 |

---

## Priority Ranking (for Pass 2 Deep Dives)

| Priority | Spec | Reason | Estimated Findings |
|----------|------|--------|--------------------|
| **1** | AU-02 (Logging/Observability) | SF-02: Critical — 3 competing patterns, no strategy, affects all domains; fixes unblock error handling audit | 15-20 |
| **2** | AU-03 (Error Handling) | SF-03: Major — two competing patterns, no taxonomy, affects every domain; must follow logging audit | 15-20 |
| **3** | AU-04 (Test Coverage) | SF-04: Critical — 17/37 packages untested; most rules require test existence to evaluate | 30-40 |
| **4** | AU-05 (Network API Security) | SF-06: Major — no input validation on untrusted boundary; security risk | 10-15 |
| **5** | AU-06 (Config & DRY) | SF-05, SF-08: Moderate — scattered os.environ, duplicated config parsing | 10-15 |
| **6** | AU-07 (Comment Headers) | SF-01: Major by count but mechanical fix — 181 files need headers; low complexity per file | 5 (systemic) |
| **7** | AU-08 (Transaction Safety) | SF-10: Moderate — only 2 explicit transactions; risk of partial writes | 5-10 |
| **8** | AU-09 (Scale & Timeouts) | SF-07: Moderate — missing timeouts, unbounded reads; low risk at current scale | 5-10 |
| **9** | AU-10 (Network API Aspirational) | SF-09: Info — stdlib http.server vs FastAPI migration path; 37 rules all aspirational | 5 (migration plan) |
| **10** | AU-01 (Clean Architecture) | 8 NDD items — need deeper inspection of dependency direction, boundary data shapes, DIP usage | 5-10 |

---

## Test Coverage Gap Map

| Package | Test File | Functions | Status |
|---------|-----------|-----------|--------|
| backlog | test_backlog.py | 69 | Well covered |
| tasks | test_task_done.py, test_task_result.py, test_lite_flow.py, test_skip_stage.py, test_dag_smoke.py, test_flow_type.py | 50 | Well covered |
| requirements | test_requirements.py, test_req_decompose_inline.py | 26 | Covered |
| cli | test_cli.py, test_entrypoint.py | 21 | Partial (surface only) |
| comms | test_register_agent_db.py, test_register_crew.py | 8 | Partial |
| crew | test_register_crew.py | 3 | Minimal |
| warroom | test_warroom.py | 6 | Covered |
| network | test_network_api_route_integrity.py | 8 | Route existence only |
| daemon | test_contracts.py | 14 | Contracts only |
| prompts | test_get_agent_prompt.py | 4 | Minimal |
| imports | test_imports.py | 17 | Import smoke only |
| auth | — | 0 | **ZERO** |
| providers | — | 0 | **ZERO** |
| intel | — | 0 | **ZERO** |
| missions | — | 0 | **ZERO** |
| lifecycle | — | 0 | **ZERO** |
| monitoring | — | 0 | **ZERO** |
| output | — | 0 | **ZERO** |
| dashboard | — | 0 | **ZERO** |
| filesafety | — | 0 | **ZERO** |
| triggers | — | 0 | **ZERO** |
| flow_bridge | — | 0 | **ZERO** |
| polling | — | 0 | **ZERO** |
| api | — | 0 | **ZERO** |
| db | — | 0 | **ZERO** (indirectly tested via others) |
| defaults | — | 0 | **ZERO** |
| fs | — | 0 | **ZERO** |

---

## Codebase Strengths (Preserve These)

1. **Clean dependency graph** — no circular imports, proper layering
2. **JSON-default CLI output** — correct for agent consumption, single funnel via output.py
3. **Non-interactive CLI** — zero prompts, fully agent-safe
4. **Descriptive package names** — filesystem-as-db pattern followed well
5. **95% docstring coverage** — not mandated format but documentation exists
6. **Auth model well-designed** — two tiers (local class+scope, network bearer) is intentional
7. **Database pattern consistent** — get_db(), WAL, Row factory everywhere
8. **Migration system works** — versioned v1-v13, idempotent, transactional
9. **Provider abstraction** — only ABC in codebase, properly used with DIP
10. **PSEUDO comments preserved** — router.py shows scaffolding discipline where applied
