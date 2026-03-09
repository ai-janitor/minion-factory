# AU-08 Prompts + Missions Audit Results

**Auditor:** AU-08 (Prompts + Missions Deep Dive)
**Date:** 2026-03-09
**Scope:** `src/minion/prompts/`, `src/minion/missions/`, `missions/`

---

## Prompt Inventory

### Python Loaders (.py files)

| File | Purpose | Thin/Fat |
|------|---------|----------|
| `prompts/__init__.py` | Package exports — 5 public builders | Thin (re-export only) |
| `prompts/_boot.py` | Load boot-sequence from contract or fallback | Thin (load + substitute) |
| `prompts/_history.py` | Build history block for post-compaction recovery | Thin (load + format) |
| `prompts/_inbox.py` | Format inbox messages and tasks for inline injection | Medium (format logic + fenix-down handling) |
| `prompts/_protocol.py` | Load protocol docs from filesystem or fallback | Thin (file read + join) |
| `prompts/_rules.py` | Load daemon rules + role prompts + capability prompts | Medium (orchestration of 3 sub-loaders) |
| `prompts/boot_prompt.py` | Compose full boot prompt from protocol+rules+boot | Thin (assembly) |
| `prompts/inbox_prompt.py` | Compose full inbox prompt from protocol+rules+inbox+history | Thin (assembly) |
| `prompts/system_prompt.py` | Merge crew-level system_prefix with agent system prompt | Thin (string concat) |
| `prompts/terminal_prompt.py` | Append poll instruction to terminal agent prompt | Thin (string append) |
| `prompts/watcher_prompt.py` | Compose watcher-mode prompt from protocol+rules+message | Thin (assembly) |
| `prompts/capabilities/__init__.py` | Load and merge prompt.md for capabilities | Thin (file read + join) |
| `prompts/roles/__init__.py` | Load prompt.md for a given role | Thin (single file read) |

### Capability Prompts (.md templates)

| File | Purpose | Template Variables? |
|------|---------|---------------------|
| `capabilities/build/prompt.md` | Build process rules (Makefile, targets) | No |
| `capabilities/code/prompt.md` | Coding rules (no try/except, file org) | No |
| `capabilities/engineer/prompt.md` | SDLC workflow, hardware awareness | No |
| `capabilities/investigate/prompt.md` | Silent failure detection rules | No |
| `capabilities/manage/prompt.md` | Task queue management, CLI commands | Yes — `{you}`, `{crew}`, `{name}` (but NOT template-rendered; literal text for agent to substitute) |
| `capabilities/memory/prompt.md` | Three-layer memory system (personal/role/crew) | Yes — `{you}`, `{your-class}` (same: literal placeholders for agent) |
| `capabilities/monitor/prompt.md` | Observe-and-report monitoring rules | No |
| `capabilities/plan/prompt.md` | Task decomposition and planning rules | No |
| `capabilities/review/prompt.md` | Code review correctness and edge cases | No |
| `capabilities/test/prompt.md` | Testing philosophy and test layers | No |

### Role Prompts (.md templates)

| File | Purpose | Template Variables? |
|------|---------|---------------------|
| `roles/auditor/prompt.md` | Audit rules + self-service chore block | Yes — `{you}` (literal placeholder) |
| `roles/builder/prompt.md` | Build rules + context protection + self-service | Yes — `{you}` |
| `roles/coder/prompt.md` | Coding rules + context protection + self-service | Yes — `{you}` |
| `roles/lead/prompt.md` | Coordination, task mgmt, command reference | Yes — `{you}`, `{name}`, `{crew}` |
| `roles/oracle/prompt.md` | Deep knowledge, cite file paths, intel write | Yes — `{you}` |
| `roles/planner/prompt.md` | Planning rules + self-service chore block | Yes — `{you}` |
| `roles/recon/prompt.md` | Recon rules + intel file routing + self-service | Yes — `{you}` |

---

## Mission Inventory

### Python Loaders (.py files)

| File | Purpose |
|------|---------|
| `missions/__init__.py` | Package exports — 5 public symbols |
| `missions/loader.py` | YAML loading, search paths, validation |
| `missions/resolver.py` | Greedy set-cover: capabilities -> minimum class slots |
| `missions/party.py` | Character matching: crew rosters -> party suggestions |
| `missions/spawn.py` | End-to-end: resolve + validate + build dynamic crew YAML + spawn |

### Mission Templates (.yaml files)

| File | Purpose | Capabilities Required |
|------|---------|----------------------|
| `missions/bd-research.yaml` | Business development research | manage, investigate, review, plan |
| `missions/bugfix.yaml` | Bug find/fix/test/review | manage, investigate, code, test, review |
| `missions/code-audit.yaml` | Codebase quality review | manage, review, investigate |
| `missions/competitive-analysis.yaml` | Competitor investigation | manage, investigate, plan |
| `missions/dependency-upgrade.yaml` | Dependency upgrade + test | manage, code, test, build, review |
| `missions/documentation.yaml` | Investigate + document | manage, investigate, review |
| `missions/incident-response.yaml` | Incident fix end-to-end | manage, investigate, code, test, build, review |
| `missions/migration.yaml` | Codebase/infra migration | manage, plan, code, test, build |
| `missions/new-feature.yaml` | Full feature lifecycle | manage, plan, code, test, build, review |
| `missions/prototype.yaml` | Rapid prototype | manage, code, build |
| `missions/security-review.yaml` | Security vulnerability scan | manage, investigate, review |

---

## Filled Checklist

### Implementation Coding Core (.py files only)

Per UF-002: IC-HDR rules apply only to .py files, not .md/.yaml templates.

| Rule | Status | Evidence |
|------|--------|----------|
| IC-HDR-1 | **NO** | Zero .py files in prompts/ or missions/ have formal PURPOSE header. All use module-level docstrings instead (e.g., `"""Load boot-sequence contract or fallback."""`). Per SF-01 systemic finding. |
| IC-HDR-2 | **NO** | Zero files have formal RESPONSIBILITIES header. Docstrings partially describe responsibility. |
| IC-HDR-3 | **NO** | Zero files have formal NOT RESPONSIBLE FOR header. |
| IC-HDR-4 | **NO** | Zero files have formal DEPENDENCIES header. Imports are clear but not documented in header format. |
| IC-HDR-5 | **YES** | Docstring headers are persistent — no evidence of removal across any file. |
| IC-SCALE-1 | **N/A** | Prompts/missions are content files with no data structures that grow with scale. Loaders read single files. |
| IC-SCALE-2 | **NO** | `_protocol.py` calls `doc.read_text()` without size limit. `party.py` opens YAML files without size limit. `_inbox.py` reads contracts without timeout. At current scale these are fine but no explicit protections exist. |
| IC-SCALE-3 | **NO** | `roles/__init__.py` and `capabilities/__init__.py` call `prompt_file.read_text()` without size limit. `loader.py` reads YAML files with `open(path)` without size guard. All files are currently small but no streaming/limiting. |
| IC-SCALE-4 | **NO** | No assumptions documented in code comments (e.g., "assumes prompt files are small", "assumes YAML is well-formed"). |
| IC-DATA-1 | **YES** | Mission YAML has a defined schema: requires `name` and non-empty `requires` list. Validated in `loader.py:_validate()`. |
| IC-DATA-2 | **YES** | Runtime validation via `_validate()` — checks for missing keys, validates capabilities against `VALID_CAPABILITIES`. |
| IC-DATA-3 | **YES** | Validation errors include expected vs received: `"unknown capability '{cap}'. Valid: {sorted(VALID_CAPABILITIES)}"`. |
| IC-DATA-4 | **YES** | Schema defined in `loader.py` (Mission dataclass + `_validate` function). Single authoritative location. |
| IC-DATA-5 | **NO** | No integration tests verify schema matches actual YAML files. `test_get_agent_prompt.py` tests crew YAML, not mission YAML. Missions have zero tests per SF-04. |
| IC-VER-1 | **YES** | Build passes — `uv run pytest` confirmed. |
| IC-VER-2 | **YES** | All imports present and correct. |
| IC-VER-3 | **YES** | Tests pass. |
| IC-VER-4 | **YES** | Build/test discipline evident. |

### Pragmatic Programmer (selected rules)

| Rule | Status | Evidence |
|------|--------|----------|
| PP-DRY-1 | **NO** | **Two DRY violations found:** (1) 6 of 7 role prompts repeat identical "Execute assigned tasks, report results." opening line and identical 7-line "Self-service chore tasks" block (auditor, builder, coder, oracle, planner, recon). This is inter-template duplication — a shared base could be injected. (2) Each of `_boot.py`, `_protocol.py`, `_rules.py`, `_inbox.py` contains hardcoded fallback prompt text duplicating content that also lives in contract YAML files. The fallback is intentional (resilience) but creates two authoritative representations of the same prompt content. |
| PP-DRY-2 | **NO** | The self-service chore block is copy-pasted across 6 role prompts verbatim. This is exactly inter-developer duplication — if the chore CLI syntax changes, 6 files must be updated. |
| PP-DRY-3 | **YES** | Reuse is easy: `load_role_prompt(role)` and `load_capability_prompts(capabilities)` are simple one-call interfaces. `build_boot_prompt()` and `build_inbox_prompt()` compose cleanly from sub-loaders. Adding a new capability = create `capabilities/{name}/prompt.md`, no Python changes needed. |
| PP-ORTH-1 | **YES** | prompts/ and missions/ are independent packages with no cross-imports. prompts/ handles text assembly; missions/ handles team composition. Neither imports the other. |
| PP-ORTH-2 | **NO** | `missions/loader.py` reads `os.getenv("MINION_MISSIONS_DIR")` directly (line 23) instead of going through `defaults.py`. Per SF-05 systemic finding. |
| PP-ORTH-3 | **YES** | Changes to prompt templates don't ripple to mission code and vice versa. Adding a new role prompt or capability prompt requires no Python changes. |
| PP-CRAFT-5 | **YES** | File names are highly descriptive: `_boot.py`, `_protocol.py`, `_rules.py`, `_history.py`, `_inbox.py` clearly communicate purpose. Subdirectory names `capabilities/build/`, `roles/lead/` are self-documenting. Mission template names (`bugfix.yaml`, `incident-response.yaml`) immediately communicate intent. |
| PP-REQ-3 | **YES** | Prompt templates are parameterized content — they use `{you}`, `{agent}`, `{role}` placeholders. Python loaders perform string substitution via `.replace()`. Mission templates are metadata — capability requirements are data, not hardcoded logic. The `resolve_slots()` function uses `CLASS_CAPABILITIES` mapping (defined in `auth.py`) to resolve capabilities to classes. Policy is metadata. |
| PP-DECOUPLE-1 | **YES** | No train wrecks in prompt or mission code. Deepest chain is `poll_data.get("messages", [])` — standard dict access. |
| PP-DECOUPLE-5 | **NO** | `missions/loader.py` line 23: `os.getenv("MINION_MISSIONS_DIR")` — config not externalized through `defaults.py`. Same as PP-ORTH-2. |
| PP-CONTRACT-1 | **NO** | No preconditions/postconditions documented. `load_role_prompt()` silently returns empty string for unknown roles — no contract about what happens with invalid input. `format_inbox()` has no precondition on `poll_data` structure. |
| PP-CONTRACT-2 | **YES** | Mission loader crashes early: `raise FileNotFoundError` for missing mission, `raise ValueError` for invalid schema. Good fail-fast behavior. |

### Clean Architecture (selected rules)

| Rule | Status | Evidence |
|------|--------|----------|
| CA-COMP-4 | **YES** | Classes that change together are colocated: `loader.py` + `resolver.py` + `party.py` + `spawn.py` all live in `missions/`. Prompt builders (`boot_prompt.py`, `inbox_prompt.py`, `watcher_prompt.py`) and sub-loaders (`_boot.py`, `_protocol.py`, `_rules.py`, `_inbox.py`, `_history.py`) all live in `prompts/`. |
| CA-COMP-5 | **YES** | Classes used together are colocated. `build_boot_prompt()` uses `_boot`, `_protocol`, `_rules` — all in same package. `resolve_and_spawn()` uses `loader`, `resolver`, `party` — all in same package. |
| CA-SCRM-2 | **YES** | File names communicate content clearly. A stranger can tell exactly what each file does: `boot_prompt.py` builds boot prompts, `loader.py` loads missions, `resolver.py` resolves capability slots. The `capabilities/` and `roles/` subdirectories with per-concept `prompt.md` files are exemplary filesystem-as-DB design. |

---

## Findings

| # | Rule | Severity | Affected Files | Description | Remediation |
|---|------|----------|----------------|-------------|-------------|
| F-01 | PP-DRY-1, PP-DRY-2 | **Moderate** | `roles/auditor/prompt.md`, `roles/builder/prompt.md`, `roles/coder/prompt.md`, `roles/oracle/prompt.md`, `roles/planner/prompt.md`, `roles/recon/prompt.md` | 6 of 7 role prompts contain identical "Execute assigned tasks, report results." opening and identical 7-line "Self-service chore tasks" block. Copy-paste duplication — if chore CLI syntax changes, 6 files must be updated. | Extract common blocks into a `roles/_common/base.md` and have `load_role_prompt()` prepend/append common sections. Or use a template include mechanism. |
| F-02 | PP-DRY-1 | **Low** | `_boot.py`, `_protocol.py`, `_rules.py`, `_inbox.py` | Hardcoded fallback prompt text in each Python loader duplicates content from contract YAML files. Two authoritative sources for the same prompt content. Fallback is intentional for resilience but creates drift risk. | Accept as designed (resilience pattern). Add a comment documenting that fallback text must stay in sync with contracts. Or add a test that verifies fallback matches contract content when contract is available. |
| F-03 | IC-HDR-1 through IC-HDR-4 | **Major** (systemic) | All 13 .py files in prompts/ and missions/ | Zero files have formal PURPOSE/RESPONSIBILITIES/NOT RESPONSIBLE/DEPENDENCIES headers. All use informal docstrings. Per SF-01 systemic finding — applies to all 181 Python files in the codebase. | Add formal headers per IC skill mandate. For these ~13 files, mechanical fix. |
| F-04 | TDD-COV-1, IC-DATA-5 | **Moderate** | `missions/` package | Zero behavioral tests for missions package. No test verifies: mission YAML loading, resolver slot computation, party suggestion, or spawn flow. `test_get_agent_prompt.py` tests crew YAML config but not missions. Per SF-04 systemic finding. | Write tests for: `load_mission()` happy/error paths, `resolve_slots()` with various capability sets, `list_missions()`, `suggest_party()` with mock crew data. |
| F-05 | PP-ORTH-2, PP-DECOUPLE-5 | **Low** | `missions/loader.py` line 23 | Direct `os.getenv("MINION_MISSIONS_DIR")` instead of using `defaults.py` as canonical config source. Per SF-05 systemic finding. | Route through `defaults.py` or create a `defaults.missions_dir()` function. |
| F-06 | IC-SCALE-2, IC-SCALE-3 | **Low** | `_protocol.py`, `roles/__init__.py`, `capabilities/__init__.py`, `missions/loader.py`, `missions/party.py` | File reads without size limits. `read_text()` and `open()` calls on prompt/mission files have no size guard. All files are currently small (< 5KB) so risk is theoretical at current scale. | Acceptable at current scale. If prompts grow, add size checks. Document assumption: "prompt/mission files expected to be < 100KB". |
| F-07 | PP-CONTRACT-1 | **Low** | `roles/__init__.py`, `capabilities/__init__.py` | `load_role_prompt()` silently returns `""` for unknown roles. `load_capability_prompts()` silently skips missing capabilities. No contract on what happens with invalid input — caller can't distinguish "role has empty prompt" from "role doesn't exist". | Add optional `strict=False` parameter that raises for unknown roles/capabilities when True. Or log a warning. |
| F-08 | IC-SCALE-4 | **Low** | All .py files | No assumptions documented in code comments. Implicit assumptions: prompt files are small, YAML is well-formed, contract files exist in docs_dir, `CLASS_CAPABILITIES` covers all valid capabilities. | Add ASSUMPTION comments per IC skill. |

---

## Strengths

1. **Excellent content-code separation.** Prompt content lives in .md files, mission definitions in .yaml files. Python loaders are genuinely thin — they read files and concatenate strings. You can change any prompt without touching Python code. You can add a new capability or role by creating a directory with `prompt.md` — no code changes required.

2. **Filesystem-as-DB design for prompts.** The `capabilities/{name}/prompt.md` and `roles/{name}/prompt.md` directory structure is exemplary. Adding a new capability is literally `mkdir + write prompt.md`. The directory tree self-documents what capabilities and roles exist. This is exactly the pattern CLAUDE.md mandates.

3. **Clean composition pattern.** Prompt builders compose from independent sub-loaders: `_protocol.py`, `_rules.py`, `_boot.py`, `_inbox.py`, `_history.py`. Each sub-loader handles one concern. The top-level builders (`boot_prompt.py`, `inbox_prompt.py`, `watcher_prompt.py`) are pure assembly — no business logic.

4. **Mission schema validation.** `loader.py:_validate()` validates YAML structure at load time with clear error messages including expected values. Capabilities are validated against `VALID_CAPABILITIES` from `auth.py` — single source of truth for what capabilities are valid.

5. **Graceful degradation.** Every prompt sub-loader has a hardcoded fallback for when contract files are missing. This means agent prompts work even without a full docs_dir installation. Resilience over purity — correct tradeoff for a system where agents must always get a usable prompt.

6. **Descriptive naming throughout.** File names immediately communicate purpose. The leading underscore convention (`_boot.py`, `_protocol.py`) clearly marks internal sub-loaders vs public builders (`boot_prompt.py`). Mission template names (`incident-response.yaml`, `prototype.yaml`) are self-documenting.

7. **Mission resolver is well-designed.** `resolve_slots()` implements a clean greedy set-cover algorithm with deterministic tiebreaking (alphabetical). Always starts with lead. Clean separation: loader handles YAML, resolver handles math, party handles crew matching, spawn handles orchestration.

8. **Orthogonal packages.** `prompts/` and `missions/` have zero cross-imports. They can evolve independently. Neither knows about the other's internals.

---

## Summary

| Metric | Count |
|--------|-------|
| Files audited (Python) | 18 (.py) |
| Files audited (templates) | 28 (.md + .yaml) |
| Rules evaluated | 28 |
| PASS | 17 |
| FAIL (NO) | 10 |
| N/A | 1 |
| Findings | 8 |
| Critical | 0 |
| Major (systemic) | 1 (F-03: headers — same as SF-01) |
| Moderate | 2 (F-01: DRY duplication, F-04: zero mission tests) |
| Low | 5 (F-02, F-05, F-06, F-07, F-08) |

**Overall assessment:** The prompts and missions packages are among the best-designed areas of the codebase. The content-code separation, filesystem-as-DB pattern, and clean composition are strong. The main issues are systemic (headers, config access, test coverage) rather than domain-specific. The one domain-specific finding worth addressing is the copy-paste duplication across role prompts (F-01).
