# Research: WS4 Code Hygiene — Existing Code Survey

## 4.1 Dependency Layer Violations
- **db/ imports auth:** Need to verify if still present after v1 refactoring (defaults.py was created to break circular deps).
- **Task imports _tmux:** `src/minion/crew/_tmux.py` is imported by crew modules. Need to verify if task files still import it directly.
- **comms <-> crew coupling:** `src/minion/comms/register.py` — need to verify if crew-context-merge logic still exists there.
- **Status:** Partially addressed by v1 refactoring (moved staleness/triggers to defaults.py), but full audit needed.

## 4.2 Code Duplication
- **_resolve_or_404:** `src/minion/network/handlers/_resolve_project_or_404.py` now exists as a shared module. It's imported by backlog.py, requirements.py, and projects.py handlers. FIXED.
- **_append_error_log:** Still duplicated between `src/minion/providers/codex.py` and `src/minion/providers/gemini.py`. Also referenced in `cli_provider_protocol.py`.
- **Role prompt duplication:** Need to check `src/minion/prompts/roles/`.
- **DBMixin pattern:** `src/minion/db/connection.py` now has a shared `connect()` function. PARTIALLY FIXED.
- **Provider error classifiers:** Still structural duplication between codex/gemini.

## 4.3 CLI Consistency
- **Verb vocabulary:** Not systematically addressed.
- **Exit codes:** Need audit — `src/minion/output.py` has remediation hints but exit code convention may still be inconsistent.
- **Short flags:** Only 1 CLI option uses short flags across ~250 options. NOT ADDRESSED.
- **Top-level command leaks:** deregister, rename, interrupt, resume — need to check if still at root.

## 4.4 Configuration Consistency
- **Config cascade:** `-C` flag behavior documented but may still have non-transparent env var mutation.
- **Network env vars bypass defaults.py:** `src/minion/defaults.py` now defines resolve_network_url(), resolve_cluster_token(), resolve_network_insecure(). FIXED — env vars are now routed through defaults.py.
- **Daemon WAL consistency:** `src/minion/db/connection.py` connect() function standardizes WAL and row_factory. FIXED.

## 4.5 Dead/Unreachable Code
- **Scaling endpoints:** `src/minion/network/handlers/scaling.py` exists but endpoints may be unreachable (need to verify router registration).
- **HTTP log suppression:** Server likely still suppresses logs.
- **TaskDB post-close:** Need to verify.
- **Bare except in intel:** Need to check if narrowed to sqlite3.IntegrityError.
- **Generic file names:** Most files now follow filesystem-as-db naming convention (evidenced by descriptive names like `path_resolution_and_slug.py`, `timestamp_and_agent_registry.py`). Some generic names remain.
