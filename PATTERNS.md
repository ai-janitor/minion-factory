# Pattern Registry — minion-factory Codebase Conventions

This document catalogs the recurring patterns used across minion-factory. Follow these conventions when adding new code. Each pattern includes where it's used, how to do it right, and what NOT to do.

---

## 1. DB Access — `get_db()` + context-local connection

**Where used:** `src/minion/tasks/create_task.py`, `src/minion/comms/send.py`, `src/minion/backlog/add_item.py`, `src/minion/warroom.py`, `src/minion/filesafety.py`, and ~30 other modules.

**Convention:**
```python
from minion.db import get_db, now_iso

def do_something() -> dict[str, object]:
    conn = get_db()              # WAL-mode, row_factory=Row, busy_timeout=5000
    cursor = conn.cursor()
    now = now_iso()              # ISO-8601 timestamp from single source
    try:
        cursor.execute("SELECT ...", (param,))
        row = cursor.fetchone()
        if not row:
            return {"error": "Not found"}
        # ... mutations ...
        conn.commit()
        return {"status": "ok", ...}
    finally:
        conn.close()
```

- Always import from `minion.db` (the package `__init__.py` re-exports everything).
- Use `get_db()` for project-local DB, `get_coordinator_db()` for global coordinator DB, `connect(path)` when you have an explicit path.
- Always use `now_iso()` for timestamps — never `datetime.now().isoformat()` directly.
- Access columns by name via `sqlite3.Row` (e.g., `row["agent_class"]`), never by index.
- Close connections after use (try/finally or context manager).

**Anti-pattern:**
```python
# WRONG: direct sqlite3.connect bypasses WAL/busy_timeout/row_factory setup
import sqlite3
conn = sqlite3.connect(".work/minion.db")

# WRONG: hardcoded path instead of resolution
conn = sqlite3.connect("/Users/someone/.work/minion.db")

# WRONG: custom timestamp format
from datetime import datetime
now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
```

---

## 2. Error Handling — Raise internally, return dicts at CLI boundary

**Where used:** `src/minion/exceptions.py` (defines hierarchy), every `cli/*_cmds.py` (returns dicts), every library module under `tasks/`, `comms/`, `db/` (raises exceptions).

**Convention:**
```python
# INTERNAL LIBRARY CODE — raise MinionError subclasses
from minion.exceptions import MinionNotFoundError, MinionStateError

def get_task(task_id: int):
    row = ...
    if not row:
        raise MinionNotFoundError(f"Task #{task_id} not found")

# CLI BOUNDARY CODE — return Result dicts
def create_task(agent_name: str, ...) -> dict[str, object]:
    if not agent:
        return {"error": "Agent not registered"}
    # ... success ...
    return {"status": "created", "task_id": 42}
```

Exception hierarchy: `MinionError` (base) -> `MinionNotFoundError`, `MinionPermissionError`, `MinionConfigError`, `MinionStateError`, `MinionDBError`.

Rule of thumb: if the function is called from a Click command handler, return a dict. If called from another library function, raise.

**Anti-pattern:**
```python
# WRONG: raising exceptions in CLI-boundary code (produces tracebacks instead of JSON)
@cli.command()
def my_command():
    raise ValueError("bad input")  # user sees a traceback

# WRONG: returning error dicts in internal library code (caller can't catch)
def internal_helper():
    return {"error": "something failed"}  # caller has to check dict keys instead of try/except

# WRONG: bare Exception or ValueError instead of MinionError subclass
raise Exception("task not found")  # use MinionNotFoundError
```

---

## 3. CLI Command Structure — Click groups with `register_commands()` pattern

**Where used:** Every `src/minion/cli/*_cmds.py` file (18 command modules).

**Convention:**
```python
"""Description of this command group.

Purpose: ...
Rationale: ...
Responsibility: ...
Organization: Click command group with subcommands."""

from __future__ import annotations
import click
from minion.cli.main import _agent_option, _output

def register_commands(cli: click.Group) -> None:
    """Attach commands to the root CLI."""

    @cli.group("mygroup")
    @click.pass_context
    def my_group(ctx: click.Context) -> None:
        """Group help text."""
        pass

    @my_group.command("subcommand")
    @_agent_option(required=True)        # use _agent_option for --agent (auto-heartbeat)
    @click.option("--flag", ...)
    @click.pass_context
    def subcommand(ctx: click.Context, agent: str, flag: str) -> None:
        """Command help text."""
        from minion.some_module import do_thing   # lazy import inside handler
        _output(do_thing(agent, flag), ctx.obj["human"], ctx.obj["compact"])
```

Key rules:
- Each `*_cmds.py` exports a `register_commands(cli)` function.
- `cli/main.py` imports and calls all `register_commands()` at module load.
- Use `_agent_option()` (not raw `click.option("--agent")`) — it auto-registers heartbeat callbacks.
- Use `_output()` (re-exported from `output.py`) for all command output — supports JSON/human/compact modes.
- Lazy-import business logic inside command handlers to avoid circular imports.

**Anti-pattern:**
```python
# WRONG: defining commands at module level instead of inside register_commands()
@click.command()
def my_cmd(): ...

# WRONG: using click.option("--agent") directly (misses heartbeat)
@click.option("--agent", required=True)

# WRONG: using print() or click.echo() for structured output (bypasses JSON mode)
click.echo(f"Task {task_id} created")  # use _output({"status": "created", ...})

# WRONG: eager imports at module top (causes circular import chains)
from minion.tasks.create_task import create_task  # move inside the handler
```

---

## 4. Config Loading — Env vars with resolvers in `defaults.py`

**Where used:** `src/minion/defaults.py` (canonical source), consumed by `db/connection.py`, `auth.py`, `network/`, `crew/`, `providers/`.

**Convention:**
```python
# In defaults.py — define env var name + resolver function
ENV_MY_SETTING = "MINION_MY_SETTING"

def resolve_my_setting() -> str:
    """Resolve from env, with a sensible default."""
    return os.getenv(ENV_MY_SETTING, "default_value")
```

Key rules:
- All env var names are defined as constants in `defaults.py` (prefixed `ENV_`).
- Each env var has a `resolve_*()` function that reads it with a default.
- Path resolution uses `resolve_db_path()` which walks up from cwd to find `.work/minion.db` (respects git repo boundaries).
- Constants like `CLASS_STALENESS_SECONDS`, `TRIGGER_WORDS`, `BATTLE_PLAN_STATUSES` also live in `defaults.py` to break circular import chains.

**Anti-pattern:**
```python
# WRONG: reading env vars inline with hardcoded names
db = os.getenv("MINION_DB_PATH", ".work/minion.db")  # use resolve_db_path()

# WRONG: defining constants in the module that uses them (causes circular imports)
# In auth.py:
CLASS_STALENESS = {"coder": 300}  # should be in defaults.py

# WRONG: config not centralized — different modules using different defaults
# file1.py: os.getenv("MINION_DB", "db.sqlite")
# file2.py: os.getenv("MINION_DB_PATH", ".work/minion.db")
```

---

## 5. Testing — `isolated_db` fixture + behavioral test naming

**Where used:** `tests/conftest.py` (fixtures), all 55+ test files in `tests/`.

**Convention:**
```python
"""Behavioral tests for <module> — <what's tested>.

Purpose: Verify <module>'s public surface: <list key functions/classes>.
"""
import pytest

pytestmark = pytest.mark.unit

def test_<function>_<behavior>(isolated_db):
    """When <condition>, <function> <expected outcome>."""
    from minion.db import register_agent_db
    register_agent_db("test-agent", "coder")
    # ... exercise the function ...
    assert result["status"] == "ok"

def test_<function>_rejects_<bad_input>(isolated_db):
    """<function> returns error when given <bad_input>."""
    result = some_function("invalid")
    assert "error" in result
```

Key rules:
- Use `isolated_db` fixture for any test touching the DB — it creates a temp `.work/` dir with isolated SQLite.
- Use `isolated_db_with_coordinator` when testing cross-project features.
- Use `runner` fixture (`CliRunner`) for CLI integration tests.
- Test names follow `test_<function>_<behavior>` pattern. Docstring describes the scenario.
- Mark unit tests with `pytestmark = pytest.mark.unit`.
- Helper fixtures in `conftest.py`: `register_lead`, `register_coder`, `insert_battle_plan()`, `insert_open_task()`.
- Import the module under test inside the test function (not at module level) to ensure DB isolation.

**Anti-pattern:**
```python
# WRONG: testing against the real DB
from minion.db import get_db
conn = get_db()  # hits .work/minion.db in the real project

# WRONG: manually creating temp DBs instead of using isolated_db
db_path = "/tmp/test.db"
conn = sqlite3.connect(db_path)

# WRONG: generic test names
def test_it_works():  # what does "it" refer to?

# WRONG: no docstring explaining the scenario
def test_create_task_fails():
    ...  # fails how? under what conditions?
```

---

## 6. File Comment Headers — Purpose, Rationale, Responsibility, Organization

**Where used:** Every `.py` file in `src/minion/`. This is a hard project rule (see CLAUDE.md).

**Convention:**
```python
"""Short description — one-line summary.

Purpose: What this module does.
Rationale: Why it exists (what problem it solves, what it replaced).
Responsibility: What it IS responsible for. What it is NOT responsible for.
Organization: How it's structured (standalone functions, Click group, class, etc.)."""
```

These headers are PERMANENT. Implementation code goes between/below them. Only change headers if the plan was wrong (update plan first, then code).

Pseudo-logic comments describe logic flow before implementation:
```python
# Pseudo: 1. Validate input  2. Look up agent  3. Check permissions  4. Execute  5. Return result
```

**Anti-pattern:**
```python
# WRONG: no module docstring
import os
def my_func(): ...

# WRONG: deleting headers during "cleanup"
# (headers are the blueprint — code fills the gaps)

# WRONG: generic description
"""Utilities."""  # describe what utilities, for what purpose
```

---

## 7. Filesystem-as-DB — Descriptive paths, slugified filenames

**Where used:** `src/minion/fs.py` (path builders), `src/minion/intel/` (intel docs), `.work/` directory structure, `src/minion/backlog/path_resolution_and_slug.py`.

**Convention:**
```python
from minion.fs import _slugify, _timestamp, atomic_write_file

# Build paths with timestamps and slugs
fname = f"{_timestamp()}-{_slugify(agent_name, 20)}-{_slugify(slug, 20)}.md"
path = os.path.join(SOME_DIR, fname)

# Write atomically (temp file + rename)
atomic_write_file(path, content)

# Read with size guard
from minion.fs import read_content_file
content = read_content_file(path)  # returns "" if missing or >10MB
```

Key rules:
- File/folder names encode purpose, scope, and context. `tree` should be self-documenting.
- Use `_slugify()` to make strings filesystem-safe.
- Use `_timestamp()` for filename timestamps (compact ISO: `20260219T143022`).
- Use `atomic_write_file()` for writes (write-to-temp, then `os.replace`).
- Use `read_content_file()` for reads (handles missing files and size limits).
- SQLite stores the path; agents read the file directly.

**Anti-pattern:**
```python
# WRONG: direct file writes (not atomic — partial writes on crash)
with open(path, "w") as f:
    f.write(content)

# WRONG: generic filenames
"data.json", "output.txt", "temp.md"

# WRONG: no size guard on reads
with open(path) as f:
    content = f.read()  # could be 2GB
```

---

## 8. Logging — `logging.getLogger(__name__)` + configure once at CLI startup

**Where used:** `src/minion/logging_setup.py` (config), library modules across `tasks/`, `comms/`, `crew/`, `providers/`, `daemon/`.

**Convention:**
```python
import logging
log = logging.getLogger(__name__)

# In library code:
log.warning("something unexpected: %s", detail)
log.error("operation failed: %s", exc)
log.debug("trace info: %s", data)
```

- `configure_logging()` is called once in `cli/main.py` at startup.
- Default level: WARNING. Set `MINION_DEBUG=1` for DEBUG.
- Logs go to stderr — keeps stdout clean for JSON output.
- CLI user-facing output uses `click.echo()` or `_output()` — NOT logging.

**Anti-pattern:**
```python
# WRONG: print to stderr for diagnostics
import sys
print(f"WARNING: {msg}", file=sys.stderr)  # use log.warning()

# WRONG: calling basicConfig in library modules
logging.basicConfig(level=logging.DEBUG)  # only cli/main.py does this

# WRONG: using logging for user-facing CLI output
log.info(f"Task {id} created")  # use _output({"status": "created", ...})
```

---

## 9. State Machines — Explicit transition dicts with validation

**Where used:** `src/minion/state_machines.py` (daemon + agent states), `src/minion/tasks/dag.py` (task phase transitions).

**Convention:**
```python
from minion.state_machines import InvalidTransition

# Define transitions as dict[str, set[str]]
MY_TRANSITIONS: dict[str, set[str]] = {
    "idle":    {"working", "stopped"},
    "working": {"idle", "error"},
    "error":   {"idle", "stopped"},
}

# Validate before transitioning
def validate_transition(machine, from_state, to_state):
    valid = machine.get(from_state, set())
    if to_state not in valid:
        raise InvalidTransition("my_machine", from_state, to_state, valid)
```

Task DAG flows are defined in YAML files under `task-flows/` and loaded by `tasks/loader.py`. Each flow type (bugfix, feature, chore) defines its own phase sequence and valid transitions.

**Anti-pattern:**
```python
# WRONG: ad-hoc status checks scattered across code
if status in ("open", "in_progress"):
    new_status = "closed"  # no validation of valid transitions

# WRONG: string comparisons without a canonical transition dict
if old_status == "idle" and new_status == "working":
    ...  # fragile, easy to miss a case
```

---

## 10. Precondition Assertions — Guard clauses at function entry

**Where used:** `src/minion/fs.py`, `src/minion/db/connection.py`, `src/minion/defaults.py`, `src/minion/tasks/create_task.py`, and many others. Tracked as backlog #63.

**Convention:**
```python
def my_function(agent_name: str, path: str) -> dict:
    # SU-09: Precondition assertions
    assert agent_name, "agent_name must not be empty"
    assert "/" not in agent_name, f"agent_name must not contain path separators: '{agent_name}'"

    # For public API boundaries, use raise instead of assert:
    if not isinstance(path, str):
        raise TypeError(f"path must be str, got {type(path).__name__}")
    if not path:
        raise ValueError("path must not be empty")
```

- Use `assert` for internal invariants (can be optimized away with `-O`).
- Use `raise TypeError/ValueError` for public API boundaries where assertions must not be stripped.
- Comment with `# SU-09: Precondition assertions` or `# Precondition assertions — backlog #63` for traceability.

**Anti-pattern:**
```python
# WRONG: no validation — silent corruption downstream
def send_message(to_agent, message):
    # to_agent could be None, empty, or contain path traversal chars
    path = f"/inbox/{to_agent}/msg.md"

# WRONG: assert on user input in production code paths
assert user_input.isdigit()  # stripped by -O flag, use raise ValueError
```

---

## 11. Lazy Imports — Defer heavy imports inside function bodies

**Where used:** `src/minion/cli/*_cmds.py` (all command handlers), `src/minion/auth.py` (agent_classes), `src/minion/db/connection.py` (migrations).

**Convention:**
```python
# In CLI command handlers — import business logic inside the handler
@my_group.command("create")
@click.pass_context
def create(ctx, ...):
    """Create something."""
    from minion.tasks.create_task import create_task  # lazy import
    _output(create_task(...), ctx.obj["human"])

# In modules with circular dependency risk
def _agent_classes():
    from minion.tasks.agent_classes import get_valid_classes  # break cycle
    return get_valid_classes
```

Rationale: minion-factory has deep import chains (auth <-> tasks <-> comms <-> db). Lazy imports inside functions break circular dependencies and speed up CLI startup.

**Anti-pattern:**
```python
# WRONG: top-level import causing circular ImportError
from minion.tasks.create_task import create_task  # at module level in a CLI file
# This triggers: auth -> tasks -> comms -> auth -> ImportError
```
