# SU-14: Code Deduplication — Providers, Prompts, DB Patterns

**Wave:** 5 (depends on SU-01)
**Requirements:** 4.2
**Dependencies:** SU-01
**Dependents:** SU-13

---

## Purpose

Extract four duplication clusters into shared code, following the pattern registry's canonical patterns. Prevents creating new duplication while fixing old.

## Requirements Traceability

- **4.2 (Code Duplication):** "_append_error_log duplicated, role prompt self-service block duplicated 6x, DBMixin pattern 10x, provider error classifiers duplicated."

## Dependencies

- **SU-01 (Pattern Registry):** Canonical patterns define WHAT the deduplicated code should look like.

## Behavior

### Duplication 1: _append_error_log (codex.py + gemini.py)

**Current state:** Both `src/minion/providers/codex.py` and `src/minion/providers/gemini.py` have a `_append_error_log()` function with identical logic: append error details to a JSONL log file.

**Target:**
- Extract to `src/minion/providers/_shared_error_log.py` (or `src/minion/providers/error_log.py` if shared module naming convention prefers no underscore)
- Single function: `append_error_log(log_dir: str, error_type: str, details: dict) -> None`
- Both codex.py and gemini.py import and call it
- Delete the duplicated functions

**Contract (E-08 for SU-13):** Extracted module path is `src/minion/providers/_shared_error_log.py`.

### Duplication 2: Role Prompt Self-Service Block (6 repetitions)

**Current state:** `src/minion/prompts/roles/*.py` — 6 of 7 role prompt files contain an identical "self-service" block that injects common agent instructions.

**Target:**
- Extract the common block to `src/minion/prompts/roles/_shared_self_service_block.py`
- Single function: `self_service_block() -> str` returning the common prompt text
- Each role prompt file calls this function instead of duplicating the block
- Role-specific customizations remain in each file (only the COMMON part is extracted)

**Identification:** The shared block likely includes instructions about polling, set-context, inbox discipline — common to all roles.

### Duplication 3: DBMixin Pattern (10 repetitions)

**Current state:** `connect()` in `db/connection.py` standardizes connections. Research says "PARTIALLY FIXED." Need to verify if the 10 repetitions of connect-execute-commit-close have been reduced.

**Target:**
- Verify current state: count remaining instances of manual connect-execute-commit-close outside of connection.py
- If still duplicated: ensure all DB access goes through `get_db()` or `connect()` from connection.py
- Pattern: `conn = get_db(); cursor = conn.cursor(); try: ... finally: conn.close()` — this is the canonical pattern from the pattern registry

### Duplication 4: Provider Error Classifiers

**Current state:** codex.py and gemini.py both classify HTTP errors into categories (transient, permanent, auth, rate_limit) with similar logic.

**Target:**
- Extract to `src/minion/providers/_shared_error_classifier.py`
- Single function: `classify_error(status_code: int, error_body: str) -> str` returning one of {"transient", "permanent", "auth", "rate_limit"}
- Provider-specific overrides: if a provider has unique status codes, it can extend the base classifier
- Pattern: chain of `if status_code == 429: return "rate_limit"` checks, per pattern registry

**Contract (E-08 for SU-13):** Extracted module path is `src/minion/providers/_shared_error_classifier.py`.

## Constraints

- Follow pattern registry canonical patterns (SU-01)
- Must not change any external behavior
- Extracted modules must not introduce new dependencies
- Must update all callers to use the shared module
- Must document extracted module paths for SU-13 (E-08 contract)

## Edge Cases

1. **Near-duplicates, not exact:** The duplicated code may differ slightly between files. Identify the common core, extract that, and leave file-specific customizations in place.
2. **Circular imports from shared modules:** Extracted modules in providers/ should not import from providers/*.py — only stdlib and shared minion utilities.
3. **Test coverage for extracted modules:** New shared modules need their own tests. Write at least one test per extracted function.
4. **DBMixin already fixed:** If v1 already reduced the 10 repetitions to an acceptable level (2-3 remaining), document as "verified complete" and move on.

## Current State

- _resolve_or_404 was already extracted (FIXED)
- _append_error_log still duplicated (confirmed)
- Role prompt block duplication needs verification
- DBMixin partially fixed
- Provider error classifiers need verification

## Test Contract

- **Test 1:** `grep -r "_append_error_log" src/minion/providers/` shows only the shared module + import statements.
- **Test 2:** Role prompt files contain `from ._shared_self_service_block import` (or equivalent) — no inline duplication.
- **Test 3:** Provider error classifier: `from ._shared_error_classifier import classify_error` exists in both codex.py and gemini.py.
- **Test 4:** All existing tests pass after extraction.
- **Test 5:** New shared modules have their own test files.
