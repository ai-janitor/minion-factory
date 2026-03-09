# AU-07 Intel + Providers Audit Results

**Auditor:** AU-07 (Intel + Providers Deep Dive)
**Date:** 2026-03-09
**Scope:** `src/minion/intel/` (13 files), `src/minion/providers/` (6 files)

---

## Intel Architecture

### Knowledge Management Model

The intel package implements a queryable knowledge layer over `.work/intel/` and project docs. It manages:

- **Document registry** — SQLite-backed index of markdown docs with slugs, tags, descriptions, and authorship
- **Document linking** — many-to-many links between intel docs and tasks/requirements via `intel_links` table
- **Frontmatter parsing** — YAML frontmatter in markdown files provides tags, linked_tasks, linked_reqs
- **War plan** — a single persistent markdown doc (`WAR_PLAN.md`) with lead-only write access
- **Search/suggest** — keyword-based relevance scoring across slug, tags, and description fields

### Document Lifecycle

1. **Register** — `add_doc()` inserts/updates a row in `intel_docs`, optionally scaffolds the file with frontmatter stub
2. **Bulk register** — `register_docs()` walks a directory, auto-derives slugs from paths, extracts tags from headings
3. **Reindex** — `reindex_intel()` walks `.work/intel/`, parses frontmatter, upserts into DB; non-destructive (no deletes)
4. **Link** — `link_doc()` creates entity links; `add_doc()` auto-links from frontmatter
5. **Query** — `list_docs()`, `find_docs()`, `get_doc()`, `for_task()`, `suggest()` all read-only
6. **Read** — `read_doc()` returns raw file content (or 10-line summary)
7. **No delete** — no `delete_doc()` function exists; reindex doesn't prune orphans

### Import Dependencies (Intel)

All intel modules depend only on:
- `minion.db` (get_db, now_iso, RUNTIME_DIR) — data layer, inward dependency
- `minion.fs` (atomic_write_file) — utility, peer dependency
- Standard library (os, json, re, sqlite3, logging, yaml)
- Internal `._frontmatter` — package-private helper

**No imports from cli/, daemon/, network/, providers/, or any outer layer.**

### Callers of Intel

- `cli/intel_cmds.py`, `cli/war_plan_cmds.py` — CLI adapter layer (correct: outer → inner)
- `tasks/create_task.py`, `tasks/define.py`, `tasks/pull_task.py` — business logic peers (acceptable: same tier)
- `polling.py`, `lifecycle.py`, `monitoring.py` — business logic peers
- `comms/register.py` — business logic peer

All callers are at the same tier or outer. No inward-violating imports observed.

---

## Provider Interface

### Protocol Definition

`cli_provider_protocol.py` defines `BaseProvider(ABC)` — a formal abstract base class with:

| Method/Property | Type | Description |
|-----------------|------|-------------|
| `__init__(agent_name, agent_cfg, use_poll)` | concrete | Stores config, initializes session_id |
| `build_command(prompt, use_resume)` | abstract | Returns CLI command list |
| `prompt_guardrails()` | abstract | Returns provider-specific guardrail text |
| `filter_log_line(line, error_log)` | virtual (default: pass-through) | Cleans verbose output |
| `supports_resume` | property (default: True) | Whether provider supports session resume |
| `resume_label` | property (default: "") | Human label for resume command |
| `_extract_error_summary(line, max_normal)` | static helper | Shared error extraction logic |

### Implementation Comparison

| Feature | Claude | Codex | Gemini | Opencode |
|---------|--------|-------|--------|----------|
| `build_command` | Yes | Yes | Yes | Yes |
| `prompt_guardrails` | Yes (empty) | Yes | Yes (extensive) | Yes |
| `filter_log_line` | Default | Override | Override | Default |
| `supports_resume` | Override (True) | Override (True) | Override (True) | Override (True) |
| `resume_label` | Override | Override | Override | Override |
| Error classification | No | `_classify_codex_error` | `_classify_gemini_error` | No |
| Error log append | No | `_append_error_log` | `_append_error_log` | No |
| Lines of code | 66 | 90 | 103 | 34 |

### Import Dependencies (Providers)

Provider modules depend only on:
- `.cli_provider_protocol` (BaseProvider) — package-internal
- Standard library (json, os, re, pathlib, typing, abc)

**No imports from minion.* at all** — providers are fully self-contained. Only the `__init__.py` registry is imported by callers.

### Callers of Providers

- `daemon/runner/__init__.py` — imports `get_provider()` (factory function)
- `daemon/runner/_polling.py`, `_hp.py`, `_prompts.py`, `_execution.py` — TYPE_CHECKING imports of `BaseProvider`

All callers go through the abstraction (`get_provider` or `BaseProvider` type), not concrete classes. DIP properly applied.

---

## Filled Checklist

### Clean Architecture

| Rule | Status | Evidence |
|------|--------|----------|
| CA-DEP-1 | **YES** | Intel imports only from `minion.db` and `minion.fs` (inward/peer). Providers import nothing outside their package. No imports from cli/, daemon/, network/. Verified via grep of all `from minion` imports. |
| CA-DEP-5 | **YES** | `BaseProvider(ABC)` defines formal interface in `cli_provider_protocol.py`. `get_provider()` factory in `__init__.py` returns `BaseProvider` type. Callers depend on the abstraction. Control flow (daemon calls provider) opposes dependency direction (provider defines interface). |
| CA-SOLID-1 | **YES** | Intel: 13 files, each with single responsibility (add, list, find, get, read, link, suggest, reindex, register, war_plan, frontmatter). Providers: each provider file handles one CLI tool. Changes to Gemini don't affect Claude. |
| CA-SOLID-3 | **YES** | All 4 providers implement identical interface (`build_command`, `prompt_guardrails`). `get_provider()` returns `BaseProvider` — callers don't know the concrete type. Swapping claude for gemini requires only config change, not code change. |
| CA-SOLID-5 | **YES** (providers) / **PARTIAL** (intel) | Providers: callers depend on `BaseProvider` abstraction. Intel: callers import concrete functions directly (`from minion.intel import add_doc`) — no interface/protocol for intel. Acceptable at this scale since intel functions are stable. |
| CA-COMP-1 | **YES** | No cycles. Intel → db (no reverse). Providers → nothing outside package. Callers → intel/providers (no reverse). Verified by import graph analysis. |
| CA-COMP-4 | **YES** | Intel files that change together are colocated: `add_doc` + `_frontmatter` + `link_doc` form the registration cluster. Provider files are colocated per-provider. |
| CA-COMP-5 | **YES** | Intel functions used together (list/find/get/read) are all in `intel/`. Provider implementations all in `providers/`. |
| CA-BOUND-3 | **YES** (intel) / **YES** (providers) | Intel functions return `dict[str, object]` — simple data structures, not entities. Providers return `List[str]` (command args) and `str` (guardrails). No entity objects cross boundaries. |

### Pragmatic Programmer

| Rule | Status | Evidence |
|------|--------|----------|
| PP-ORTH-1 | **YES** | Each provider is fully self-contained — ClaudeProvider knows nothing about CodexProvider. Each intel module operates independently. Adding a new provider or intel function doesn't affect existing ones. |
| PP-ORTH-3 | **YES** | Change to GeminiProvider (e.g., new flag) touches only `gemini.py`. Change to `read_doc.py` logic touches only that file. Verified: no cross-provider imports, no cross-intel-module coupling beyond `_frontmatter`. |
| PP-DRY-1 | **NO** | `_append_error_log()` is duplicated verbatim between `codex.py` (lines 78-89) and `gemini.py` (lines 92-103) — identical 12-line static method. Should be in `BaseProvider` or a shared utility. |
| PP-DRY-2 | **NO** | `_classify_codex_error()` and `_classify_gemini_error()` share structural pattern: try JSON parse → pattern match → fallback to `_extract_error_summary()`. The JSON error extraction logic is duplicated with minor field-name variations. Could be a template method in BaseProvider with provider-specific overrides. |
| PP-DECOUPLE-4 | **YES** | Single ABC hierarchy (`BaseProvider` → 4 providers). No deep inheritance. The ABC defines interface + shared helpers. Intel uses no inheritance at all — pure functions. |
| PP-CRAFT-5 | **YES** | Names reveal intent throughout: `read_doc`, `find_docs`, `intel_for_task`, `suggest`, `war_plan`, `build_command`, `prompt_guardrails`, `filter_log_line`, `_extract_error_summary`. Slug, tag, frontmatter vocabulary is consistent. |

### Implementation Coding Core

| Rule | Status | Evidence |
|------|--------|----------|
| IC-HDR-1 | **NO** | Zero files have formal PURPOSE header. All use module-level docstrings instead. Example: `read_doc.py` has `"""Read the content of a registered intel doc."""` — informal but present. Reference: SF-01 systemic finding. |
| IC-HDR-2 | **NO** | Zero files have formal RESPONSIBILITIES header. Docstrings describe responsibility informally. Reference: SF-01. |
| IC-HDR-3 | **NO** | Zero files have NOT RESPONSIBLE FOR header. Reference: SF-01. |
| IC-HDR-4 | **NO** | Zero files have DEPENDENCIES header. Reference: SF-01. |
| IC-HDR-5 | **YES** | Module-level docstrings are stable/permanent — no evidence of removal across the codebase history. |
| IC-SCALE-3 | **NO** | `read_doc.py` line 25: `content = fh.read()` — unbounded full-file read with no size limit. A 1GB intel doc would consume 1GB of memory. The `summary=True` flag truncates to 10 lines but only AFTER the full read. Additionally, `_frontmatter.py` line 29: `content = fh.read()` — same unbounded read for frontmatter parsing. `war_plan.py` lines 22-23 and 66: unbounded reads of WAR_PLAN.md. `register_docs.py` reads headings line-by-line (safe). |

---

## Findings

| # | Rule | Severity | Affected Files | Description | Remediation |
|---|------|----------|----------------|-------------|-------------|
| F-01 | PP-DRY-1 | Moderate | `codex.py:78-89`, `gemini.py:92-103` | `_append_error_log()` is copy-pasted verbatim (12 lines) between CodexProvider and GeminiProvider. Identical datetime import, identical mkdir+write+except pattern. | Move `_append_error_log()` to `BaseProvider` as a static method or standalone utility. |
| F-02 | PP-DRY-2 | Minor | `codex.py:57-76`, `gemini.py:61-89` | `_classify_codex_error()` and `_classify_gemini_error()` share structural pattern: JSON parse → regex fallback → `_extract_error_summary()`. The JSON extraction differs only in field names. | Extract a template method `_classify_provider_error()` in BaseProvider with hook for provider-specific JSON field names. Or pass a field-name config to a shared implementation. |
| F-03 | IC-SCALE-3 | Major | `read_doc.py:25`, `_frontmatter.py:29`, `war_plan.py:22,66` | Unbounded file reads — `fh.read()` with no size limit. A large intel doc would cause memory exhaustion. `read_doc.py` is the highest risk since it's user-triggered (CLI `minion intel read`). | Add `MAX_DOC_SIZE` constant (e.g., 10MB). Read up to limit, return truncation warning if exceeded. For `summary=True`, read line-by-line instead of full-read-then-truncate. |
| F-04 | IC-HDR-1 to IC-HDR-4 | Major (systemic) | All 19 files in intel/ and providers/ | No formal PURPOSE/RESPONSIBILITIES/NOT RESPONSIBLE/DEPENDENCIES headers. Module docstrings provide informal coverage. | Reference SF-01 from AU-00. Mechanical fix: add headers to all files. Low complexity per file but 19 files in scope. |
| F-05 | — | Minor | `intel/add_doc.py:77-86` | Bare `except Exception: pass` blocks swallow errors during auto-link insertion from frontmatter. If `intel_links` INSERT fails for non-integrity reasons (e.g., table missing), the error is silently dropped. | Change to `except sqlite3.IntegrityError: pass` (matching `link_doc.py` pattern) and let other exceptions propagate or log. |
| F-06 | — | Minor | `intel/register_docs.py:31,107` | Bare `except Exception: pass` in `_extract_tags_from_headings()` and `_first_heading()`. File read errors silently swallowed — acceptable for bulk ops but could hide permission errors. | Add logging at DEBUG level for failed file reads. |
| F-07 | — | Info | `intel/read_doc.py`, `intel/list_docs.py`, etc. | No delete/unregister operation for intel docs. `reindex_intel()` explicitly does NOT delete orphaned DB rows. Stale entries accumulate if files are removed from disk. | Consider adding `unregister_doc()` or a `--prune` flag to reindex. Low priority — matches CS-DATA-5 finding from AU-00. |
| F-08 | — | Info | `intel/suggest.py:37-39` | `suggest()` loads ALL intel_docs into memory for keyword scoring (`cursor.fetchall()`). At current scale (dozens of docs) this is fine; at 10,000+ docs it would be slow. No pagination. | Document scale assumption. Consider SQLite FTS5 if doc count grows significantly. |

---

## Strengths

1. **Clean dependency direction** — Intel depends only on db/ and fs/ (inward). Providers depend on nothing outside their package. Zero outward-violating imports. This is textbook Clean Architecture dependency rule compliance.

2. **Formal ABC with factory** — `BaseProvider(ABC)` is the only ABC in the entire codebase and it's well-designed: two abstract methods, sensible defaults for optional methods, shared utility in `_extract_error_summary()`. The `get_provider()` factory + `_REGISTRY` dict is clean DIP.

3. **Provider interchangeability** — All 4 providers implement identical interface. `get_provider("claude", ...)` and `get_provider("gemini", ...)` are fully interchangeable from the caller's perspective. Config-driven provider selection works without code changes.

4. **Intel as pure functions** — Every intel module exports one function with `dict[str, object]` return type. No classes, no state, no side effects beyond DB writes. Simple, testable, composable. The `dict` return pattern is consistent with the rest of the codebase.

5. **Consistent error handling** — Intel functions return `{"error": "..."}` for expected failures (doc not found, file missing) and let unexpected exceptions propagate. This matches the codebase convention.

6. **Frontmatter parsing is defensive** — `_parse_frontmatter()` never raises: catches OSError for file read, catches generic Exception for YAML parse, validates types before use, returns defaults for missing fields. Production-quality defensive coding.

7. **War plan access control** — `set_war_plan()` and `append_war_plan()` enforce lead-only access by checking agent_class in the DB. This is a proper authorization boundary.

8. **Lazy imports everywhere** — Callers use lazy imports (`from minion.intel import X` inside function bodies), preventing circular import issues and keeping startup fast.

9. **No global state** — Neither package uses `os.environ`, module-level mutable state, or singletons. All state flows through function parameters and DB queries. Clean orthogonality.

10. **Descriptive file names** — `add_doc.py`, `find_docs.py`, `for_task.py`, `link_doc.py`, `read_doc.py`, `register_docs.py`, `cli_provider_protocol.py` — filesystem-as-documentation is well-executed here.

---

## Summary

| Skill | Pass | Fail | N/A |
|-------|------|------|-----|
| Clean Architecture (9 rules) | 9 | 0 | 0 |
| Pragmatic Programmer (6 rules) | 4 | 2 | 0 |
| Implementation Coding Core (6 rules) | 1 | 5 | 0 |
| **Total (21 rules)** | **14** | **7** | **0** |

**Overall assessment:** Intel and providers are the best-architected packages in the codebase. Clean Architecture compliance is perfect — dependency direction, DIP, SRP, LSP all satisfied. The two DRY violations in providers are straightforward to fix (move shared code to BaseProvider). The IC-HDR failures are systemic (SF-01) and not specific to these packages. The unbounded file read in `read_doc.py` (F-03) is the most actionable finding — it's a real risk that's cheap to fix.
