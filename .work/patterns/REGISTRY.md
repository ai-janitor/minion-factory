# Pattern Registry

Decided conventions and patterns for the minion-factory codebase. Agents and contributors
should follow these patterns for consistency. Each entry explains the pattern, why it was
chosen, and where to find the canonical implementation.

---

## Error Handling: MinionError hierarchy

**Pattern:** All user-facing errors inherit from `MinionError`. CLI commands catch
`MinionError` and print a clean message. Unexpected exceptions propagate with tracebacks.

**Why:** Separates expected failures (bad input, missing resources) from bugs. Agents see
clean error messages; developers see tracebacks for unexpected failures.

**Canonical:** `src/minion/tasks/engine.py` raises `MinionError` subtypes. CLI layers
catch them in click commands.

**Anti-pattern:** Bare `raise Exception("...")` or `sys.exit(1)` without a clean error
class. These bypass structured error handling.

---

## Logging: Structured stderr warnings

**Pattern:** Use `print(f"WARNING: ...", file=sys.stderr)` for non-fatal warnings.
No logging framework (stdlib `logging`) is used. Critical daemon errors use the
`_log()` method on `AgentDaemon` which writes to per-agent log files.

**Why:** Zero-dependency logging. Agents read stderr for diagnostics. The daemon log
files (`~/.minion-swarm/logs/`) provide persistent history. A logging framework adds
configuration complexity without value for the current agent-based architecture.

**Canonical:** `src/minion/daemon/runner/_db.py` uses `self._log()`. Source modules
use `print(..., file=sys.stderr)`.

**Anti-pattern:** Using `logging.getLogger()` or silently swallowing exceptions with
bare `except: pass`.

---

## DB Access: get_db() with WAL mode

**Pattern:** All DB connections go through `get_db()` (or `_daemon_connect()` in the
daemon runner). Every connection sets: WAL journal mode, `row_factory = sqlite3.Row`,
`busy_timeout = 5000ms`, and `foreign_keys = ON`.

**Why:** WAL mode allows concurrent reads during writes (critical for multi-agent).
`row_factory = sqlite3.Row` gives dict-like access. `busy_timeout` prevents immediate
`OperationalError` under contention. Foreign keys enforce referential integrity.

**Canonical:** `src/minion/db/connection.py:get_db()` is the primary factory.
`src/minion/daemon/runner/_db.py:_daemon_connect()` is the daemon equivalent.

**Anti-pattern:** Raw `sqlite3.connect()` without WAL/row_factory/busy_timeout. This
was the daemon inconsistency fixed in backlog #86.

---

## Config: defaults.py as single source of truth

**Pattern:** All environment variable names and default values are defined in
`src/minion/defaults.py`. Resolver functions (`resolve_db_path()`, `resolve_docs_dir()`,
`resolve_network_url()`, etc.) provide the lookup logic. Consuming modules import from
defaults.py rather than reading `os.environ` directly.

**Why:** Single source of truth prevents env var name typos and inconsistent defaults
across modules. Resolver functions encapsulate fallback logic (env > convention > default).

**Canonical:** `src/minion/defaults.py` defines all `ENV_*` constants and `resolve_*()`
functions. `src/minion/db/connection.py` imports `resolve_db_path`.

**Anti-pattern:** `os.environ.get("MINION_SOME_VAR", "hardcoded-default")` scattered
across modules. This was the issue fixed in backlog #62.

---

## Path Resolution: resolve_path() for relative paths

**Pattern:** Use `defaults.resolve_path(raw_value, base)` to resolve possibly-relative
paths against a base directory. Both `crew/config.py` and `daemon/config.py` use this
for consistent path handling.

**Why:** Crew YAMLs and daemon configs reference paths relative to the config file
location or project dir. A single resolver prevents each module from implementing its
own expanduser/resolve logic.

**Canonical:** `src/minion/defaults.py:resolve_path()`.

**Anti-pattern:** Inline `Path(raw).expanduser(); if not path.is_absolute(): ...` logic
duplicated across config loaders.

---

## Test Isolation: isolated_db fixture

**Pattern:** Every test that touches the DB uses the `isolated_db` fixture from
`tests/conftest.py`. This creates a fresh `.work/` directory, sets `MINION_DB_PATH`,
resets the cached path, initializes schema, and changes cwd.

**Why:** Tests must not share state. The DB path is cached globally in `db.connection`,
so `reset_db_path()` must be called to prevent cross-test contamination.

**Canonical:** `tests/conftest.py:isolated_db` and variants.

**Anti-pattern:** Manually calling `init_db()` with `os.environ` manipulation in each
test file. This was the duplication fixed in backlog #70.

---

## Test Markers: unit / integration / smoke

**Pattern:** Every test file has a `pytestmark = pytest.mark.<level>` module-level marker.
- `unit`: Pure logic, no DB/filesystem/network. Fast.
- `integration`: Touches DB or CLI runner. Medium speed.
- `smoke`: End-to-end flows exercising multiple subsystems. Slowest.

**Why:** Enables selective test runs: `pytest -m unit` for fast feedback during
development, full suite for CI.

**Canonical:** `pyproject.toml [tool.pytest.ini_options]` defines markers.
`tests/conftest.py` provides shared fixtures.

---

## Filesystem as DB: Naming conventions

**Pattern:** File and folder names encode purpose, scope, and context. An agent should
understand the codebase by reading `ls -R`, not by opening files. Use 2-4 levels of
descriptive folder nesting.

**Why:** Context is precious for agents. Descriptive tree structure reduces the need to
read file contents just to understand organization.

**Canonical:** `CLAUDE.md` section "Filesystem as DB". Example:
`src/minion/daemon/runner/_constants.py` not `src/minion/daemon/constants.py`.

**Anti-pattern:** Generic names like `utils.py`, `helpers.js`, `misc/`. These force
agents to read file contents to understand purpose.
